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
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ALL = os.path.join(HERE, "data", "all.json")
REPORT = os.path.join(HERE, "data", "ref", "kieru.md")
JURAN_KATEI = 120   # 「縦覧は4か月」という仮定。**下で当たるかを測る**
# こちらが毎日見に行き始めた日。**これより前は保存から積んだ分**なので、
# 「いつ消えたか」の幅が大きい（保存の間隔だけ分からない）
SITE_START = "2026-09-11"


def hi(x):
    return datetime.date.fromisoformat(x)


def measure(recs, start=None):
    """**いつネットから消えたか**を数える。中央値は出さない。

    2026-09-19、中島さんの——

    > 中央値はだめにゃ。**情報としてしょぼい**きがするにゃ。
    > 閉鎖日は書いてあるにゃね？？ あとは**ネットから消えた日**はどうかにゃ？

    **3つとも正しい。**

      中央値          **こちらの観測の話**。読む人には関係ない → 出さない
      廃止日          届出に書いてある事実 → 既に個票に出ている
      **消えた日**    **こちらしか持っていない** → ここで数える

    ただし**消えた日は点ではない。** 持っているのは「最後に在るのを見た日」で、
    実際に消えたのはその翌日から次に見た日までの**どこか**（3.5「終了は点ではなく区間」）。

    だから**幅で分ける。** 毎日見ている期間なら幅1日。
    保存（Internet Archive）から積んだ分は、保存の間隔だけ幅がある。
    **幅はこちらの弱点の数字でもある。**

    **捕まえないもの**：なぜ消えたか。縦覧が終わったのか、
    差し替えられたのか、相手の都合か。**確かめていないので書かない。**
    """
    start = start or SITE_START
    kieta = [r for r in recs
             if r.get("mode") == "snapshot" and not r.get("listed")
             and r.get("last_seen")]
    mainichi = [r for r in kieta if r["last_seen"] >= start]
    hozon = [r for r in kieta if r["last_seen"] < start]
    tsuki = collections.Counter(r["last_seen"][:7] for r in kieta)
    return kieta, mainichi, hozon, tsuki


def katei_wa_ataru(recs):
    """「縦覧開始＋4か月で消える」という仮定が当たるかを数える。

    **仮定を書いたら、当たるかを測る。** 当たらない仮定で画面に日付を出すと、
    それは予測であって実績ではなくなる（3.5）。

    2026-09-19 の実測では、**当たり25・外れ89**。
    だから画面に「◯月◯日まで」とは書かない。
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
    kieta, mainichi, hozon, tsuki = measure(recs)
    ok, ng, nashi = katei_wa_ataru(recs)
    nokoru = sum(1 for r in recs
                 if r.get("mode") == "snapshot" and r.get("listed"))

    lines = [
        "# 自治体のページから消えた届出", "",
        "**このファイルは `kieru.py` が書く。** 手で直さない。", "",
        "**こちらしか持っていない記録。** 届出が自治体のページから消えても、",
        "このサイトには残る。いつ消えたかを数える。", "",
        f"消える置き場（`snapshot`）に **{nokoru + len(kieta):,}件**。",
        f"うち **{len(kieta):,}件が消えた**。残り {nokoru:,}件はまだ載っている。",
        f"消えない置き場（`cumulative`）の "
        f"{sum(1 for r in recs if r.get('mode') == 'cumulative'):,}件は、ここに数えない。", "",
        "## 「消えた日」は点ではなく、区間", "",
        "持っているのは「**最後に在るのを見た日**」。実際に消えたのは、",
        "その翌日から次に見た日までのどこか（3.5）。**幅で分ける。**", "",
        "| | 件数 | 幅 |", "|---|---:|---|",
        f"| **毎日見ていた期間に消えた** | {len(mainichi):,} | "
        f"**1日**。「◯日には在り、翌日には無かった」と書ける |",
        f"| 保存から積んだ分 | {len(hozon):,} | 保存の間隔だけ分からない |", "",
        f"毎日見に行き始めたのは **{SITE_START}**。",
        "**幅1日で言えるのは、それ以降に消えたものだけ。**",
        "いまは少ないが、**毎日増える。**", "",
    ]
    if mainichi:
        lines += ["### 幅1日で言えるもの", "",
                  "| 最後に在るのを見た日 | 種類 | 市区町村 | 収集先 |",
                  "|---|---|---|---|"]
        for r in sorted(mainichi, key=lambda x: x["last_seen"], reverse=True):
            lines.append(f"| {r['last_seen']} | {r.get('kind')} | "
                         f"{r.get('area')} | `{r.get('source')}` |")
        lines.append("")

    lines += ["## 最後に見た月", "", "| 月 | 件数 |", "|---|---:|"]
    for m, n in sorted(tsuki.items(), reverse=True)[:12]:
        lines.append(f"| {m} | {n:,} |")
    lines += ["",
              "**一度に大きく消える月がある。** 年度替わりの入れ替えとみているが、",
              "**確かめていないので書かない**（3.3）。", "",
              "## 出さないことにしたもの", "",
              "**「◯日で消えます」という中央値は出さない。**",
              "こちらの観測の話であって、読む人に関係がない（2026-09-19、中島さん）。", "",
              "**「あと3日で消えます」も書かない。** 予測は外れる。",
              f"「縦覧は4か月」という仮定を測ったら、±14日以内で当たったのは {ok:,}件、",
              f"**外れたのが {ng:,}件**だった（`review_from` を持たないもの {nashi:,}件は除く）。", "",
              "書けるのは2つだけ。", "",
              "    届出に書かれた廃止日      向こうが言っている事実",
              "    こちらが最後に見た日      こちらが見た事実。**他に誰も持っていない**", ""]

    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("\n".join(lines[:10]))
    print(f"→ {REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
