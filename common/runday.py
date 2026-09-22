#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""この実行の「今日」。走り始めに1回決めて、最後まで同じ値を使う。

毎朝の巡回は 22:00 UTC に始まり、終わるのは翌日の 00:10 UTC ごろ。
**走っている途中で日付が変わる。** そのため、

    取ってきた日（recon が 22時台に打つ）    2026-09-18
    commit の日（git が 翌 00:08 に打つ）    2026-09-19

が毎日1日ずれていた（2026-09-19 に気づいた）。サイトに出ている取得日は、
**毎日1日早いほうが出ていた。**

時間帯を日本時間に寄せると、いまの時刻ならまたがなくなる。
だがそれは「たまたままたがない」だけで、走る時刻が動けばまた起きる。
**決めるのは走り始めの1回。** 走らせる側が `RUN_DATE` を渡す。

共通仕様3.5。`as_of`（値がいつのものか）と `fetched_on`（こちらが取った日）を
分けるのと同じ話で、こちらは **`fetched_on` が1つの実行の中で2つある**という形。
"""
import os
from datetime import date

ENV = "RUN_DATE"


def today():
    """この実行の日付（ISO）。`RUN_DATE` があればそれ、無ければ実際の今日。

    手元で走らせるときは `RUN_DATE` を置かない。実際の今日でよい。
    **読めない値が入っていたら落とす。** 黙って今日に倒すと、
    渡したつもりで渡せていないことに気づけない。
    """
    v = (os.environ.get(ENV) or "").strip()
    if not v:
        return date.today().isoformat()
    return date.fromisoformat(v).isoformat()   # 形が違えば ValueError で止まる


def today_date():
    """date 型が要るところ用。"""
    return date.fromisoformat(today())
