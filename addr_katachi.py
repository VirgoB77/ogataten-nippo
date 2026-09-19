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


KOMAKAI = ("住居表示（…番…号）", "地番（…番地…）", "…番 まで")


def mise_key(r):
    """市区町村＋店名。**突合の鍵であって、場所の鍵ではない。**

    括弧の中（（仮称）など）と空白を落とす。**地番は入れない**——
    4節の「台帳の鍵は並び順に頼らない」と同じで、
    **鍵に場所を入れると、場所が分かっていない行が鍵を作れなくなる。**
    """
    mise = re.sub(r"\s|　|（.*?）|\(.*?\)", "", (r.get("store") or ""))
    return ((r.get("area") or ""), mise)


def mikomi(recs):
    """場所が付く見込みを4段で数える。**それぞれ別の手で増える。**

    2026-09-19、中島さん（不動産の実務）の——

    > 町丁目しかない38.4%も、絶対 開発申請があるから大丈夫のはずにゃ

    **方向は正しい。だが「全部」ではない。** 数えたので、ここに残す。

    ① 住所だけ        いま出せるもの
    ② ＋店名でつなぐ   同じ店の別の届出が細かい住所を持っている
    ③ ＋開発許可       新設の地番が取れれば、その店の他の届出にも回る
    ④ 残り            **その店の新設届を、うちがまだ持っていない**

    ④は開発許可の問題ではない。**こちらの収集の穴**（6節 `unobserved`）。

    **捕まえないもの**：開発許可が本当に全部当たるか。
    既存ビルへの入居や増床は開発行為を伴わないことがある。**確かめていない。**
    """
    komakai = set()
    for r in recs:
        if katachi(r.get("address")) in KOMAKAI and r.get("store"):
            komakai.add(mise_key(r))
    arai = [r for r in recs if katachi(r.get("address")) not in KOMAKAI]
    tsunagaru = [r for r in arai if mise_key(r) in komakai]
    nokori = [r for r in arai if mise_key(r) not in komakai]
    # 残ったものの中の「新設」に地番が付けば、同じ店の他の届出にも回る
    shinsetsu = set(mise_key(r) for r in nokori if r.get("kind") == "新設")
    mawaru = [r for r in nokori if mise_key(r) in shinsetsu]
    saigo = [r for r in nokori if mise_key(r) not in shinsetsu]
    n = len(recs)
    return [
        ("住所だけ（いま）", n - len(arai), "役所が番まで書いている"),
        ("＋店名でつなぐ", n - len(nokori), "同じ店の別の届出が細かい住所を持っている"),
        ("＋開発許可で新設に地番", n - len(saigo), "**中島さんの筋。** 兵庫と大阪の両方が要る"),
        ("最後まで残る", len(saigo), "**その店の新設届を、うちがまだ持っていない**"),
    ], saigo


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
    dan, saigo = mikomi(recs)
    lines += ["", "## 場所が付く見込み", "",
              "住所の書かれ方だけでは決まらない。**店名でつなぐ**のと、",
              "**開発許可で新設に地番を付ける**のが効く（2026-09-19、中島さん）。", "",
              "| 手 | 場所が付く | 割合 | 何で増えるか |", "|---|---:|---:|---|"]
    for name, v, naze in dan[:3]:
        lines.append(f"| {name} | {v:,} | {v / n * 100:.1f}% | {naze} |")
    nokoru = dan[3][1]
    lines += [f"| **{dan[3][0]}** | {nokoru:,} | {nokoru / n * 100:.1f}% | {dan[3][2]} |", ""]
    uchiwake = collections.Counter(r.get("kind") for r in saigo)
    lines += ["最後まで残るものの内訳：" + "・".join(
        f"{k} {v:,}" for k, v in uchiwake.most_common()), "",
        "ほとんどが**変更**。変更届は既にある店の話なので、",
        "その店の**新設届をうちが持っていれば**場所が付く。持っていない。",
        "**開発許可の問題ではなく、こちらの収集の穴**（6節 `unobserved`）。", "",
        "## 数えていないこと", "",
        "**開発許可が本当に全部当たるかは、数えていない。**",
        "既存ビルへの入居や増床は開発行為を伴わないことがある。",
        "上の3段目は「全部当たれば」の数で、**実測ではない。**", "",
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
