#!/usr/bin/env python3
"""「消える前に見る」の材料を、実測で数える。**作る前に測る。**

2026-09-19、案出しから届いた案——

> 今週消える縦覧情報／今月で掲載終了しそうな情報

**作れる。だが「あと3日で消えます」とは書かない。** 未来の主張になる（3.5）。
書くのは**過去の実績**で、それなら外れようがない。

    ❌ あと3日で消えます                    予測。外れる
    ✅ この収集先では、こちらが見てから
       中央値◯日で消えています（過去◯件）    実績。外れようがない

**そして「載ってから」とも書かない。** こちらが持っているのは
`first_seen`（**こちらが初めて見た日**）であって、相手が載せた日ではない。
3.5「『初めて』は、こちらが見た初めてでしかない」と同じ形。

**捕まえないもの**：相手がいつ載せたか。分からない。
"""
import collections
import datetime
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ALL = os.path.join(HERE, "data", "all.json")
REPORT = os.path.join(HERE, "data", "ref", "kieru.md")
JURAN_KATEI = 120   # 「縦覧は4か月」という仮定。**下で当たるかを測る**


def hi(x):
    return datetime.date.fromisoformat(x)


def measure(recs):
    """収集先ごとに「こちらが見てから消えるまでの日数」を数える。

    **`cumulative` の置き場は消えない。** 消える置き場（`snapshot`）だけ見る。
    混ぜると「ほとんど消えない」という嘘の数字になる。
    """
    by = collections.defaultdict(list)
    for r in recs:
        if r.get("mode") != "snapshot" or r.get("listed"):
            continue
        if not (r.get("first_seen") and r.get("last_seen")):
            continue
        by[r.get("source") or "？"].append(
            (hi(r["last_seen"]) - hi(r["first_seen"])).days)
    return by


def katei_wa_ataru(recs):
    """「縦覧開始＋4か月で消える」という仮定が当たるかを数える。

    **仮定を書いたら、当たるかを測る。** 当たらない仮定で画面に日付を出すと、
    それは予測であって実績ではなくなる（3.5）。
    """
    ok = ng = nashi = 0
    for r in recs:
        if r.get("mode") != "snapshot" or r.get("listed"):
            continue
        if not r.get("last_seen"):
            continue
        if not r.get("review_from"):
            nashi += 1
            continue
        yoso = hi(r["review_from"]) + datetime.timedelta(days=JURAN_KATEI)
        if abs((hi(r["last_seen"]) - yoso).days) <= 14:
            ok += 1
        else:
            ng += 1
    return ok, ng, nashi


def main():
    if not os.path.exists(ALL):
        print(f"{ALL} が無い")
        return 1
    with open(ALL, encoding="utf-8") as f:
        recs = json.load(f)
    by = measure(recs)
    ok, ng, nashi = katei_wa_ataru(recs)
    kieta = sum(len(v) for v in by.values())
    nokoru = sum(1 for r in recs
                 if r.get("mode") == "snapshot" and r.get("listed"))

    lines = [
        "# 消えるまでの日数（実測）", "",
        "**このファイルは `kieru.py` が書く。** 手で直さない。", "",
        "「今週消える」を作るための材料。**作る前に測った。**", "",
        f"消える置き場（`snapshot`）に **{nokoru + kieta:,}件**。",
        f"うち **{kieta:,}件が既に消えた**。残り {nokoru:,}件はまだ載っている。",
        f"消えない置き場（`cumulative`）の "
        f"{sum(1 for r in recs if r.get('mode') == 'cumulative'):,}件は、ここに数えない。", "",
        "## 収集先ごと", "",
        "| 収集先 | 消えた | 中央値 | 最小 | 最大 |", "|---|---:|---:|---:|---:|",
    ]
    for s, v in sorted(by.items(), key=lambda x: -len(x[1])):
        v = sorted(v)
        lines.append(f"| `{s}` | {len(v):,} | {statistics.median(v):.0f}日 "
                     f"| {v[0]}日 | {v[-1]}日 |")
    lines += ["",
              "**収集先ごとにまったく違う。** ひとつの平均にまとめない。", "",
              "## 「縦覧は4か月」は当たらなかった", "",
              f"`review_from` ＋ {JURAN_KATEI}日 を、実際に消えた日と比べた。", "",
              f"| | 件数 |", "|---|---:|",
              f"| ±14日以内で当たった | {ok:,} |",
              f"| **外れた** | {ng:,} |",
              f"| `review_from` を持っていない | {nashi:,} |", "",
              "**画面に「◯月◯日まで」と書けない。** 仮定が外れている。", "",
              "## 書き方", "",
              "    ❌ あと3日で消えます                 予測。外れる",
              "    ❌ この収集先では載ってから◯日        **載ってから**は分からない",
              "    ✅ こちらが見てから中央値◯日で消えています（過去◯件）", "",
              "`first_seen` は**こちらが初めて見た日**で、相手が載せた日ではない。",
              "見る前のことは分からない（3.5）。", "",
              "**中央値が0日の収集先がある。** これは「すぐ消える」ではなく、",
              "**こちらが1回しか見ていないうちに消えた**という意味。",
              "観測の区間が短いほど0に寄る。数字が育つのを待つ。", ""]

    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("\n".join(lines[:9]))
    print(f"→ {REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
