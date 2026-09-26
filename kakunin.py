#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""取得可否確認（preflight）を1回だけ走らせる（2026-09-27・統括判断）。

**手で押す workflow（.github/workflows/kakunin.yml）からだけ呼ぶ。** 定時では走らせない。

    python3 kakunin.py <許可ID>

通信を出すのは門（common/kado.py の Kado.kakunin）だけ。ここは門を始めて、許可IDを渡すだけ。
運営者が手で書いた許可（data/ref/preflight/approvals/<許可ID>.json）が無ければ、門が通信0で止める。
記録は data/ref/preflight/records/<source_id>/ に1つ増える（上書きしない。本文は残さない）。

終了コード：0＝確認が最後まで済んだ ／ 3＝門が止めた（記録はある）／ 2＝引数が違う（何もしない）
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from common import hikisu, kado, runday  # noqa: E402
from common.fetch import UA  # noqa: E402

TSUKAIKATA = "使い方: python3 kakunin.py <許可ID>（data/ref/preflight/approvals/<許可ID>.json）"


def main(argv):
    # **知らない引数・形の違う許可IDでは、門も始めない**（記録も書かない）
    if len(argv) != 1 or not kado.PF_ID.match(argv[0]):
        hikisu.check(set(), argv or ["（許可IDが無い）"], TSUKAIKATA)
    k = kado.hajimeru(HERE, "ogataten-nippo", UA, today=runday.today())
    rec = k.kakunin(argv[0])
    print(json.dumps({x: rec.get(x) for x in ("approval_id", "source_id", "result", "stop_reason",
                                              "external_requests", "kiroku_path")},
                     ensure_ascii=False, indent=1))
    return 0 if rec["result"] == "完了" else 3


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
