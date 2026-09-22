#!/usr/bin/env python3
"""フロアのページ1枚から、**観測に要るものだけを抜く**段。**取りに行かない。**

## 何を抜いて、何を捨てるか

統括の判断（2026-09-21）——

> 取得レスポンスに図が含まれることはあるが、**図形・画像そのものを保存資産に
> しない。** 観測に必要な**識別子・属性・事実**だけを抽出して保存する。

    **抜く**   店の側のID／場所の側のID候補／館の記号／階／掲載されていた事実
    **捨てる** `polygon` の座標・`path` の `d`・`rect` の位置・画像

**捨てても差分が取れることを確かめてある。** 同じ対応が `<option>` の側にも
入っているので、**図形を1つも読まずに、店と場所の対応が取れる。**

## 店の側と、場所の側を**混ぜない**

    shop_source_id     `/shopguide/detail/N` の N。**店のID**
    map_id_candidate   `value="map10101"`。**場所の側の候補**

**`map_id_candidate` を、こちらの確定した区画ID（`unit_id`）にしない**（統括の指示）。
**店が入れ替わっても同じ値が続くことを観測できて初めて**、区画として使える
可能性を測り直す。**いまは候補のまま。**

## 館は**記号のまま**出す。名前に直さない

`map` / `mapg` / `mapp` / `mapa` の前置きが館を分けているように見えるが、
**向こうがそう言っているわけではない。** 記号のまま持って、**読み替えない**（ルール⑥）。

## 店と結びついていない `map_id_candidate` がある

**「空き区画」とは読まない**（統括の指示）。
値の名前が自分で用途を言っているものが多い（`map_stairs_1f` など）。
**語で分けて数えるところまで。判定はしない。**
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common.fetch import decode_html  # noqa: E402
from common.runday import today  # noqa: E402

KIROKU = HERE / "data" / "ref" / "floor-chushutsu.md"

# **抜き方の版。** 変えたら上げる（古い記録を新しい抜き方で読んだつもりにならない）
NUKI_VERSION = "chushutsu-1"

OPTION = re.compile(r"<option\b[^>]*>", re.I)
DETAIL = re.compile(r"/shopguide/detail/(\d+)")
# **館を分けていそうな前置き。** 記号のまま持つ。**名前に直さない**
KIGOU = re.compile(r"^(map[a-z]*)")

# 共用部・設備らしい語。**分けて数えるだけ。判定はしない**
SHURUI = (
    ("階段", r"階段|stairs"), ("エレベーター", r"エレベーター|elevator"),
    ("エスカレーター", r"エスカレーター|escalator"),
    ("トイレ", r"トイレ|toilet|restroom"),
    ("駐車・駐輪", r"駐車|駐輪|parking"),
    ("エントランス・ゲート", r"エントランス|entrance|ゲート"),
    ("案内", r"インフォメーション|information|案内|info"),
    ("庭・広場", r"ガーデン|garden|広場|テラス|コート|stage|ステージ"),
    ("設備・サービス",
     r"ATM|ロッカー|locker|自動販売|喫煙|smoke|授乳|ベビー|baby|救護|AED|post|photo"),
    ("催事", r"event|催事"),
)

# **図形のしるし。** ここに当たるものは、出力に入ってはいけない
ZUKEI = ("points=", ' d="', "polygon", "viewBox", "<path", "<rect", "<svg")


def _attr(tag: str, na: str):
    m = re.search(rf'{na}="([^"]*)"', tag)
    return m.group(1) if m else None


def bunrui(mei: str):
    """名前を語で分ける。**判定はしない。** どれにも当たらなければ「分からない」"""
    for na, pat in SHURUI:
        if re.search(pat, mei or "", re.I):
            return na
    return "分からない"


def chushutsu(raw: bytes, ctype: str = ""):
    """1枚から、**識別子と属性だけ**を抜く。**座標は1つも読まない。**"""
    hon, _m = decode_html(raw, ctype)

    mise, kyoyou = [], []
    for m in OPTION.finditer(hon):
        tag = m.group(0)
        cv = _attr(tag, "data-connection-value") or ""
        mid = cv.split("value=")[-1] if "value=" in cv else _attr(tag, "value")
        if not mid or not mid.startswith("map"):
            continue
        det = _attr(tag, "data-detail-url") or ""
        fid = _attr(tag, "data-floor-id")
        fid2 = re.search(r"floorId=(\d+)", cv)
        mei = _attr(tag, "data-shop-name") or (
            cv.split("shopName=")[-1].split("/")[0] if "shopName=" in cv else "")
        kigou = (KIGOU.match(mid).group(1) if KIGOU.match(mid) else "")
        d = {
            "map_id_candidate": mid,          # **場所の側の候補。確定IDではない**
            "tatemono_kigou": kigou,          # **記号のまま。名前に直さない**
            "floor_id": fid or (fid2.group(1) if fid2 else None),
            "mei": mei,
        }
        sid = DETAIL.search(det)
        if sid:
            mise.append(dict(d, shop_source_id=sid.group(1),   # **店のID**
                             kana=_attr(tag, "data-sub-search") or "",
                             betsumei=_attr(tag, "data-sub-two-search") or "",
                             keisai="掲載されていた"))
        else:
            kyoyou.append(dict(d, shurui=bunrui(mei)))
    return {"mise": mise, "kyoyou": kyoyou}


def kazoeru(d):
    """map_id_candidate を分ける。**「空き区画」とは読まない**（統括の指示）。"""
    import collections
    bymap = collections.defaultdict(set)
    for r in d["mise"]:
        bymap[r["map_id_candidate"]].add(r["shop_source_id"])
    for r in d["kyoyou"]:
        bymap.setdefault(r["map_id_candidate"], set())
    byshop = collections.defaultdict(set)
    for r in d["mise"]:
        byshop[r["shop_source_id"]].add(r["map_id_candidate"])

    ichitai1 = [k for k, v in bymap.items() if len(v) == 1]
    fukusuu_mise = {k: sorted(v) for k, v in bymap.items() if len(v) > 1}
    mise_nashi = [k for k, v in bymap.items() if not v]
    fukusuu_map = {k: sorted(v) for k, v in byshop.items() if len(v) > 1}

    shurui = collections.Counter(r["shurui"] for r in d["kyoyou"])
    return {
        "版": NUKI_VERSION,
        "店の数": len(byshop),
        "map_id_candidate の数": len(bymap),
        "店と1対1": len(ichitai1),
        "同じ map に複数の店": fukusuu_mise,
        "1店に複数の map": fukusuu_map,
        "店と結びついていない map": len(mise_nashi),
        "結びついていないものの語の分け": dict(shurui),
        "館の記号": dict(collections.Counter(
            r["tatemono_kigou"] for r in d["mise"] + d["kyoyou"])),
        "階の種類": len({r["floor_id"] for r in d["mise"] if r["floor_id"]}),
    }


def zukei_ga_haitteinaika(d) -> list:
    """**図形が出力に混ざっていないか。** 混ざっていたら名前を返す。

    **捨てると決めたものは、捨てたことを毎回確かめる**（言うだけにしない）。
    """
    moji = json.dumps(d, ensure_ascii=False)
    return [z for z in ZUKEI if z in moji]


def houkoku(d, kazu, hiduke, moto):
    a = [].append
    a("# フロアのページから、識別子と属性だけを抜いた記録")
    a("")
    a(f"{hiduke}。**取りに行っていない。** 保存済みの1枚を読んだだけ。")
    a(f"読んだもの：`{moto}`（抜き方の版 `{NUKI_VERSION}`）")
    a("")
    a("**図形・画像は1つも入っていない**（座標・`d`・`points` を読んでいない）。")
    a("**店の名前も、この記録には入らない**（金庫の側にだけ入る）。")
    a("")
    a("| | 数 |")
    a("|---|---:|")
    a(f"| 店（`shop_source_id`） | **{kazu['店の数']}** |")
    a(f"| `map_id_candidate` | **{kazu['map_id_candidate の数']}** |")
    a(f"| └ 店と1対1 | {kazu['店と1対1']} |")
    a(f"| └ 同じ map に複数の店 | {len(kazu['同じ map に複数の店'])} |")
    a(f"| └ **店と結びついていない** | **{kazu['店と結びついていない map']}** |")
    a(f"| 1店に複数の map | {len(kazu['1店に複数の map'])} |")
    a(f"| 階の種類（`floor_id`） | {kazu['階の種類']} |")
    a("")
    a("**⚠ 「店と結びついていない数」を「空き区画の数」と読まない**（統括の指示）。")
    a("語で分けると、こうなっている。**判定はしていない。**")
    a("")
    a("| 語の分け | 数 |")
    a("|---|---:|")
    for k, v in sorted(kazu["結びついていないものの語の分け"].items(),
                       key=lambda x: -x[1]):
        a(f"| {k} | {v} |")
    a("")
    a("**館の記号**（**記号のまま。名前に直していない**）")
    a("")
    for k, v in sorted(kazu["館の記号"].items(), key=lambda x: -x[1]):
        a(f"  - `{k}` {v}")
    a("")
    a("## この段が言わないこと")
    a("")
    a("- **`map_id_candidate` を区画IDと呼んでいない。** 候補のまま")
    a("- **空き区画の数を出していない**")
    a("- **座標から地図を描いていない**")
    a("- **店の名前を、この記録に入れていない**")
    a("")
    return "\n".join(a.__self__)


def main(argv=None):
    p = argparse.ArgumentParser(
        description="フロアのページから識別子と属性だけを抜く。取りに行かない")
    p.add_argument("moto", help="保存済みのHTML（**取りに行かない**）")
    p.add_argument("--ctype", default="text/html; charset=utf-8")
    p.add_argument("--json", default="", help="抜いた結果の置き場（**金庫の側**）")
    a = p.parse_args(argv)

    michi = Path(a.moto)
    if not michi.exists():
        print(f"もとのHTMLが無い: {michi}", file=sys.stderr)
        return 1
    d = chushutsu(michi.read_bytes(), a.ctype)

    warui = zukei_ga_haitteinaika(d)
    if warui:
        print(f"**図形が混ざっている**: {warui}", file=sys.stderr)
        return 1

    kazu = kazoeru(d)
    KIROKU.parent.mkdir(parents=True, exist_ok=True)
    KIROKU.write_text(houkoku(d, kazu, today(), michi.name), encoding="utf-8")
    if a.json:
        Path(a.json).parent.mkdir(parents=True, exist_ok=True)
        Path(a.json).write_text(
            json.dumps({"hi": today(), "版": NUKI_VERSION, **d},
                       ensure_ascii=False, indent=1), encoding="utf-8")
    for k, v in kazu.items():
        if isinstance(v, dict) and len(v) > 6:
            v = f"{len(v)} 種類"
        print(f"  {k}: {v}")
    print(f"\n{KIROKU} に書いた")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
