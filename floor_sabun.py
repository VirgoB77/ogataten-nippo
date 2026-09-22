#!/usr/bin/env python3
"""2回ぶんの観測から、**入店と退店を出す**段。**取りに行かない。**

## この段がいちばん怖がっているもの

**取得が途中で切れた回を、「大量退店」と読むこと。**

    本当に起きたこと   64店のうち30店しか取れなかった
    まちがった読み     **34店が退店した**

一度こう書いてしまうと、**あとから直せない。**
「その日に34店消えた」という記録が残り、**次の回で34店が入店に化ける。**
履歴が二重に壊れる。

だから、この段は**差分を出す前に、観測が完全だったかを先に決める。**
**完全だと言えないなら、差分を出さずに止まる。**

## 4つの成功を、別々に持つ（正本9節）

    処理成功   段が最後まで走った
    観測成功   **原典を最後まで受け取れた**
    保存成功   受け取ったものが、次の段から読める場所に残った
    **差分判定成功**  **そのうえで、差分を出してよいと決められた**

**上3つが立っても、4つ目は立たないことがある。**
完全に受け取れていても、**差分の形が取得事故に似ている**なら、保留する。

## 完全かどうかは、**この段が推測しない**

**取得の層が知っていることを、そのまま受け取る。**

    todoita     転送が最後まで来たか（Content-Length と合ったか等）
    owari       原典の終わりの印が在るか（`</html>` 等）
    moto_kensuu 原典自身が「全◯件」と言っているか（**無ければ None**）

**どれか1つでも「分からない」なら、観測失敗。** 差分は出さない。
**「分からない」を「大丈夫」に倒さない**（3.4・既定は止まる側）。

## **固定のしきい値を、根拠なく本番のルールにしない**（統括・2026-09-21）

「前回64店だったから、次回60店未満なら失敗」——**これは根拠が無い。**
**何店まで減るのが普通か**は、**観測を続けないと分からない**（いまは1枚しかない）。

代わりに、**数ではなく形**を見る。

    **消えた店が、原典の並びの末尾に固まっているか**

途中で切れた取得は、**並びの後ろがまるごと落ちる。**
本当の退店は、**ばらばらの位置**で起きる。**これは数を決めなくても見られる。**

**⚠ この見方には前提がある。** 「原典の並びが、回をまたいで安定していること」。
**それはまだ測っていない**（観測点が1つしかない）。だから**これは二の矢**で、
一の矢は上の「取得の層が知っていること」。

## 表記ゆれは、**控えめにだけ揃える**

**無理に全部を同一視するルールは作らない**（統括の指示）。
揃えるのは、**機械が確実に同じだと言える範囲**だけ。

    NFKC        全角/半角の英数・カタカナ・記号（＆→&、･→・ など）
    空白を落とす 全角/半角スペースの有無
    大小を揃える ABC / abc

**長音と負符号（ー と -）は揃えない。** 別の字なので、**別扱いのまま出す。**
**揃えた範囲と、揃えなかった範囲を、両方記録する。**

## 区画IDが無いので、**原理的に分けられないもの**がある

原典に区画番号が無い（`kukaku_no` は70区画すべて空だった）。だから——

    同じ店が別の階へ移った        **入店1＋退店1**にしか見えない
    同じ場所でブランド名が変わった  **入店1＋退店1**にしか見えない

**「移転」とも「屋号替え」とも断定しない。** 分からないものは分からないままにする。
**そう書くこと自体が結果**（ルール⑥）。
"""
from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common.runday import today  # noqa: E402

KIROKU = HERE / "data" / "ref" / "floor-sabun.md"

# **4つの成功を別々に持つ**（正本9節）。1つにまとめない
SEIKOU = ("処理", "観測", "保存", "差分判定")

# **状態の語。** これが付いていても、在籍は在籍
JOTAI_GO = ("改装中", "一時休業", "休業中", "準備中", "リニューアル中",
            "工事中", "close", "closed")


def naraberu(s: str) -> str:
    """**控えめにだけ揃える。** 機械が確実に同じだと言える範囲まで。

    **長音と負符号は揃えない。** 別の字なので、別扱いのまま出す。
    """
    t = unicodedata.normalize("NFKC", s or "")
    t = "".join(c for c in t if not c.isspace())
    return t.casefold()


def jotai_wo_hazusu(s: str):
    """店名から**状態の表記**を外す。**外したことを返す。**

    「◯◯（改装中）」は、**◯◯が居なくなったのではない。**
    **外した事実も返す**ので、記録に「状態が付いた」と書ける。
    """
    moto = s or ""
    t = moto
    for g in JOTAI_GO:
        for kakko in ("（{}）", "({})", "【{}】", "[{}]", " {}", "　{}"):
            ku = kakko.format(g)
            for x in (ku, ku.upper(), ku.lower()):
                if x in t:
                    t = t.replace(x, "")
    t = t.strip()
    return (t or moto), (t != moto)


def kagi(mise: dict):
    """突き合わせの鍵。**階と、揃えた店名。**

    **区画番号は使わない**——原典に無い（70区画すべて空だった）。
    """
    na, _ = jotai_wo_hazusu(mise.get("mei") or mise.get("mise") or "")
    return (mise.get("kai") or "", naraberu(na))


def kansei(shirushi: dict, kazu: int):
    """**観測が完全だったか。** この段は推測しない。取得の層に聞く。

    返すのは `(完全か, わけ)`。**1つでも「分からない」なら、完全ではない。**
    """
    if shirushi is None:
        return False, "取得の層から印が渡されていない（**分からない**）"
    if shirushi.get("todoita") is not True:
        return False, ("転送が最後まで来たと言えない"
                       f"（todoita={shirushi.get('todoita')!r}）")
    if shirushi.get("owari") is not True:
        return False, ("原典の終わりの印が無い"
                       f"（owari={shirushi.get('owari')!r}）")
    moto = shirushi.get("moto_kensuu")
    if moto is not None and moto != kazu:
        return False, f"原典が「全{moto}件」と言っているのに、{kazu}件しか読めていない"
    return True, ""


def suehen_ka(mae: list, kieta_kagi: set):
    """**消えた店が、原典の並びの末尾に固まっているか。**

    途中で切れた取得は、**並びの後ろがまるごと落ちる。**
    本当の退店は、**ばらばらの位置**で起きる。**数を決めずに見られる。**

    **⚠ 前提**：原典の並びが回をまたいで安定していること。**まだ測っていない。**
    """
    ichi = [i for i, m in enumerate(mae) if kagi(m) in kieta_kagi]
    nokori = [i for i, m in enumerate(mae) if kagi(m) not in kieta_kagi]
    if not ichi or not nokori:
        return bool(ichi)          # 全部消えた＝末尾がまるごと落ちた形
    return min(ichi) > max(nokori)


def sabun(mae: list, ato: list, shirushi: dict = None):
    """2回ぶんから、入店と退店を出す。**完全でなければ、出さない。**

    **前が無い回は「差分未判定」。**「差分0件」でも「全部入店」でもない。
    比べる相手が無いだけで、**何も起きていないとは言えない**（統括・2026-09-21）。
    """
    d = {"hi": today(), "mae_kazu": len(mae), "ato_kazu": len(ato),
         "処理": True, "観測": False, "保存": None, "差分判定": False,
         "hatsu": False,
         "riyuu": "", "hairi": [], "taiten": [], "jotai_tsuita": [],
         "hata": [], "oboegaki": []}

    ok, why = kansei(shirushi, len(ato))
    d["観測"] = ok
    if not ok:
        d["riyuu"] = f"**観測が完全だと言えない**：{why}。**差分は出さない**"
        return d

    # **観測元が変わった回も、前が無い回と同じ。**
    # 別のページ同士を比べると、**中身と関係なく全部が入れ替わって見える**
    # （2026-09-21、観測元を替えた日に実物で出かけた）
    if shirushi and shirushi.get("moto_chigau"):
        d["hatsu"] = True
        d["riyuu"] = ("**観測元が変わった。前の回は比べる相手ではない。差分未判定。**"
                      "**別のページ同士を比べると、中身と関係なく全部が入れ替わって見える**")
        return d

    # **前が無い回。** ここを通さないと、第1観測が「全部入店」になる。
    # **大量退店の裏返し。** 2026-09-21、統括の指摘で見つかった
    if not mae:
        d["hatsu"] = True
        d["riyuu"] = ("**比べる相手が無い（第1観測）。差分未判定。**"
                      "**「差分0件」とも「変化なし」とも書かない**"
                      "——**何も起きていないとは言えない**")
        return d

    m_kagi = {kagi(m): m for m in mae}
    a_kagi = {kagi(m): m for m in ato}
    kieta = set(m_kagi) - set(a_kagi)
    fueta = set(a_kagi) - set(m_kagi)

    # **状態の表記が付いただけ**のものを、退店と数えない
    for k in sorted(set(m_kagi) & set(a_kagi)):
        _n, tsuita = jotai_wo_hazusu(a_kagi[k].get("mei") or "")
        if tsuita:
            d["jotai_tsuita"].append(k[1])

    d["taiten"] = sorted(k[1] for k in kieta)
    d["hairi"] = sorted(k[1] for k in fueta)

    # **二の矢。** 形が取得事故に似ていないか。
    #
    # **止める旗と、書くだけの旗を分ける**（2026-09-21）。
    # 「退店だけで入店0」で止めると、**ふつうの閉店が全部保留になる。**
    # 本当の閉店は、入店を伴わないほうが多い。**書くだけにする。**
    if kieta and not fueta:
        d["oboegaki"].append("**退店だけで、入店が0**（ふつうの閉店でも起きる）")
    if kieta and suehen_ka(mae, kieta):
        # **これは止める。** 途中で切れた取得は、並びの後ろがまるごと落ちる
        d["hata"].append("**消えた店が、原典の並びの末尾に固まっている**。"
                         "途中で切れた取得と同じ形")

    if d["hata"]:
        d["riyuu"] = ("観測は完全だと言えたが、**差分の形が取得事故に似ている**。"
                      "**人が見るまで差分を確定しない**")
        return d

    d["差分判定"] = True
    return d


# ────────────────────────────────────────────────────────────
# 人工の「あと」を作って、自分を壊しにいく段
# ────────────────────────────────────────────────────────────

MARU = {"todoita": True, "owari": True, "moto_kensuu": None}


def _kopi(mise):
    return [dict(m) for m in mise]


def tsukuru(mae: list):
    """**9つの人工データ**を作る。**ネットに出ない。**

    返すのは `[(番号, 名前, あと, 印, 期待)]`。
    **期待は、測る前に決めておく**（あとから決めると都合よく選べる）。
    """
    de = []

    de.append((1, "完全に同じ64店", _kopi(mae), MARU,
               {"入店": 0, "退店": 0, "差分判定": True}))

    a = _kopi(mae)
    a.pop(30)
    de.append((2, "1店だけ削除（まんなか）", a, MARU,
               {"入店": 0, "退店": 1, "差分判定": True,
                "note": "末尾ではないので止めない。**ふつうの閉店の形**"}))

    a = _kopi(mae)
    a.append({"kai": "2F", "mei": "架空ストア", "gyotai": "その他",
              "ichi": "北モール"})
    de.append((3, "架空の1店を追加", a, MARU,
               {"入店": 1, "退店": 0, "差分判定": True}))

    # 4 表記ゆれ。**揃う範囲と揃わない範囲を測る**
    #
    # **その字を実際に持つ店を選ぶ。** 2026-09-21、ここを i 番目で決め打ちしていて、
    # **3件が空振りした**（その店名に「・」「ー」「&」が無かった）。
    # 「変えたつもりで、何も変えていない」回が **○** で並ぶ。
    # **0件は、その道を1回も通っていないときにも出る**（9節）の、検査の側の形。
    yure = [("全角英数", None, lambda s: s.translate(str.maketrans(
                "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
                "ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ０１２３４５６７８９"))),
            ("空白を足す", None, lambda s: " " + s + " "),
            ("全角スペース", None, lambda s: "　" + s),
            ("大文字にする", None, lambda s: s.upper()),
            ("中黒を半角に", "・", lambda s: s.replace("・", "･")),
            # **揃えない。** ー と - は別の字。**別扱いのまま出るのが正しい**
            ("長音を負符号に", "ー", lambda s: s.replace("ー", "-")),
            ("&を全角に", "&", lambda s: s.replace("&", "＆")),
            ("カタカナを半角に", "ア", lambda s: s.translate(str.maketrans(
                "アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワン",
                "ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝ")))]
    for i, (na, iru, f) in enumerate(yure):
        # **その字を持つ店を探す。** 無ければ**未測定**にする（空振りを○にしない）
        saki = None
        for j, m in enumerate(mae):
            if iru is None or iru in (m.get("mei") or ""):
                if f(m["mei"]) != m["mei"]:
                    saki = j
                    break
        if saki is None:
            de.append((f"4-{i + 1}", f"表記ゆれ：{na}", None, MARU,
                       {"未測定": True,
                        "note": f"**64店に「{iru}」を含む店名が無い。測れない**"}))
            continue
        a = _kopi(mae)
        a[saki]["mei"] = f(a[saki]["mei"])
        # **揃えると決めた範囲だけ 0/0 を期待する。**
        # 「長音と負符号」は**揃えないと決めた**ので、**1/1 が正しい答え**。
        # ここを 0/0 と書いていて、検査が落ちた（2026-09-21）。
        # **落ちたのは検査ではなく、こちらの期待のほう。**
        soroeru = na != "長音を負符号に"
        de.append((f"4-{i + 1}", f"表記ゆれ：{na}", a, MARU,
                   {"入店": 0 if soroeru else 1, "退店": 0 if soroeru else 1,
                    "差分判定": True,
                    "note": (f"{saki + 1}番目の店で試した"
                             + ("" if soroeru else
                                "。**揃えないと決めた範囲。**"
                                "別の字なので**入店1＋退店1になるのが正しい**"))}))

    a = _kopi(mae)
    a[5]["kai"] = "3F"
    de.append((5, "同じ店を別の階へ移す", a, MARU,
               {"入店": 1, "退店": 1, "差分判定": True,
                "note": "**「移転」とは出せない。** 区画IDが無い"}))

    for i, (na, katachi) in enumerate([("改装中", "{}（改装中）"),
                                       ("一時休業", "{} 一時休業")]):
        a = _kopi(mae)
        a[7 + i]["mei"] = katachi.format(a[7 + i]["mei"])
        de.append((f"6-{i + 1}", f"状態の表記を足す：{na}", a, MARU,
                   {"入店": 0, "退店": 0, "差分判定": True}))

    a = _kopi(mae)
    a[9]["mei"] = "別ブランド"
    de.append((7, "同じ場所でブランド名だけ変える", a, MARU,
               {"入店": 1, "退店": 1, "差分判定": True,
                "note": "**「屋号替え」とは出せない。** 区画IDが無い"}))

    a = _kopi(mae)
    a[11]["yokoku"] = {"hi": "10/31", "nani": "CLOSE"}
    de.append((8, "CLOSE の予告だけ足す", a, MARU,
               {"入店": 0, "退店": 0, "差分判定": True}))

    # 9 **いちばん大事**。途中で切れた
    for nokori in (10, 30, 63):
        a = _kopi(mae)[:nokori]
        # 取得の層が「切れた」と言えている回
        de.append((f"9-{nokori}a", f"途中で切れた（{nokori}店・転送が切れたと分かる）",
                   a, {"todoita": False, "owari": False, "moto_kensuu": None},
                   {"差分判定": False, "観測": False}))
        # **印が何も無い回**（取得の層が黙っている）
        de.append((f"9-{nokori}b", f"途中で切れた（{nokori}店・印が無い）",
                   a, None, {"差分判定": False, "観測": False}))
        # **印は「完全」と言っているのに中身が欠けている回**（いちばん危ない）
        de.append((f"9-{nokori}c", f"途中で切れた（{nokori}店・印は完全と言っている）",
                   a, MARU, {"差分判定": False, "観測": True,
                             "note": "**二の矢で止める**"}))
    return de


def kensa(mae: list):
    """9つを通して、**期待と実測を並べる。** 判定は混ぜない。"""
    de = []
    for no, na, ato, shirushi, kitai in tsukuru(mae):
        if kitai.get("未測定"):
            de.append({"no": no, "na": na, "kitai": kitai,
                       "jissoku": {}, "atta": None, "hata": [], "riyuu": "",
                       "note": kitai.get("note", "")})
            continue
        d = sabun(mae, ato, shirushi)
        jissoku = {"入店": len(d["hairi"]), "退店": len(d["taiten"]),
                   "観測": d["観測"], "差分判定": d["差分判定"]}
        atta = all(jissoku.get(k) == v for k, v in kitai.items()
                   if k in jissoku)
        de.append({"no": no, "na": na, "kitai": kitai, "jissoku": jissoku,
                   "atta": atta, "hata": d["hata"], "riyuu": d["riyuu"],
                   "note": kitai.get("note", "")})
    return de


def houkoku(kekka, hiduke, moto):
    a = [].append
    a("# 差分検出器を、人工のデータで壊しにいった記録")
    a("")
    a(f"{hiduke}。**ネットに1回も出ていない。** 金庫の第1観測点だけを使った。")
    a("")
    a(f"    もとの店数  {moto} 店（本館2F・人が画面で確かめた実物から正規化）")
    a("")
    a("**期待は、測る前に決めた。** あとから決めると、都合のいい答えを選べる。")
    a("")
    a("| # | 何を変えたか | 期待 | 実測 | 合ったか | 覚書 |")
    a("|---|---|---|---|---|---|")
    for d in kekka:
        ki = "／".join(f"{k}={v}" for k, v in d["kitai"].items() if k != "note")
        if not d["jissoku"]:
            a(f"| {d['no']} | {d['na']} | — | **未測定** | — | {d['note']} |")
            continue
        ji = (f"入店={d['jissoku']['入店']}／退店={d['jissoku']['退店']}"
              f"／観測={d['jissoku']['観測']}／差分判定={d['jissoku']['差分判定']}")
        a(f"| {d['no']} | {d['na']} | {ki} | {ji} "
          f"| {'○' if d['atta'] else '**×**'} | {d['note']} |")
    a("")
    chigau = [d for d in kekka if d["atta"] is False]
    mi = [d for d in kekka if d["atta"] is None]
    a(f"合った {len(kekka) - len(chigau) - len(mi)} / {len(kekka) - len(mi)}"
      + (f"（ほかに**未測定 {len(mi)}**）" if mi else ""))
    a("")
    if chigau:
        a("## 合わなかったもの")
        a("")
        for d in chigau:
            a(f"- **{d['no']} {d['na']}**：期待 {d['kitai']} / 実測 {d['jissoku']}")
        a("")
    a("## 止めた理由")
    a("")
    for d in kekka:
        if d["riyuu"]:
            a(f"- **{d['no']}**：{d['riyuu']}")
            for h in d["hata"]:
                a(f"    - {h}")
    a("")
    return "\n".join(a.__self__)


def main(argv=None):
    p = argparse.ArgumentParser(description="差分検出器を人工データで壊す。取りに行かない")
    p.add_argument("--moto", default="inbox/floor/gardens/2026-09-21-2F-seiki.json")
    p.add_argument("--kai", default="2F")
    a = p.parse_args(argv)

    michi = HERE / a.moto
    if not michi.exists():
        print(f"もとのデータが無い: {michi}", file=sys.stderr)
        print("**金庫から持ってくる**（inbox/floor/gardens/）", file=sys.stderr)
        return 1
    nama = json.loads(michi.read_text(encoding="utf-8"))
    mae = [dict(m, kai=a.kai) for m in nama["mise"]]

    kekka = kensa(mae)
    KIROKU.parent.mkdir(parents=True, exist_ok=True)
    KIROKU.write_text(houkoku(kekka, today(), len(mae)), encoding="utf-8")
    for d in kekka:
        shirushi = {True: "○", False: "×", None: "－"}[d["atta"]]
        print(f"{shirushi} {str(d['no']):8} {d['na']}  {d['note']}")
    chigau = sum(1 for d in kekka if d["atta"] is False)
    mi = sum(1 for d in kekka if d["atta"] is None)
    print(f"\n合った {len(kekka) - chigau - mi} / {len(kekka) - mi}"
          + (f"（未測定 {mi}）" if mi else ""))
    print(f"{KIROKU} に書いた")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
