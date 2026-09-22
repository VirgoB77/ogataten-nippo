#!/usr/bin/env python3
"""**箱の履歴**——施設そのものが、いつ、どう変わったかを並べる段。

ここは**取りに行かない。** 手元の `data/all.json` を読むだけ。
webに1回も行かないので、相手のサーバーも Claude の枠も使わない。

## なぜ「箱」なのか

商業施設のテナント履歴は、既に強いサービスがある（2026-09-20・外の目）。
**同じものを作ると負ける。過去は買えないので、追いつけない。**

こちらが持っているのは**主語が違うもの。**

    向こう   **ショップ**が主語。見に行って、開いた／閉じたを確認する
    こちら   **設置者と箱**が主語。届出は**工事より前**に出る

店舗面積・駐車場台数・営業時間・閉店時刻は、**向こうが持っていない。**
そして**廃止届は「これから閉まる」の記録**で、見に行く調べ方では先回りできない。

## 出来事の形

**点では持てない日付を、点で持たない**（9節）。

届出Aで値がα、届出Bで値がβなら、**変わったのはAとBのあいだ。**
届出日そのものは点だが、**値が動いた日は区間でしか分からない。**

    ❌ 2021-07-05 に駐車場が減った
    ✅ 2019-03-12 と 2021-07-05 のあいだに、駐車場の届出値が変わった

## **届出された値**であって、**そうなった値**ではない

2026-09-21、外の目の指摘。**こちらが踏んでいた。**

届出は**工事より前**に出る。だから**早い**のが値打ちなのだが、
**同じ理由で「まだ起きていない」。** 予定が変わることも、撤回されることもある。

    ❌ 2021年に駐車場が95台に**なった**
    ✅ 2021年までに、駐車場を95台に**する届出が出た**

**「早い」と「確かめた」は両立しない。** 早いものは、まだ確かめられていない。
ここを混ぜると、**見に行って確認する調べ方より正確だ**と名乗ることになる。
そちらは遅いかわりに**起きたことを見ている**（ルール⑥）。

## 「変わっていない」と「2回見ていない」を混ぜない

様式の回によって埋まる欄が違う（9節）。
**その欄が2回以上埋まっている施設だけ**が、比較できる。
埋まっていない施設は「変わっていない」ではなく **「見ていない」。**

## 施設名を寄せること

同じ施設が別の名前で出てくる。寄せないと**出来事が減る方向に間違える。**
寄せ方はここに1か所だけ置く（**拾い方を散らさない**・9節）。

**寄せは下限を作る道具で、正解ではない。** 寄せ足りなければ出来事は減る。
**増える方向には間違えない**ので、数字は必ず「下限」と名乗る。

## 寄せの向きが、欄によって**逆**になる

ここが今日いちばん間違えたところ（2026-09-20）。

    **施設名**を寄せない   → 同じ施設が別扱いになる → **出来事が減る**（下限）
    **事業者名**を寄せない → 書き方の違いが出来事になる → **出来事が増える**（上限）

**2つを混ぜて1つの数字にすると、両方向に間違えた数字になる。**
なので**箱（数値）と中身（名前）を、最初から分けて数える。**

そして名前のほうは、寄せても**「変わった」とは言えない。**
商号変更・合併・持株会社化は名前そのものが変わるので、
**法人番号が無いうちは「表記が変わった」までしか言えない**（`privacy.same_corp` の注）。

## 承継だけは、**名前ではなく番号でつなぐ**

2026-09-21。「別の法人へ交代したか」を聞かれて数えたら、
**承継の届出は198件あるのに、誰から誰へは19件しか言えなかった。**

**理由は「取れていない」ではなかった。**
**元の表に「前の設置者」の列が無い。** 承継の行に載っているのは**そのときの設置者**だけ。

**前は、前の届出にしか無い。** つなぐ鍵は2つある。

    **施設名を寄せる**    ← どの出どころでも使える。**表記ゆれで外れる**
    **店舗番号**          ← 1つの出どころにしか無い。**外れない**

**承継のように「前と後」が要るところは、番号を使う。**
番号でつないだら、**19件 → 104件**になった。

**ただし番号は、その出どころの中でしか通じない。**
だから**施設名の寄せ方は置き換えない。** 承継のところだけ番号を使う。
**片方に寄せると、番号の無い出どころが丸ごと落ちる。**

## 出すもの

    inbox/hako-rireki/hako-rireki.md    人が読む報告
    inbox/hako-rireki/hako-rireki.json  出来事の一覧

**`inbox/` は `.gitignore`。** `data/ref/` に置くと**リポジトリに入る＝URLで読める**ので、
そこに置いて「まだ公開していない」と書くと**名乗りが嘘になる**（ルール⑥）。

**作り方は残す。作ったものは残さない。** `data/all.json` から何度でも作り直せる。

伏せる線を決めていないので、決める前に出さない（9節・止まる側）。
とくに**「変わった区間」はこちらが観測して作ったもの**で、
役所が出した写しではない。**出し方は、出すと決めてから決める。**
"""
from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from common import privacy

HERE = Path(__file__).resolve().parent
MOTO = HERE / "data" / "all.json"
# **`inbox/` に出す。** `data/ref/` はリポジトリに入る＝**URLで読める。**
# そこに置いて「まだ公開していない」と書くと、**名乗りが嘘になる**（ルール⑥）。
# 2026-09-20、危うくそう書くところだった。
SAKI = HERE / "inbox" / "hako-rireki"
SAKI_MD = SAKI / "hako-rireki.md"
SAKI_JSON = SAKI / "hako-rireki.json"

# **箱の欄。** テナント（誰が入っているか）ではなく、施設そのものの値。
HAKO = (
    ("area_m2", "店舗面積", "m2"),
    ("floor_area_m2", "延床面積", "m2"),
    ("parking", "駐車場", "台"),
    ("bicycle", "駐輪場", "台"),
    ("open_time", "開店時刻", ""),
    ("close_time", "閉店時刻", ""),
)
# **中身の欄。** 箱と分けて数える（主語が違う）
NAKAMI = (("retailer", "小売業者", ""), ("operator", "設置者", ""))

_KAKKO = re.compile(r"[（(\[【].*?[）)\]】]")
_KIGOU = re.compile(r"[\s\-‐―ー・,，.．'\"’”]")


def yoseru(name: str) -> str:
    """施設名を寄せる。**寄せ方はここ1か所だけ。**

    **法人格の一覧は自分で持たない。** `privacy.corp_core` が正本。
    2026-09-20、ここに2本目を書いていた。**同じ知識が2か所にあると、
    片方に足した日に、もう片方が黙る。**
    """
    if not name:
        return ""
    s = unicodedata.normalize("NFKC", name).replace("　", " ")
    s = _KAKKO.sub("", s)
    s = privacy.corp_core(s)
    s = _KIGOU.sub("", s)
    return s.lower()


def atai(rec: dict, ran: str):
    """その届出で、その欄が埋まっているか。**空は「見ていない」。**"""
    if ran in ("retailer", "operator"):
        v = rec.get(f"{ran}_display") or rec.get(ran)
    else:
        v = rec.get(ran)
    if v in (None, "", 0):
        return None
    return str(v).strip() or None


def hi(rec: dict) -> str:
    """その届出の日。**無ければ空。並べるときに後ろへ回す。**"""
    return rec.get("notified_on") or rec.get("event_on") or ""


def dekigoto(recs):
    """出来事を拾う。**値が動いた区間だけ**を返す。"""
    yado = defaultdict(list)
    for r in recs:
        na = yoseru((r.get("store") or "").strip())
        if na:
            yado[na].append(r)

    out = []
    for na, rows in yado.items():
        rows = sorted(rows, key=lambda r: (hi(r) == "", hi(r)))
        mise = (rows[-1].get("store") or "").strip()
        for ran, mei, tani in HAKO + NAKAMI:
            mita = [(hi(r), atai(r, ran)) for r in rows]
            mita = [(d, v) for d, v in mita if v is not None and d]
            if len(mita) < 2:
                continue  # **2回見ていない。「変わっていない」ではない**
            namae = ran in ("retailer", "operator")
            for (d1, v1), (d2, v2) in zip(mita, mita[1:]):
                if v1 == v2:
                    continue
                # **名前は、書き方の違いだけのことがある。**
                # `same_corp` は法人格と全角半角を吸う。中黒や異体字は吸えない
                # ので、ここで消えなかったものも「変わった」とは言えない。
                if namae and privacy.same_corp(v1, v2):
                    continue
                out.append(
                    {
                        "store": mise,
                        "store_key": na,
                        "field": ran,
                        "field_label": mei,
                        "nanori": "届出の値",
                        "unit": tani,
                        "kind": "箱" if any(ran == k for k, _, _ in HAKO) else "中身",
                        "note": "" if any(ran == k for k, _, _ in HAKO) else "表記が変わっただけのことがある",
                        "from": v1,
                        "to": v2,
                        "after": d1,   # **この日より後**
                        "before": d2,  # **この日までに**
                    }
                )

    # 廃止届は、それだけで1つの出来事（**閉店の予告**）
    for r in recs:
        # **`kubun_raw` で数えない。** その欄は一部の届出にしか無く、
        # **194件のうち49件しか当たらなかった**（2026-09-21）。`kind` が本物
        if (r.get("kind") or "") == "廃止" and hi(r):
            out.append(
                {
                    "store": (r.get("store") or "").strip(),
                    "store_key": yoseru((r.get("store") or "").strip()),
                    "field": "haishi",
                    "field_label": "廃止届",
                    "unit": "",
                    "kind": "廃止",
                    "from": "",
                    "to": "",
                    "after": hi(r),
                    "before": hi(r),
                }
            )
    return sorted(out, key=lambda e: (e["before"], e["store"], e["field"]))


def shoukei(recs):
    """承継の届出を、**店舗番号で前の届出につなぐ。**

    **施設名では寄せない。** ここは「前と後」が要るので、**外れない鍵を使う。**
    番号はその出どころの中でしか通じないので、**(出どころ, 番号) で持つ。**

    **「誰から誰へ」と言えるのは、法人→法人で、書き方の違いでないときだけ。**
    それでも**商号変更・合併・持株会社化は見分けられない**（`privacy.same_corp` の注）。
    言えるのは「**設置者の名前が変わった**」まで。
    """
    ban = defaultdict(list)
    for r in recs:
        no = (r.get("store_no") or "").strip()
        if no and hi(r):
            ban[(r.get("source"), no)].append(r)
    for k in ban:
        ban[k].sort(key=hi)

    out = []
    for r in recs:
        if (r.get("kind") or "") != "承継":
            continue
        no = (r.get("store_no") or "").strip()
        if not no:
            continue  # **番号が無い出どころ。「無い」ではなく「つなげない」**
        rows = ban[(r.get("source"), no)]
        i = rows.index(r) if r in rows else -1
        mae = None
        for p2 in reversed(rows[:i] if i > 0 else []):
            if atai(p2, "operator"):
                mae = p2
                break
        ima = atai(r, "operator")
        if not (mae and ima):
            continue
        zen = atai(mae, "operator")
        if zen == ima:
            continue
        hojin = (mae.get("operator_kind") == "corp"
                 and r.get("operator_kind") == "corp")
        out.append({
            "store": (r.get("store") or "").strip(),
            "after": hi(mae), "before": hi(r),
            "from": zen, "to": ima,
            "hojin": hojin,
            # **書き方の違いは落とす。それでも「交代した」とは言えない**
            "kakikata": bool(hojin and privacy.same_corp(zen, ima)),
        })
    return sorted(out, key=lambda e: e["before"])


def mireru(recs):
    """欄ごとに、**比較できる施設の数**。分母を間違えないために先に出す。"""
    yado = defaultdict(list)
    for r in recs:
        na = yoseru((r.get("store") or "").strip())
        if na:
            yado[na].append(r)
    d = {}
    for ran, mei, _ in HAKO + NAKAMI:
        n = sum(
            1
            for rows in yado.values()
            if sum(1 for r in rows if atai(r, ran) is not None and hi(r)) >= 2
        )
        d[ran] = (mei, n)
    return d, len(yado)


def _kazu(e):
    """その出来事が、数で比べられるか。**比べられないものを0に数えない。**"""
    try:
        float(e["from"]), float(e["to"])
    except (ValueError, TypeError):
        return False
    return True


def houkoku(recs, ev, miru, yado_kazu) -> str:
    kumi = Counter(e["field_label"] for e in ev)
    tana = Counter(e["before"][:4] for e in ev if e["before"])
    hako_n = len({e["store_key"] for e in ev if e["kind"] == "箱"})
    naka_n = len({e["store_key"] for e in ev if e["kind"] == "中身"})

    L = []
    a = L.append
    a("# 箱の履歴（**まだ公開していない**）")
    a("")
    a("`hako_rireki.py` が作った。**webに1回も行っていない。**")
    a("手元の `data/all.json` を読んで数えただけ。")
    a("")
    a("**数字は全部「下限」。** 施設名を寄せきれていなければ、出来事は減る方向に出る。")
    a("**増える方向には間違えない。**")
    a("")
    a("## 分母（**ここを間違えると、答えが倍ちがう**）")
    a("")
    a(f"    届出          {len(recs)} 件")
    a(f"    施設（寄せた） {yado_kazu} 棟")
    a("")
    a("**欄ごとに、比較できる施設の数が違う。** 様式の回によって埋まる欄が違うので、")
    a("**その欄が2回以上埋まっている施設だけ**が「変わったか」を言える。")
    a("")
    a("    欄            2回以上見た施設")
    for ran, mei, _ in HAKO + NAKAMI:
        a(f"    {mei:<12} {miru[ran][1]} 棟")
    a("")
    a("> **「変わっていない」と「2回見ていない」は、同じ顔で出てくる。**")
    a("")
    a("## 出来事の数（**箱と中身を混ぜない**）")
    a("")
    a("**寄せの向きが、欄によって逆になる。** 混ぜて1つの数字にすると、")
    a("**両方向に間違えた数字**になる。")
    a("")
    hako_ev = [e for e in ev if e["kind"] == "箱"]
    naka_ev = [e for e in ev if e["kind"] == "中身"]
    hai_ev = [e for e in ev if e["kind"] == "廃止"]
    a(f"    **箱**（数値）    {len(hako_ev)} 件 / {hako_n} 棟    ← **下限**。寄せ足りないと減る")
    a(f"    **中身**（名前）  {len(naka_ev)} 件 / {naka_n} 棟    ← **上限**。書き方の違いが混じる")
    a(f"    **廃止届**        {len(hai_ev)} 件               ← 区分そのものなので、ぶれない")
    a("")
    for mei, n in kumi.most_common():
        a(f"    {mei:<12} {n} 件")
    a("")
    a("### 箱のほうの、差の大きさ")
    a("")
    chiisai = []
    for e in hako_ev:
        try:
            x, y = float(e["from"]), float(e["to"])
        except ValueError:
            continue
        if x and abs(y - x) / x < 0.01:
            chiisai.append(e)
    a(f"    数で比べられた出来事            {len([e for e in hako_ev if _kazu(e)])} 件")
    a(f"    **うち差が1%未満**              {len(chiisai)} 件  ← **丸めかもしれない**")
    a("")
    a("**落としていない。** どれが丸めでどれが本物かは、こちらでは決められない。")
    a("**選り分けると、こちらが判断したことになる**（3.3）。数えて、そう書くだけ。")
    a("")
    a("### 中身のほうは、「変わった」と言えない")
    a("")
    a("`privacy.same_corp` で書き方の違いを落としたが、**中黒・異体字・「ほか」の有無**は")
    a("落ちない。そのうえ、**落ちたとしても言えるのは「表記が変わった」まで。**")
    a("")
    a("    商号変更・合併・持株会社化は、**名前そのものが変わる**")
    a("    見分けるには法人番号が要る（`privacy.same_corp` の注）")
    a("")
    a("**なので中身の欄は、いまの形では商品にならない。**")
    a("**箱の欄と廃止届が、いま手元にあるもの。**")
    a("")
    a("## **届出された値**であって、**そうなった値**ではない")
    a("")
    a("**届出は工事より前に出る。** だから早いが、**同じ理由でまだ起きていない。**")
    a("予定が変わることも、撤回されることもある。")
    a("")
    a("    ❌ 駐車場が95台に**なった**")
    a("    ✅ 駐車場を95台に**する届出が出た**")
    a("")
    a("**「早い」と「確かめた」は両立しない。** 見に行って確認する調べ方は遅いが、")
    a("**起きたことを見ている。** こちらは早いが、**まだ確かめていない。**")
    a("")
    a("**撤回や変更の届出がこの中にどれだけあるかは、数えていない。**")
    a("")
    a("## 承継（**番号でつないだ。名前では寄せていない**）")
    a("")
    sk = shoukei(recs)
    ieru = [e for e in sk if e["hojin"] and not e["kakikata"]]
    a(f"    承継の届出                  {sum(1 for r in recs if r.get('kind') == '承継')} 件")
    a(f"    **前の届出とつながった      {len(sk)} 件**")
    a(f"    うち法人→法人              {sum(1 for e in sk if e['hojin'])} 件")
    a(f"    うち書き方だけ              {sum(1 for e in sk if e['kakikata'])} 件")
    a(f"    **→ 名前が変わったと言える  {len(ieru)} 件**")
    a("")
    a("**「交代した」とは言えない。** 商号変更・合併・持株会社化は見分けられない。")
    a("言えるのは **「設置者の名前が変わった」** まで（法人番号が要る）。")
    a("")
    a("**番号が無い出どころは、ここに出てこない。**")
    a("**「無い」ではなく「つなげない」。**")
    a("")
    a("## 年ごと（**変わった区間の、後ろの端の年**）")
    a("")
    a("**前の端の年ではない。** 変わったのは2つの届出のあいだなので、")
    a("**年をまたいでいることがある。**")
    a("")
    for y in sorted(tana):
        a(f"    {y}  {tana[y]} 件")
    a("")
    a("## 出来事（新しい順に50件）")
    a("")
    a("**日付は区間。** 「この日より後、この日までに」という意味。")
    a("毎日1回しか見ていないのと同じ理由で、**点では持てない**。")
    a("")
    for e in list(reversed(ev))[:50]:
        if e["kind"] == "廃止":
            a(f"- {e['before']}　**{e['store']}**　廃止**届**（閉店したかは見ていない）")
        else:
            t = e["unit"]
            sa = ""
            if _kazu(e):
                x, y = float(e["from"]), float(e["to"])
                if x:
                    sa = f"（{(y - x) / x * 100:+.0f}%）"
            shirushi = "" if e["kind"] == "箱" else "　※表記の違いかもしれない"
            a(
                f"- {e['after']} 〜 {e['before']}　**{e['store']}**　"
                f"{e['field_label']}の**届出値** {e['from']}{t} → {e['to']}{t}{sa}{shirushi}"
            )
    a("")
    a("---")
    a("")
    a("**この一覧は `inbox/` にある。** `inbox/` は `.gitignore` なので、")
    a("**リポジトリにも site にも入っていない。**")
    a("")
    a("`data/ref/` に置くと**リポジトリに入る＝URLで読める。**")
    a("そこに置いて「公開していない」と書くと、**名乗りが嘘になる**（ルール⑥）。")
    a("")
    a("**中身の値そのものは、全部もう公開している**（施設名・面積・駐車場・事業者名）。")
    a("伏せているのは**並べ方**のほう——「いつ、どう変わったか」は")
    a("**こちらが観測して作ったもの**で、役所が出した写しではない。")
    return "\n".join(L) + "\n"


def main():
    SAKI.mkdir(parents=True, exist_ok=True)
    recs = json.loads(MOTO.read_text(encoding="utf-8"))
    ev = dekigoto(recs)
    miru, yado_kazu = mireru(recs)
    SAKI_JSON.write_text(
        json.dumps(ev, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    SAKI_MD.write_text(houkoku(recs, ev, miru, yado_kazu), encoding="utf-8")
    print(f"出来事 {len(ev)} 件 / 施設（寄せた）{yado_kazu} 棟")
    print(f"  {SAKI_MD}")
    print(f"  {SAKI_JSON}")


if __name__ == "__main__":
    main()
