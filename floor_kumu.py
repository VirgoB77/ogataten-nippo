#!/usr/bin/env python3
"""渡された1枚から、**区画の表を組む**段。**取りに行かない。**

## この段がやること

    ① 型を確かめる   抽出した結果が、決めた形を守っているか
    ② 表を出す       **人が答え合わせするための表**
    ③ 数える         合っていた数・直した数・**作り出した数**

**抽出そのものは、この箱の外でやる**（Claude が読む）。
ここは**型と数**だけを見る。**読めたかどうかを、読んだ本人が採点しない**ため。

## 入り口は2つ。**どちらから来たかを記録に書く**

    人が渡した      運営者がブラウザで1枚開いて渡した
    この箱が取った  `floor_get.py` が `inbox/floor/<id>/<日付>.html` に置いた

**2026-09-21 の1枚目は「人が渡した」。** 取りに行く段はまだ人が規約を読んでいない。

## 数え方を、先に決めておく

あとから決めると、**都合のいい数え方を選べてしまう。**

    合っていた   原典にあり、こちらも同じ値を出した
    直した       原典にあり、こちらも出したが、値が違った
    **落とした** 原典にあるのに、こちらが出さなかった
    **作った**   **原典に無いのに、こちらが出した**

**「作った」は別に数える。** ほかの3つは足し引きで気づけるが、
これだけは**もっともらしい顔で混ざる**ので、割合ではなく実数で出す。

    店名の精度 = 合っていた ÷（合っていた + 直した + 落とした）
    人の手間   =（直した + 落とした + 作った）÷ 出した行数

**分母を書かずに割合を出さない**（3.5）。

## トークン数は**測っていない**

この箱は外に出られないので、数えてくれる相手に聞けない（9節）。
**文字数とバイト数は数えた。トークン数は数えていないので、書かない。**
目安の係数を掛けて「およそ◯トークン」と書くのは、**測ったことにならない。**
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

# 区画1つに要る欄。**足りないものがあれば、埋めずに落とす**
RAN = ("kai", "mise", "jotai")
# 状態。**「分からない」を必ず持つ。** 空区画かどうか読めない相手がいる
JOTAI = ("営業中", "空区画", "準備中", "分からない")
# **予告。** 地図の上に赤帯で載っている（2026-09-21 に拡大して確かめた）。
#
#     LEPSIM        の区画に  「9/18 OPEN」
#     薬 マツモトキヨシ の区画に  「9/4 RENEWAL OPEN」
#
# **赤帯は、直上の店名の区画のもの。** 帰属のルールはこれ。
#
# **これは差分より先に取れる。** 1枚目と2枚目を比べなくても、
# 「次に変わる区画」がその日のうちに分かる。**差分の答え合わせにも使える**
# ——予告どおりに変わったか。**予告が外れることもあるので、別の欄にする。**
YOKOKU = ("OPEN", "RENEWAL OPEN", "CLOSE")
MOTO = ("人が渡した", "この箱が取った")
# **渡され方。** 文字と画面の写真では、大きさの測り方が違う。
# 2026-09-21 の1枚目は画面の写真だった。**文字数で測ろうとして、測れなかった。**
KATACHI = ("文字", "画面の写真")
# **どこまで読んだか。** 一部だけ読んだものを、全部読んだ精度として数えない。
# 2026-09-21、1枚目の1Fは**赤帯（予告）だけ**を読んだ。全区画は読んでいない。
# ここを欄にしておかないと、**分母が小さいまま「精度◯%」が出てしまう。**
HANI = ("全部", "予告だけ")


def kensa(d: dict):
    """型を確かめる。**直さない。落ちたところを全部返す。**"""
    warui = []
    for r in ("id", "mei", "mita_hi", "moto", "kukaku"):
        if r not in d:
            warui.append(f"欄が無い: {r}")
    moto = d.get("moto") or {}
    if moto.get("donoyouni") not in MOTO:
        warui.append(f"moto.donoyouni が {MOTO} のどれでもない: {moto.get('donoyouni')!r}")
    if not isinstance(moto.get("bytes"), int):
        warui.append("moto.bytes が数でない（**数えていないなら数える**）")
    if moto.get("hani") not in HANI:
        warui.append(f"moto.hani が {HANI} のどれでもない: {moto.get('hani')!r}")
    if moto.get("katachi") not in KATACHI:
        warui.append(f"moto.katachi が {KATACHI} のどれでもない: {moto.get('katachi')!r}")
    elif moto["katachi"] == "文字":
        if not isinstance(moto.get("moji"), int):
            warui.append("文字で渡されたのに moto.moji が数でない")
    else:
        # **画面の写真は文字数で測れない。** 枚数と画素で測る。
        # ここで moji を required にすると、**測れないものに数を入れることになる**
        if not isinstance(moto.get("maisu"), int):
            warui.append("画面の写真なのに moto.maisu（枚数）が数でない")
        if moto.get("moji") is not None:
            warui.append("画面の写真に moji（文字数）が入っている。**測れないものを測ったことにしない**")
    for i, k in enumerate(d.get("kukaku") or [], 1):
        for r in RAN:
            if not k.get(r):
                warui.append(f"{i}行目に {r} が無い")
        if k.get("jotai") and k["jotai"] not in JOTAI:
            warui.append(f"{i}行目の jotai が {JOTAI} のどれでもない: {k['jotai']!r}")
        y = k.get("yokoku")
        if y is not None:
            if y.get("nani") not in YOKOKU:
                warui.append(f"{i}行目の yokoku.nani が {YOKOKU} のどれでもない: "
                             f"{y.get('nani')!r}")
            # **日は文字のまま持つ。** 地図に年が書いていないので、
            # こちらで年を足すと**作文になる**（「9/18」は今年とは限らない）
            if not isinstance(y.get("hi"), str) or not y["hi"]:
                warui.append(f"{i}行目の yokoku.hi が文字でない（**年を足さない**）")
    if not d.get("kukaku"):
        warui.append("区画が0行。**「無い」ではなく「読めなかった」かもしれない**")
    return warui


def hyou(d: dict):
    """**人が答え合わせするための表。** 空の欄は人が埋める。"""
    a = [].append
    moto = d["moto"]
    a(f"# {d['mei']} のフロアマップ（{d['mita_hi']}）")
    a("")
    a(f"どこから来たか：**{moto['donoyouni']}**")
    if moto.get("url"):
        a(f"元：{moto['url']}")
    if moto["katachi"] == "文字":
        ookisa = f"{moto['moji']:,} 文字 / {moto['bytes']:,} バイト"
    else:
        ookisa = (f"画面の写真 {moto['maisu']} 枚 / {moto['bytes']:,} バイト"
                  + (f" / {moto['gaso']}" if moto.get("gaso") else ""))
    a(f"渡され方：**{moto['katachi']}**")
    a(f"大きさ：{ookisa}（**トークン数は数えていない**）")
    a(f"出した行数：**{len(d['kukaku'])}**")
    a("")
    a("## 答え合わせ")
    a("")
    a("**合っていたら ○。違ったら「正しい値」に書く。**")
    a("**ここに出ていない店が原典にあれば、いちばん下に足す（落とした分）。**")
    a("")
    a("| # | 階 | 区画 | 店名 | 業態 | 状態 | 予告 | 合ってる？ | 正しい値 |")
    a("|---|---|---|---|---|---|---|---|---|")
    for i, k in enumerate(d["kukaku"], 1):
        y = k.get("yokoku")
        a(f"| {i} | {k.get('kai') or ''} | {k.get('kukaku_no') or ''} "
          f"| {k.get('mise') or ''} | {k.get('gyotai') or ''} | {k.get('jotai') or ''} "
          f"| {(y['hi'] + ' ' + y['nani']) if y else ''} |  |  |")
    a("")
    yoko = [(i, k) for i, k in enumerate(d["kukaku"], 1) if k.get("yokoku")]
    if yoko:
        a(f"**予告のある区画 {len(yoko)}。** 地図に赤帯で載っていた分。"
          "**差分を待たずに「次に変わる区画」が分かる。**")
        a("")
        for i, k in yoko:
            y = k["yokoku"]
            a(f"- {i}. {k['mise']} … **{y['hi']} {y['nani']}**")
        a("")
        a("**年は書いていないので足していない。**「9/18」は今年とは限らない。")
        a("")
    else:
        a("予告のある区画は0。**「無い」ではなく「読めなかった」かもしれない。**")
        a("")
    a("")
    a("**落とした分（原典にあるのに、上に無い店）**")
    a("")
    a("| 階 | 店名 | 状態 |")
    a("|---|---|---|")
    a("|  |  |  |")
    a("")
    return "\n".join(a.__self__)


def kazoeru(d: dict, awase: dict):
    """合っていた・直した・落とした・**作った**を数える。

    `awase` の形：
        {"chigau": [{"gyo": 3, "ran": "mise", "tadashii": "◯◯"}],
         "otoshita": [{"kai": "2F", "mise": "◯◯"}],
         "tsukutta": [5, 9]}          ← 原典に無い行の番号
    """
    if d["moto"].get("hani") != "全部":
        # **一部だけ読んだものの精度は、精度ではない。**
        # 分母が「原典にある数」ではなく「こちらが見た範囲」になってしまう
        raise ValueError(
            f"読んだ範囲が「{d['moto'].get('hani')}」。**全部読んでいないので数えない**")
    zen = len(d["kukaku"])
    # **一部だけ答え合わせしたものを、全体の精度として出さない。**
    # 2026-09-21、70行のうち**5行だけ**人が確かめた。そのまま割ると、
    # **怪しいと思った行ばかり選んで確かめた分母**で精度が出てしまう。
    # `mita` は人が実際に確かめた行番号。**入っていなければ全部を確かめたとみなす。**
    mita = awase.get("mita")
    zenbu = mita is None or len(set(mita)) >= zen
    han = set(range(1, zen + 1)) if zenbu else set(mita)

    tsukutta = sorted(set(awase.get("tsukutta") or []) & han)
    naoshita_gyo = sorted({c["gyo"] for c in (awase.get("chigau") or [])
                           if c["gyo"] in han and c["gyo"] not in tsukutta})
    dashita = len(han)
    # **作った行は「原典にある」の数に入れない。** 分母を膨らませない
    atteta = dashita - len(tsukutta) - len(naoshita_gyo)

    if not zenbu:
        # **「落とした」は範囲で切れない。** 原典を通して見ないと数えられない
        return {
            "全部を確かめたか": False,
            "出した行数": zen,
            "確かめた行数": dashita,
            "合っていた": atteta,
            "直した": len(naoshita_gyo),
            "落とした": None,          # **確かめていない。0ではない**
            "作った": len(tsukutta),
            "原典にある数（分母）": None,
            "店名の精度": None,        # **出さない**
            "人の手間": None,
            "確かめた範囲での合致率": (atteta / dashita) if dashita else None,
            "直した欄の数": len([c for c in (awase.get("chigau") or [])
                              if c["gyo"] in han]),
        }

    otoshita = len(awase.get("otoshita") or [])
    bunbo = atteta + len(naoshita_gyo) + otoshita
    seido = (atteta / bunbo) if bunbo else None
    tema = ((len(naoshita_gyo) + otoshita + len(tsukutta)) / dashita) if dashita else None
    return {
        "全部を確かめたか": True,
        "出した行数": dashita,
        "確かめた行数": dashita,
        "合っていた": atteta,
        "直した": len(naoshita_gyo),
        "落とした": otoshita,
        "作った": len(tsukutta),
        "原典にある数（分母）": bunbo,
        "店名の精度": seido,
        "人の手間": tema,
        "直した欄の数": len(awase.get("chigau") or []),
    }


def kazu_no_hyou(d, n):
    a = [].append
    a(f"## 数えた（{d['mei']}・{d['mita_hi']}）")
    a("")
    a("| | 数 |")
    a("|---|---|")
    for k in ("出した行数", "確かめた行数", "合っていた", "直した", "落とした", "作った",
              "原典にある数（分母）", "直した欄の数"):
        a(f"| {k} | {'**確かめていない**' if n[k] is None else n[k]} |")
    a("")
    if not n["全部を確かめたか"]:
        r = n["確かめた範囲での合致率"]
        a(f"**全部は確かめていない。**{n['出した行数']} 行のうち {n['確かめた行数']} 行。")
        a("")
        a("**だから精度は出さない。** 確かめる行を選ぶのは人で、"
          "**怪しいと思った行から確かめる**ので、その分母で割ると精度が低く出る。")
        a("**逆に自信のある行から確かめれば高く出る。** どちらも精度ではない。")
        a("")
        if r is not None:
            a(f"確かめた範囲での合致率 {r:.0%}"
              f"（{n['合っていた']} ÷ {n['確かめた行数']}）**——これは精度ではない**")
        a("")
        return "\n".join(a.__self__)
    if n["店名の精度"] is None:
        a("**店名の精度：分からない**（原典にある数が0。**0件は「無い」ではない**）")
    else:
        a(f"**店名の精度 {n['店名の精度']:.1%}**"
          f"（{n['合っていた']} ÷ {n['原典にある数（分母）']}）")
    if n["人の手間"] is not None:
        a(f"**人の手間 {n['人の手間']:.1%}**"
          f"（{n['直した'] + n['落とした'] + n['作った']} ÷ {n['出した行数']}）")
    a("")
    if n["作った"]:
        a(f"**原典に無いものを {n['作った']} 行つくった。**"
          "割合ではなく実数で見る。もっともらしい顔で混ざる")
    else:
        a("原典に無いものは作らなかった（この1枚では）")
    a("")
    return "\n".join(a.__self__)


def main(argv=None):
    p = argparse.ArgumentParser(description="渡された1枚から区画の表を組む。取りに行かない")
    p.add_argument("chushutsu", help="抽出した結果の JSON")
    p.add_argument("--awase", help="答え合わせの JSON。あれば数える")
    p.add_argument("--saki", help="書き出す先（既定は標準出力）")
    a = p.parse_args(argv)

    d = json.loads(Path(a.chushutsu).read_text(encoding="utf-8"))
    warui = kensa(d)
    if warui:
        print("型が守られていない：", file=sys.stderr)
        for w in warui:
            print("  - " + w, file=sys.stderr)
        return 1

    de = hyou(d)
    if a.awase:
        n = kazoeru(d, json.loads(Path(a.awase).read_text(encoding="utf-8")))
        de += "\n" + kazu_no_hyou(d, n)
    if a.saki:
        Path(a.saki).write_text(de, encoding="utf-8")
        print(f"{a.saki} に書いた")
    else:
        print(de)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
