#!/usr/bin/env python3
"""町丁目までのキーが作れなかった行を数えて、記録に残す。

共通仕様4節の③は「`addr_key_town` を空にして**記録する**」と書いている。
**その記録が、どこにも無かった**（2026-09-19 に気づいた）。
`data/parse-unknown.md` は列の対応の話で、町丁目のことは1行も書いていない。
4,809件のうち1,369件（28%）が、黙って空のままだった。

空になる理由は**3つ**ある。**混ぜない。**

  ①でも②でも決まらない   町丁目の一覧が無いので②が効かない
  原典に住所が書かれていない  向こうが書かなかった。こちらでは減らせない
  住所は在るが読めなかった   6節の unresolved。自分が減らすもの

**2026-09-21 に、この段自身が2つ目を数えていなかった。**
`addrlib.normalize` は住所が空でも投げないので、**空の行が「読めた行」に混ざり、
「住所そのものが読めなかった行: 0」と書かれていた。**
実際は 464 行が空だった。**0件は、その道を1回も通っていないときにも出る**（6節）。
戒めを書いた当人が、同じ文の下で踏んでいた。

一覧は `data/ref/towns.json`（出典は `towns.meta.json`）。**どの市の一覧が在るかは
ここに書かない**——この段が毎回その場で数えて記録に出す。出どころは国土交通省の位置参照情報で、
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
    """(全体, 空, 市ごとの内訳, 読めなかった数, 住所が無かった数) を返す。

    **3つを分ける。** 原典が書かなかった行を「読めた行」に混ぜると、
    町丁目が当たらない割合が薄まり、**こちらの取りこぼしに見える。**
    """
    total = empty = unreadable = nashi = 0
    by_city = collections.Counter()
    for r in recs:
        # ① **原典に住所が書かれていない。** ここで先に分ける。
        #    normalize は空でも投げないので、下まで落とすと「読めた」に混ざる
        if not (r.get("address") or "").strip():
            nashi += 1
            continue
        try:
            d = addrlib.normalize(r.get("pref", ""), r.get("city", ""), r.get("address", ""))
        except ValueError:
            raise                            # 食い違いは握りつぶさない（4節）
        except Exception:
            unreadable += 1                  # ② 住所は在るが読めなかった
            continue
        total += 1
        if not d.get("addr_key_town"):       # ③ 町丁目の一覧がまだ無い
            empty += 1
            by_city[f'{r.get("pref", "")}{r.get("city", "")}'] += 1
    return total, empty, by_city, unreadable, nashi


def main():
    with open(ALL, encoding="utf-8") as f:
        recs = json.load(f)
    total, empty, by_city, unreadable, nashi = measure(recs)
    pct = (empty * 100.0 / total) if total else 0.0
    zentai = total + unreadable + nashi

    # **どの市に一覧が在るかを、その場で数える。**書き置くと古くなる
    mochi = addrlib.load_towns()
    ichiran = "、".join(f"`{c}`（{len(v):,}件）" for c, v in sorted(mochi.items()))

    lines = [f"# 町丁目までつながらなかった行（{runday.today()} に数えた）", "",
             f"- 数えた行（全部）: **{zentai:,}**",
             f"- **原典に住所が書かれていなかった行: {nashi:,}**"
             "（こちらでは減らせない）",
             f"- 住所は在るが**読めなかった**行: {unreadable:,}（こちらが減らすもの）",
             f"- 住所が読めた行: **{total:,}**",
             f"- そのうち `addr_key_town` が空: **{empty:,}**"
             f"（読めた行の {pct:.1f}%）", "",
             "**3つを分ける。** 原典が書かなかった行を「読めた行」に混ぜると、",
             "町丁目が当たらない割合が薄まり、**こちらの取りこぼしに見える。**", "",
             "空になるのは、**その市の町丁目の一覧がまだ無い**か、一覧は在っても",
             "**その町名が載っていない**ため。正本4節の②・①\' が効かず、③で空になる。",
             "**推測で埋めない**のは正しいが、**空になったことを記録していなかった**",
             "ので、ここに出す。", "",
             "一覧が在る市（`data/ref/towns.json`）：" + (ichiran or "**まだ1市も無い**"), "",
             "一覧の出どころは国土交通省の大字・町丁目レベル位置参照情報。",
             "出典は `data/ref/towns.meta.json`。**towns.json には混ぜない**", "",
             "## 市区町村ごと", "", "| 市区町村 | 空 |", "|---|---:|"]
    for city, n in by_city.most_common():
        lines.append(f"| {city} | {n:,} |")
    lines.append("")

    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("\n".join(lines[:12]))
    print(f"→ {REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
