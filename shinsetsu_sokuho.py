#!/usr/bin/env python3
"""新設届の**前向き観測**。**商品は作らない。**

## なぜ「前向き」なのか

2026-09-21 に測ったら、**過去の「初めて見た日」は使えなかった。**

    まとめて取った日が混ざる（1,419件・714件）
    そもそも欄が無い記録が2,167件
    **時刻を持っていない。日だけ**

**過去は直せない。** なので**今日から先の分だけ**を、きれいに貯める。

**90日ためてから判断する。** いま**サイトも通知も作らない**（統括の判断・2026-09-21）。

## 出すもの3つ

    **① 自治体で確認できた最初の日**  公告の日／縦覧が始まった日
    **② こちらが初めて見た日**        `first_seen`
    **③ 出どころ**

**①は、出どころが書いているときだけ立つ。**
書いていなければ **「初回確認日」** として②を使い、**そう名乗る**（ルール⑥）。
**「公開された日」と「こちらが見た日」を、同じ欄に混ぜない。**

## ⚠️ 速さの上限は、**相手の公開頻度**

**毎日見ても、相手が月に1回しか出さなければ、月に1回しか知れない。**

    ① → ②   **相手が決める。**こちらには縮められない
    ② → ③   **こちらが決める。**最大1日

なので**相手が新しい行を出す間隔**も一緒に数える。**そこが天井。**

**ただしこれは「こちらが見た日」の間隔であって、「相手が出した日」の間隔ではない。**
**毎日見ているので近いはずだが、同じではない。**
"""
from __future__ import annotations

import collections
import json
import statistics
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common.runday import today  # noqa: E402

ALL = HERE / "data" / "all.json"
KIROKU = HERE / "data" / "ref" / "shinsetsu-sokuho.md"
DAICHO = HERE / "data" / "ref" / "shinsetsu-sokuho.json"

# **前向き観測を始めた日。** これより前は、まとめて取った分が混ざるので入れない。
# **動かさない。** 動かすと、混ざったものが入り込む
KAISHI = "2026-09-21"

# ①に使える欄。**上から順に見る。** どれも無ければ「分からない」
KOUKAI = (
    ("gazette_date", "公告された日"),
    ("review_from", "縦覧が始まった日"),
)


def hi(r) -> str:
    return r.get("first_seen") or ""


def koukai_bi(r):
    """①。**出どころが書いているときだけ立つ。**

    立たなければ `(None, "分からない")` を返す。**②で埋めない。**
    """
    for k, na in KOUKAI:
        v = (r.get(k) or "").strip()
        if v:
            return v, na
    return None, "分からない"


def hirou(recs, kaishi: str = KAISHI):
    """前向き観測に入れる新設届。**始めた日より前は入れない。**"""
    de = []
    for r in recs:
        if (r.get("kind") or "") != "新設":
            continue
        mita = hi(r)
        if not mita or mita < kaishi:
            continue  # **まとめて取った分が混ざる。入れない**
        bi, na = koukai_bi(r)
        de.append({
            "store": (r.get("store") or "").strip(),
            "notified_on": r.get("notified_on") or "",
            # ① 公開された日。**無ければ None。②で埋めない**
            "koukai_bi": bi,
            "koukai_no_moto": na,
            # ② こちらが初めて見た日
            "mita_bi": mita,
            # ③ 出どころ
            "source": r.get("source") or "",
            "pref": r.get("pref") or "",
        })
    return sorted(de, key=lambda e: (e["mita_bi"], e["source"]))


def kankaku(de):
    """出どころごとに、**新しい新設届が現れた日の間隔。**

    **これは「こちらが見た日」の間隔。** 相手が出した日の間隔ではない。
    毎日見ているので近いはずだが、**同じではない**（9節・名乗り）。
    """
    hi_by = collections.defaultdict(set)
    for e in de:
        hi_by[e["source"]].add(e["mita_bi"])
    out = {}
    for s, days in hi_by.items():
        d = sorted(date.fromisoformat(x) for x in days)
        if len(d) < 2:
            out[s] = {"kaisuu": len(d), "chuuoutchi": None,
                      "naze": "**2回以上見ないと、間隔は出ない**"}
            continue
        k = [(d[i + 1] - d[i]).days for i in range(len(d) - 1)]
        out[s] = {"kaisuu": len(d), "chuuoutchi": statistics.median(k),
                  "mijikai": min(k), "nagai": max(k), "naze": ""}
    return out


def houkoku(de, kan, kyou) -> str:
    L = []
    a = L.append
    a("# 新設届の前向き観測")
    a("")
    a(f"**{KAISHI} から始めた。いまは {kyou}。**")
    a("")
    a("**商品は作っていない。** 90日ためてから判断する（2026-09-21 の判断）。")
    a("")
    a(f"    貯まった新設届   **{len(de)} 件**")
    a("")
    a("**始めた日より前は入れていない。** まとめて取った分が混ざるので。")
    a("")
    a("## ① 公開された日が、どれだけ立っているか")
    a("")
    c = collections.Counter(e["koukai_no_moto"] for e in de)
    for na in ("公告された日", "縦覧が始まった日", "分からない"):
        a(f"    {na:14s} {c[na]} 件")
    a("")
    a("**「分からない」は、出どころが公開の日を書いていないもの。**")
    a("**②（こちらが初めて見た日）で埋めていない。** 埋めると、")
    a("**相手が出した日と、こちらが見た日が、同じ欄で混ざる**（ルール⑥）。")
    a("")
    a("## ①→② が何日か（**相手が決める。こちらには縮められない**）")
    a("")
    v = []
    for e in de:
        if not e["koukai_bi"]:
            continue
        d = (date.fromisoformat(e["mita_bi"])
             - date.fromisoformat(e["koukai_bi"])).days
        v.append(d)
    if len(v) >= 1:
        v.sort()
        a(f"    測れた   {len(v)} 件")
        a(f"    **中央値 {statistics.median(v):+.0f} 日**   最短 {v[0]:+d}   最長 {v[-1]:+d}")
    else:
        a("    **まだ1件も測れない。** 0件ではなく、**まだ貯まっていない**")
    a("")
    a("## 出どころごとに、新しい新設届が現れる間隔（**天井**）")
    a("")
    a("**毎日見ても、相手が月に1回しか出さなければ、月に1回しか知れない。**")
    a("")
    for s, k in sorted(kan.items()):
        if k["chuuoutchi"] is None:
            a(f"    {s:20s} {k['kaisuu']} 回  {k['naze']}")
        else:
            a(f"    {s:20s} {k['kaisuu']} 回  **中央値 {k['chuuoutchi']:.0f} 日**"
              f"  最短 {k['mijikai']} / 最長 {k['nagai']}")
    if not kan:
        a("    **まだ1件も無い。** 0件ではなく、**まだ貯まっていない**")
    a("")
    a("## 1件ずつ")
    a("")
    if not de:
        a("**まだ1件も無い。** 始めたばかり。**0件ではなく、まだ来ていない。**")
    for e in de:
        a(f"- **{e['mita_bi']}** に見た　{e['store']}　（{e['pref']}・{e['source']}）")
        a(f"  - 届出の日　{e['notified_on']}")
        if e["koukai_bi"]:
            a(f"  - **{e['koukai_no_moto']}**　{e['koukai_bi']}")
        else:
            a("  - 公開された日　**分からない**（出どころが書いていない）")
    a("")
    a("---")
    a("")
    a("**この一覧は、他所に載った日と突き合わせるための材料。**")
    a("**突き合わせはこちらではしない**（外の一覧を取りに行かない）。")
    return "\n".join(L) + "\n"


def main(argv=None):
    if not ALL.exists():
        print("data/all.json が無い", file=sys.stderr)
        return 2
    recs = json.loads(ALL.read_text(encoding="utf-8"))
    kyou = today()
    de = hirou(recs)
    kan = kankaku(de)
    DAICHO.write_text(json.dumps(
        {"kaishi": KAISHI, "kyou": kyou, "kensuu": len(de),
         "kankaku": kan, "ichiran": de},
        ensure_ascii=False, indent=1), encoding="utf-8")
    KIROKU.write_text(houkoku(de, kan, kyou), encoding="utf-8")
    print(f"前向き観測 {len(de)} 件（{KAISHI} から）")
    print(f"  {KIROKU}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
