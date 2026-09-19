#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用途地域のポリゴンと、住所→座標の対応表を国交省から取ってくる（取るだけ）。

  国土数値情報 A29 用途地域        https://nlftp.mlit.go.jp/ksj/
  位置参照情報 街区レベル（大字・丁目レベルも） https://nlftp.mlit.go.jp/isj/

**このスクリプトは取ってくるだけで、何にも当てない。**
落ちてくる中身（ファイル構成・属性名・座標系・番地の粒度）を、
実物を見てから決めるため。見ていないものに当てるコードは書けない。

置き場は金庫（`data/ref/youto/`）。生データなので公開側には置かない（9節）。

    python3 ref_youto.py            # 90日以内に取っていれば取りに行かない
    python3 ref_youto.py --force    # いますぐ取り直す
    python3 ref_youto.py --dry-run  # 一覧ページだけ見て、リンクを報告する

共通仕様3.4のとおり：robots.txt を見る、名乗る、同じ相手に5秒あける、同時1本。
429/503/待機列が返ったら、その場でやめる（リトライで突破しない）。

なぜ要るか：用途地域は 4,809件の届出のうち 1,231件にしか無い。
場所（番地キー）で数えると 1,551 か所に1件も無い（兵庫661・大阪890）。
公報の本文にも書かれていないことを確かめた（2026-09-19）。

**取れたものは `zoning` には入れない。** 届出が言ったことと、いまの地図が
言うことは別（共通仕様3.5）。入れるなら `zoning_now` と `zoning_asof`。
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
from common.fetch import UA, WAIT, check_robots   # noqa: E402

OUT = os.path.join(HERE, "data", "raw", "youto")   # 金庫（private）。取ってきた生データ（9節）
META = os.path.join(OUT, "meta.json")
REPORT = os.path.join(HERE, "data", "ref", "youto-report.md")
MAX_AGE_DAYS = 90
TIMEOUT = 120

# 取る対象。いま扱っている2府県だけ。増やすときはここに足す
PREFS = {"27": "大阪府", "28": "兵庫県"}

SOURCES = [
    # (名前, 一覧ページ, zip のリンクを見分ける正規表現)
    ("A29", "https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-A29-v2_1.html",
     re.compile(r"A29[-_][^\"']*?_(\d{2})[_.][^\"']*\.zip", re.I)),
    ("ISJ", "https://nlftp.mlit.go.jp/isj/",
     re.compile(r"(\d{2})000[^\"']*\.zip", re.I)),
]

# 1ファイルの上限。これを超えたら落とさずに報告だけする（ディスクは有限）
MAX_ZIP = 200_000_000
BUDGET = 700_000_000     # 1回の実行で落とす合計の上限


def get(url, limit):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        if r.status in (429, 503):
            raise RuntimeError(f"HTTP {r.status}。相手が混んでいる。やめる（3.4）")
        data = r.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f"{limit} バイトを超えた")
    return data


def head(url):
    """落とす前に大きさを聞く。大きすぎるものを掴まないため。"""
    req = urllib.request.Request(url, headers={"User-Agent": UA}, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return int(r.headers.get("Content-Length") or 0)
    except Exception:
        return 0


def links(html, base, pat):
    """一覧ページから、対象の府県の zip へのリンクを拾う。URL は決め打ちしない。"""
    found = {}
    for m in re.finditer(r'href="([^"]+\.zip)"', html, re.I):
        href = urllib.parse.urljoin(base, m.group(1))
        g = pat.search(href)
        if not g:
            continue
        code = g.group(1)
        if code in PREFS:
            found.setdefault(code, []).append(href)
    return found


def fresh():
    if not os.path.exists(META):
        return False
    try:
        with open(META, encoding="utf-8") as f:
            d = date.fromisoformat(json.load(f)["fetched_on"])
    except Exception:
        return False
    return (runday.today_date() - d).days < MAX_AGE_DAYS


def main():
    force = "--force" in sys.argv
    dry = "--dry-run" in sys.argv
    if fresh() and not (force or dry):
        print(f"用途地域の元データは{MAX_AGE_DAYS}日以内に取っている。取りに行かない")
        return 0

    lines = [f"# 用途地域の元データ（{runday.today()} に見た）", ""]
    got, spent, meta = [], 0, {"fetched_on": runday.today(), "files": []}
    os.makedirs(OUT, exist_ok=True)

    for name, page, pat in SOURCES:
        ok, why = check_robots(page)
        lines.append(f"## {name}  {page}")
        lines.append(f"- robots: {why}")
        if not ok:
            lines.append("- **取りに行かない**（共通仕様3.4）")
            lines.append("")
            continue
        try:
            html = get(page, 20_000_000).decode("utf-8", "replace")
        except Exception as e:
            lines.append(f"- 一覧ページが読めなかった：{type(e).__name__} {e}")
            lines.append("")
            continue
        time.sleep(WAIT)

        found = links(html, page, pat)
        all_zip = len(re.findall(r'href="[^"]+\.zip"', html, re.I))
        lines.append(f"- ページの中の zip リンク（全部）: {all_zip} 本")
        for code, label in PREFS.items():
            urls = found.get(code) or []
            lines.append(f"- {label}（{code}）: {len(urls)} 本")
            if not urls:
                lines.append("  - **見つからなかった。ページの作りが変わったかもしれない**")
                continue
            # いちばん新しそうなもの（URL を並べて末尾）を1本だけ
            url = sorted(urls)[-1]
            size = head(url)
            time.sleep(WAIT)
            lines.append(f"  - {url}")
            lines.append(f"  - 大きさ: {size:,} バイト")
            if dry:
                continue
            if size > MAX_ZIP:
                lines.append(f"  - **大きすぎるので落とさない**（上限 {MAX_ZIP:,}）")
                continue
            if spent + (size or MAX_ZIP) > BUDGET:
                lines.append("  - **今回の合計の上限に達した。次回に回す**")
                continue
            try:
                data = get(url, MAX_ZIP)
            except Exception as e:
                lines.append(f"  - 落とせなかった：{type(e).__name__} {e}")
                time.sleep(WAIT)
                continue
            time.sleep(WAIT)
            fn = os.path.join(OUT, f"{name}-{code}.zip")
            with open(fn, "wb") as f:
                f.write(data)
            spent += len(data)
            got.append(fn)
            meta["files"].append({"name": name, "pref": code, "url": url,
                                  "bytes": len(data), "file": os.path.basename(fn)})
            lines.append(f"  - 落とした → `{os.path.basename(fn)}`（{len(data):,} バイト）")
            # 中に何が入っているかを書き出す。**次の段はこれを読んでから書く**
            try:
                import zipfile
                with zipfile.ZipFile(fn) as z:
                    names = z.namelist()
                lines.append(f"  - 中身 {len(names)} 件: " + ", ".join(n[-40:] for n in names[:12]))
            except Exception as e:
                lines.append(f"  - 中身が読めなかった：{type(e).__name__} {e}")
        lines.append("")

    lines += ["## 次にやること", "",
              "この報告を読んでから、当てるコードを書く（属性名・座標系・番地の粒度を見る）。",
              "**取れたものは `zoning` には入れない。** 届出が言ったことと、いまの地図が",
              "言うことは別（共通仕様3.5）。入れるなら `zoning_now` と `zoning_asof`。", ""]

    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    if not dry:
        with open(META, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=1)
    print("\n".join(lines))
    print(f"→ {REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
