#!/usr/bin/env python3
"""町丁目までのキーが作れなかった行を数えて、記録に残す。

共通仕様4節の③は「`addr_key_town` を空にして**記録する**」と書いている。
**その記録が、どこにも無かった**（2026-09-19 に気づいた）。
`data/parse-unknown.md` は列の対応の話で、町丁目のことは1行も書いていない。
4,809件のうち1,369件（28%）が、黙って空のままだった。

空になる理由は2つある。**混ぜない。**

  ①でも②でも決まらない   町丁目の一覧が無いので②が効かない（いまは全部これ）
  住所そのものが読めない   6節の unresolved。自分が減らすもの

一覧（`data/ref/towns.json`）はまだ無い。出どころは国土交通省の位置参照情報で、
`ref_youto.py` が既に同じ場所（`nlftp.mlit.go.jp/isj/`）を見に行っている。
**用途地域と町丁目一覧は、同じ1回の実行で取りに行ける。**
"""
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import addr as addrlib          # noqa: E402
from common import runday                   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ALL = os.path.join(HERE, "data", "all.json")
REPORT = os.path.join(HERE, "data", "ref", "town-gap.md")


def measure(recs):
    """(全体, 空, 市ごとの内訳, 読めなかった数) を返す。"""
    total = empty = unreadable = 0
    by_city = collections.Counter()
    for r in recs:
        try:
            d = addrlib.normalize(r.get("pref", ""), r.get("city", ""), r.get("address", ""))
        except ValueError:
            raise                            # 食い違いは握りつぶさない（4節）
        except Exception:
            unreadable += 1
            continue
        total += 1
        if not d.get("addr_key_town"):
            empty += 1
            by_city[f'{r.get("pref", "")}{r.get("city", "")}'] += 1
    return total, empty, by_city, unreadable


def main():
    with open(ALL, encoding="utf-8") as f:
        recs = json.load(f)
    total, empty, by_city, unreadable = measure(recs)
    pct = (empty * 100.0 / total) if total else 0.0

    lines = [f"# 町丁目までつながらなかった行（{runday.today()} に数えた）", "",
             f"- 住所が読めた行: **{total:,}**",
             f"- そのうち `addr_key_town` が空: **{empty:,}**（{pct:.1f}%）",
             f"- 住所そのものが読めなかった行: {unreadable:,}", "",
             "空になるのは、いまは**町丁目の一覧（`data/ref/towns.json`）がまだ無い**ため。",
             "正本4節の②が効かず、③で空になっている。**推測で埋めない**のは正しいが、",
             "**空になったことを記録していなかった**ので、ここに出す。", "",
             "一覧の出どころは国土交通省の位置参照情報。`ref_youto.py` が既に",
             "同じ場所を見に行っているので、**同じ1回の実行で取りに行ける。**", "",
             "## 市区町村ごと", "", "| 市区町村 | 空 |", "|---|---:|"]
    for city, n in by_city.most_common():
        lines.append(f"| {city} | {n:,} |")
    lines.append("")

    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("\n".join(lines[:9]))
    print(f"→ {REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
