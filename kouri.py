#!/usr/bin/env python3
"""小売業者の変化を数える。**「変わった」と「入れ替わった」は別。**

2026-09-19、中島さん（商業不動産の実務）から
「ビルや商業施設のフロアマップ」の案が出た。
**うちのデータでどこまで見えるかを先に測った**（作る前に測る）。

結果は「繋がるが、弱い」。

    変更届のうち「小売業者に関するもの」   **「変わった」としか書いていない**
    小売業者の名前が年をまたいで変わった建物 **ほとんどが社名変更**

        ㈱イオン        → イオンリテール㈱
        上新電機㈱      → 株式会社Joshin

**テナントの入れ替えではない。** だから「小売業者が変わった」と出すと、
社名変更まで「入れ替え」に読まれる（3.5「名乗りは事実の主張になる」）。

    ❌ 小売業者が入れ替わった     **入れ替えかどうかは分からない**
    ✅ 届出に書かれた小売業者の名前が、◯年◯月から◯年◯月のあいだに変わった

そして**届出は最大でも数者しか載せない。** なんばパークスは届出上5者だが、
実際は200店舗を超える。**フロアマップでないと分からない穴がここ。**

**捕まえないもの**：なぜ変わったか。社名変更か、譲渡か、入れ替えか。
**届出には書かれていない。**
"""
import collections
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ALL = os.path.join(HERE, "data", "all.json")
REPORT = os.path.join(HERE, "data", "ref", "kouri.md")


def norm(x):
    """突合の鍵。**空白だけ落とす。** 会社の種類（㈱・株式会社）は落とさない。

    落とすと「㈱イオン」と「イオンリテール㈱」が同じに見える。
    **同じに見せたいのではなく、違うことを数えたい。**
    """
    return re.sub(r"\s|　", "", (x or "").strip())


def measure(recs):
    """建物ごとに、届出に載った小売業者の名前の移り変わりを集める。"""
    tate = collections.defaultdict(list)
    for r in recs:
        s, q = norm(r.get("store")), norm(r.get("retailer"))
        if s and q:
            tate[s].append((r.get("notified_on") or "", q))
    for v in tate.values():
        v.sort()
    # **「年をまたいで変わった」と「同じ日に複数いる」は別のこと。**
    #
    # 2026-09-19、ここを1回まちがえた。どちらも
    # 「その建物に出てくる名前が2つ以上か」で数えていたので、
    # **2つの行が同じ数（103）を出していた。** 名前だけ違う同じ数。
    # 競売統計の「市区町村92は升92だった」と同じ形（正本9節）。
    #
    # 分けるには**日を見る。**
    #   同じ日に2つ以上   → テナントが複数（入れ替えではない）
    #   日が違って2つ以上 → 名前が移り変わった
    onaji_hi = {}
    for s, v in tate.items():
        hi = collections.defaultdict(set)
        for d, q in v:
            hi[d].add(q)
        if any(len(qs) > 1 for qs in hi.values()):
            onaji_hi[s] = max(hi.values(), key=len)

    utsuri = {}
    for s, v in tate.items():
        hi = collections.defaultdict(set)
        for d, q in v:
            hi[d].add(q)
        # その日その日の名前をつないで、**日をまたいで増えているか**
        zentai = {q for _d, q in v}
        if len(zentai) > max((len(qs) for qs in hi.values()), default=0):
            utsuri[s] = sorted(v)
    return tate, utsuri, onaji_hi


def main():
    if not os.path.exists(ALL):
        print(f"{ALL} が無い")
        return 1
    with open(ALL, encoding="utf-8") as f:
        recs = json.load(f)
    tate, utsuri, onaji_hi = measure(recs)

    henko = sum(1 for r in recs
                if r.get("kind") == "変更" and "小売業" in (r.get("content") or ""))

    lines = [
        "# 小売業者の変化", "",
        "**このファイルは `kouri.py` が書く。** 手で直さない。", "",
        "「フロアマップ」の案が出たので、**うちのデータでどこまで見えるかを測った。**", "",
        "| | 件数 |", "|---|---:|",
        f"| 変更届のうち「小売業者に関するもの」 | {henko:,} |",
        f"| 小売業者の名前が載っている建物 | {len(tate):,} |",
        f"| **日をまたいで名前が移り変わった建物** | {len(utsuri):,} |",
        f"| **同じ届出日に2者以上が載っている建物** | {len(onaji_hi):,} |", "",
        "**下の2つは別のこと。** 上は名前が変わった、下はテナントが複数。",
        "ここは一度まちがえて、**2つの行が同じ数を出していた**（名前だけ違う同じ数）。", "",
        "## 分かったこと", "",
        "**① 変更届は「変わった」としか書いていない。**",
        "   内容の欄は「小売業者の名称及び住所並びに代表者氏名」で、",
        "   **何から何に変わったかは書かれていない。**", "",
        "**② 名前が変わって見えるものは、ほとんどが社名変更。**", "",
        "       ㈱イオン        → イオンリテール㈱",
        "       上新電機㈱      → 株式会社Joshin", "",
        "   **テナントの入れ替えではない。**",
        "   「小売業者が入れ替わった」と出すと、社名変更まで入れ替えに読まれる。", "",
        "**③ 届出は数者しか載せない。**",
        "   届出上いちばん多い建物でも数者だが、大きい施設は200店舗を超える。",
        "   **その穴はフロアマップでないと埋まらない。**", "",
        "## 書き方", "",
        "    ❌ 小売業者が入れ替わった",
        "    ✅ 届出に書かれた小売業者の名前が、◯年◯月から◯年◯月のあいだに変わった", "",
        "## 数えていないこと", "",
        "**なぜ変わったか。** 社名変更か、譲渡か、入れ替えか。",
        "**届出には書かれていない。**", "",
    ]
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("\n".join(lines[6:12]))
    print(f"→ {REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
