#!/usr/bin/env python3
"""住所が**どこまで書かれているか**を数えて、記録に残す。

地図に点を置けるかどうかは、こちらの腕ではなく**役所が何を書いたか**で決まる。
先にそれを数える。**測る前に作らない**（共通仕様9節）。

2026-09-19、中島さんの——

> 町丁目レベルはさすがにだめにゃ。開店と閉店は場所を特定しても問題ないはずにゃ。

そのとおりで、**大型店は事業者**なので位置を出すことに問題は無い（3.1）。
だが**出せる細かさは住所しだい**で、こちらでは増やせない。
町丁目の真ん中に点を置くのは、**届出が言っていない場所を言う**ことになる（3.5）。

印は4つに分かれる。**混ぜない。**

    …番…号     住居表示。位置参照情報の街区レベルで番まで当たる
    …番地…     地番。法務省の登記所備付地図で筆まで当たる
    …番 まで    どちらとも言えない。両方あててみる
    番の印が無い  役所が町名までしか書いていない。**点は置けない**

**捕まえないもの**：印があれば本当に当たるか。それは実際に引き当てて測る。
ここが数えているのは「**住所の書かれ方**」だけ。
"""
import collections
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ALL = os.path.join(HERE, "data", "all.json")
REPORT = os.path.join(HERE, "data", "ref", "addr-katachi.md")

# **印は、住所の文字列の中にしか無い。** 種類や自治体から推測しない
GO = re.compile(r"[0-9０-９]\s*号")
BANCHI = re.compile(r"番\s*地")
BAN = re.compile(r"[0-9０-９]\s*番")

KATACHI = [
    ("住居表示（…番…号）", "位置参照情報の街区レベル", "番まで"),
    ("地番（…番地…）", "法務省の登記所備付地図", "筆まで"),
    ("…番 まで", "両方あててみる", "番まで（たぶん）"),
    ("番の印が無い", "町名までしか書かれていない", "**点は置けない**"),
    ("住所が空", "店名から推定するしかない", "**点は置けない**"),
]


def katachi(addr):
    """住所1つの書かれ方を返す。**順番が意味を持つ。**

    「…番…号」は「…番」も満たすので、細かいほうから先に見る。
    ゆるいほうを先に見ると、住居表示が全部「…番 まで」に落ちる。
    """
    a = (addr or "").strip()
    if not a:
        return "住所が空"
    if GO.search(a):
        return "住居表示（…番…号）"
    if BANCHI.search(a):
        return "地番（…番地…）"
    if BAN.search(a):
        return "…番 まで"
    return "番の印が無い"


def measure(recs):
    zentai = collections.Counter()
    rei = collections.defaultdict(list)
    for r in recs:
        k = katachi(r.get("address"))
        zentai[k] += 1
        a = (r.get("address") or "").strip()
        # **見本は実物から取る。** ただし**市区町村より下は出さない**
        if a and len(rei[k]) < 2:
            rei[k].append(re.sub(r"[0-9０-９]", "◯", a)[:30])
    return zentai, rei


def main():
    if not os.path.exists(ALL):
        print(f"{ALL} が無い")
        return 1
    with open(ALL, encoding="utf-8") as f:
        recs = json.load(f)
    zentai, rei = measure(recs)
    n = len(recs)

    okeru = sum(zentai[k] for k in ("住居表示（…番…号）", "地番（…番地…）", "…番 まで"))
    lines = [
        "# 住所が、どこまで書かれているか", "",
        f"`data/all.json` {n:,}件を数えたもの。**このファイルは `addr_katachi.py` が書く。**",
        "手で直さない。", "",
        "地図に点を置ける細かさは、こちらの腕ではなく**役所が何を書いたか**で決まる。",
        "町丁目の真ん中に点を置くのは、**届出が言っていない場所を言う**ことになる（3.5）。", "",
        f"**番まで辿れる見込みがあるのは {okeru:,}件（{okeru / n * 100:.1f}%）。**",
        f"残り {n - okeru:,}件（{(n - okeru) / n * 100:.1f}%）は、役所が町名までしか書いていないか、住所が無い。", "",
        "| 書かれ方 | 件数 | 割合 | どこから引くか | どこまで当たるか | 例 |",
        "|---|---:|---:|---|---|---|",
    ]
    for name, doko, madde in KATACHI:
        v = zentai.get(name, 0)
        lines.append(f"| {name} | {v:,} | {v / n * 100:.1f}% | {doko} | {madde} | "
                     + "（数字は◯に伏せた）" + " ".join(rei.get(name, [])) + " |")
    lines += ["", "## 数えていないこと", "",
              "印があれば**本当に当たるか**は、ここでは分からない。",
              "実際に引き当ててから、当たった件数をここに足す。", ""]

    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("\n".join(lines[:9]))
    print(f"→ {REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
