#!/bin/sh
# 検査を走らせる。**これを直に呼ぶ。** python3 test_privacy.py を手で打たない。
#
# 理由が2つある（どちらも 2026-09-19 に実物で踏んだ。共通仕様9節）。
#
# 1. 古い __pycache__ が使われる。
#    .pyc が古いかどうかは (mtime, サイズ) で決まる。「売却」→「落札」のように
#    **同じバイト数で、同じ秒のうちに**書き換えると、両方が一致してしまい、
#    Python は古いほうを読む。30回試して30回とも古いままだった。
#    直したのに落ち続ける／壊したのに鳴らない、が両方起きる。
#    **`python3 -B` では直らない。** -B は「新しく書かない」だけで、
#    もうある .pyc は読む（実測）。消すしかない。
#
# 2. 出力を見たくて、落ちたことを捨ててしまう。
#    `python3 test.py | tail -2 && git commit` は tail の 0 が返るので通る。
#    `python3 test.py; echo $?` も、$? を読んだ時点で set -e が効かない。
#    落ちたら止まる形で書く。
set -e
cd "$(dirname "$0")"
find . -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
: "${RUN_DATE:=$(TZ=Asia/Tokyo date +%F)}"
export RUN_DATE
python3 test_privacy.py > /tmp/check.log 2>&1 || { tail -20 /tmp/check.log; exit 1; }
tail -2 /tmp/check.log
# 門（common/kado.py）の検査。unittest（tests/ に __init__.py は無くても discover は動く）
python3 -m unittest discover -s tests > /tmp/check-kado.log 2>&1 || { tail -40 /tmp/check-kado.log; exit 1; }
tail -3 /tmp/check-kado.log
