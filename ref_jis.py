#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""総務省の「全国地方公共団体コード」を取ってきて data/ref/jis-codes.json にする。

  https://www.soumu.go.jp/denshijiti/code.html

共通仕様4節の city_code の元。政府標準利用規約（CC BY 4.0 互換）。
中身は合併のとき以外は変わらないので、90日以内に取っていれば取りに行かない。
取りに行くときは共通仕様3.4のとおり：robots.txt を見る、名乗る、5秒あける。

  python3 ref_jis.py           # 90日たっていれば取り直す
  python3 ref_jis.py --force   # いますぐ取り直す
"""

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "common"))
import runday
from common.fetch import UA, WAIT, check_robots, decode_html   # noqa: E402
from common import hikisu   # 知らない引数で止める（3.4）
import xlsx                                        # noqa: E402

PAGE = "https://www.soumu.go.jp/denshijiti/code.html"
REF = os.path.join(HERE, "data", "ref")
OUT = os.path.join(REF, "jis-codes.json")
XLSX = os.path.join(REF, "jis-codes.xlsx")
META = os.path.join(REF, "jis-codes.meta.json")
MAX_AGE_DAYS = 90
TIMEOUT = 60


def get(url, limit=30_000_000):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        data = r.read(limit + 1)
    if len(data) > limit:
        raise ValueError("大きすぎる")
    return data


def find_code_file(html, base):
    """ページの中から、市区町村コードの Excel へのリンクを探す。候補を全部返す（先頭が本命）。"""
    cands = []
    for m in re.finditer(r'<a[^>]+href="([^"]+\.xlsx?)"[^>]*>(.*?)</a>', html, re.S | re.I):
        href, label = m.group(1), re.sub(r"<[^>]+>", "", m.group(2))
        ctx = html[max(0, m.start() - 300):m.start()]
        score = 0
        for w, pt in (("市区町村コード", 3), ("都道府県コード", 2), ("全国", 1), ("一覧", 1)):
            if w in label or w in ctx:
                score += pt
        if "政令" in label or "廃置" in label or "変更" in label:
            score -= 2
        cands.append((score, urllib.parse.urljoin(base, href), label.strip()))
    cands.sort(key=lambda x: -x[0])
    return cands


def _parent_city(code5, city, out):
    """政令指定都市の区の行なら、親の市の名前。そうでなければ空。

    区の行は名前が「区」で終わり「市」を含まない（「北区」）。親は、コードの
    先頭3桁が同じで直前に出てきた市（大阪市 27100 の区は 271xx、堺市 27140 の区は 2714x。
    行はコード順なので「いちばん最近の市」で堺と大阪を取り違えない）。
    コードの数字の並びから区かどうかを当てるのはやめた。住吉区 27120 のように
    0 で終わる区があり、それを市と読み違える。
    """
    if not city.endswith("区") or "市" in city:
        return ""
    for row in reversed(out):
        if row["code"][:3] == code5[:3] and row["city"].endswith("市"):
            return row["city"]
    return ""


def rows_to_codes(rows):
    """Excel の行から [{"code": "27127", "pref": "大阪府", "city": "大阪市北区"}] を作る。

    団体コードは6桁（末尾は検査数字）。5桁が全国地方公共団体コード。
    都道府県の行（市区町村名が空）は入れない。
    政令指定都市の区は、シートによって「北区」とだけ書いてあるものと
    「大阪市北区」と書いてあるものがある。前者は直前の市の名前を頭に付ける。
    """
    out = []
    ic = ip = im = None
    for row in rows:
        cells = [str(c).strip() for c in row]
        if ic is None:
            if any("団体コード" in c for c in cells):
                ic = next(i for i, c in enumerate(cells) if "団体コード" in c)
                ip = next(i for i, c in enumerate(cells) if "都道府県名" in c and "カナ" not in c)
                im = next(i for i, c in enumerate(cells) if "市区町村名" in c and "カナ" not in c)
            continue
        if len(cells) <= max(ic, ip, im):
            continue
        code, pref, city = cells[ic], cells[ip], cells[im]
        if not re.fullmatch(r"[0-9]{6}", code) or not pref or not city:
            continue
        code5 = code[:5]
        parent = _parent_city(code5, city, out)
        if parent:
            city = parent + city
        out.append({"code": code5, "pref": pref, "city": city})
    return out


def fresh():
    if not (os.path.exists(OUT) and os.path.exists(META)):
        return False
    try:
        with open(META, encoding="utf-8") as f:
            d = date.fromisoformat(json.load(f)["fetched_on"])
    except Exception:
        return False
    return (runday.today_date() - d).days < MAX_AGE_DAYS


def main():
    hikisu.check({"--force"}, tsukaikata="使い方: python3 ref_jis.py [--force]")
    force = "--force" in sys.argv
    if fresh() and not force:
        print(f"jis-codes.json は{MAX_AGE_DAYS}日以内に取っている。取りに行かない")
        return 0
    ok, why = check_robots(PAGE)
    if not ok:
        print(f"{why}。取りに行かない（共通仕様3.4）")
        return 0
    # **utf-8 と決め打ちしていた。総務省は Shift_JIS。**
    # meta の label が "Excel\ufffdt\ufffd@\ufffdC\ufffd\ufffd" と化けていて、
    # しかも find_code_file() はその化けた文字列に「政令」「廃置」「変更」で
    # 点を付けていた。**正しいものが選ばれていたのは href の形のおかげで、
    # 理由が無かった**（2026-09-19、開発系が写しに来て見つけた）
    html, enc = decode_html(get(PAGE))
    print(f"ページは {enc} として読んだ")
    time.sleep(WAIT)
    cands = find_code_file(html, PAGE)
    if not cands:
        print("市区町村コードの Excel へのリンクがページに見つからなかった。ページの作りが変わった")
        return 1
    print("候補:", [(s, l[:30], u[-24:]) for s, u, l in cands[:4]])
    score, url, label = cands[0]
    data = get(url)
    time.sleep(WAIT)
    os.makedirs(REF, exist_ok=True)
    with open(XLSX, "wb") as f:
        f.write(data)
    rows = []
    for name, rs in xlsx.read(XLSX).items():
        rows += rs
    codes = rows_to_codes(rows)
    if len(codes) < 1500:
        print(f"読めた市区町村が {len(codes)} 件しかない（全国で約1,900のはず）。書き出さない")
        return 1
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(codes, f, ensure_ascii=False, indent=0)
    with open(META, "w", encoding="utf-8") as f:
        json.dump({"fetched_on": runday.today(), "source_url": url, "label": label,
                   "page": PAGE, "rows": len(codes)}, f, ensure_ascii=False, indent=1)
    print(f"jis-codes.json を書いた：{len(codes)} 市区町村（{label}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
