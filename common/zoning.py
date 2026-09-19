#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用途地域の書き方をそろえる。

同じ用途地域が、収集先によって別の文字列で入っている。
実測で **31通りの書き方**があった（2026-09-19）。

    第１種住居 112 ／ 第一種住居地域 27 ／ 第一種住居 18 ／ 第1種住居 13

**4通りに割れていると、170件が1つとして数えられない。**
横断ハブの前に、同じサイトの中で集計できていない。

**読めないものは返さない**（共通仕様4節「推測で埋めない」）。
「近接商業」は法律にある区分ではないが、**「近隣商業の書き間違いだろう」は
こちらの推測**なので当てない。読めなかったものは呼ぶ側が
`data/parse-unknown.md` に出す。
"""
import re
import unicodedata

# 都市計画法9条の13種類と、用途地域が無い区域の言い方
CANON = [
    "第一種低層住居専用地域", "第二種低層住居専用地域",
    "第一種中高層住居専用地域", "第二種中高層住居専用地域",
    "第一種住居地域", "第二種住居地域", "準住居地域", "田園住居地域",
    "近隣商業地域", "商業地域", "準工業地域", "工業地域", "工業専用地域",
    "市街化調整区域", "市街化区域", "用途地域の指定のない区域",
]

# 略し方。**前方一致では引かない**（「準工業」が「工業」に当たる）。
# 書かれていた形そのものと突き合わせる
_ALIAS = {}
for _c in CANON:
    _ALIAS[_c] = _c
    if _c.endswith("地域"):
        _ALIAS[_c[:-2]] = _c                      # 商業地域 → 商業
for _n in ("一", "二"):
    _ALIAS[f"第{_n}種中高層住居"] = f"第{_n}種中高層住居専用地域"
    _ALIAS[f"第{_n}種中高層"] = f"第{_n}種中高層住居専用地域"
    _ALIAS[f"第{_n}種低層住居"] = f"第{_n}種低層住居専用地域"
    _ALIAS[f"第{_n}種低層"] = f"第{_n}種低層住居専用地域"

# 区切り。全角読点・半角読点（､）・改行・スラッシュ・中黒
_SPLIT = re.compile(r"[、,､\n/／・]")
_DIGIT = {"1": "一", "2": "二", "１": "一", "２": "二"}


def _one(s):
    """1つ分をそろえる。読めなければ None。"""
    s = unicodedata.normalize("NFKC", s or "").strip()
    s = "".join(s.split())
    if not s:
        return None
    # 第1種／第２種 → 第一種／第二種。数字は「第◯種」のところだけ直す
    s = re.sub(r"第([12１２])種", lambda m: "第" + _DIGIT[m.group(1)] + "種", s)
    return _ALIAS.get(s)


def normalize(value):
    """書かれていた文字列 → (そろえた用途地域の一覧, 読めなかった一覧)。

    1つの店が複数の用途地域にまたがることがあるので、どちらも一覧で返す。
    並び順は書かれていた順のまま。同じものは1つにする。
    """
    got, unknown = [], []
    for part in _SPLIT.split(str(value or "")):
        part = part.strip()
        if not part:
            continue
        c = _one(part)
        if c is None:
            if part not in unknown:
                unknown.append(part)
        elif c not in got:
            got.append(c)
    return got, unknown
