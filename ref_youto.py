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
    # (名前, 見に行くページ（上から順に。1本目で zip が見つかればそこで止める）,
    #  zip のリンクを見分ける正規表現)
    # **1本目で空振りでも、そこで終わりにしない。** 一覧の作りが変わっていることが
    # あるので、上の階層も見て、何が置いてあるかを報告に残す（2026-09-19）
    ("A29", ["https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-A29-v2_1.html",
             "https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-A29.html",
             "https://nlftp.mlit.go.jp/ksj/index.html"],
     re.compile(r"A29[-_][^\"']*?_(\d{2})[_.][^\"']*\.zip", re.I)),
    # ISJ の `/isj/` は「位置参照情報**とは**」の説明ページで、配っていない。
    # 配り口は、そのページ自身が載せていた `_choose_method.cgi`。
    # **決め打ちではなく、1回目の報告が持って帰った URL**（2026-09-19）
    ("ISJ", ["https://nlftp.mlit.go.jp/cgi-bin/isj/dls/_choose_method.cgi",
             "https://nlftp.mlit.go.jp/isj/",
             "https://nlftp.mlit.go.jp/isj/index.html"],
     re.compile(r"(\d{2})000[^\"']*\.zip", re.I)),
]

# 1ファイルの上限。これを超えたら落とさずに報告だけする（ディスクは有限）
MAX_ZIP = 200_000_000
BUDGET = 700_000_000     # 1回の実行で落とす合計の上限


def get(url, limit, meta=None):
    """取ってくる。`meta` を渡すと、最後のURL・状態・型をそこに書く。

    **「見つからなかった」だけでは、次に何をすればいいか分からない。**
    どこに飛ばされたのか、何が返ってきたのかを持って帰る（2026-09-19）。
    """
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        if r.status in (429, 503):
            raise RuntimeError(f"HTTP {r.status}。相手が混んでいる。やめる（3.4）")
        if meta is not None:
            meta["status"] = r.status
            meta["final_url"] = r.geturl()
            meta["content_type"] = r.headers.get("Content-Type") or ""
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


# 引用符で囲まれた「/ を含む .zip」を、どこにあっても拾う。
# **href だけを見ていたので 0 本だった**（2026-09-19）。実物はこうだった：
#   onclick="javascript:DownLd('3.77MB','A29-11_27_GML.zip',
#            '../data/A29/A29-11/A29-11_27_GML.zip' ,this);"
# / を含まないもの（引数の2つめのファイル名だけ）は落とす。
# 同じ onclick の3つめに、道つきのものが必ず入っている
_ZIP_ANY = re.compile(r"""['"]([^'"\s<>]*/[^'"\s<>]*\.zip)['"]""", re.I)


def _ver(url):
    """新しさの順に並べるための鍵。`A29-11` と `A29-19` を数として比べる。

    文字として並べると `A29-9` が `A29-11` より後ろに来る。
    いまは2桁しか無いが、桁が増えた日に黙って古いほうを選ばないようにする。
    """
    return [int(x) for x in re.findall(r"\d+", url)]


def links(html, base, pat):
    """一覧ページから、対象の府県の zip を拾う。URL は決め打ちしない。"""
    found = {}
    for m in _ZIP_ANY.finditer(html):
        href = urllib.parse.urljoin(base, m.group(1))
        g = pat.search(href)
        if not g:
            continue
        code = g.group(1)
        if code in PREFS and href not in found.get(code, []):
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


# 報告に**実物**を持って帰るための切り出し。
#
# 2026-09-19 の1回目は「cgi が3本ありました」と**数だけ**持って帰り、
# 中身を置いてきた。数は実物ではない。ページの実物は金庫に置くが、
# **金庫は統括のセッションから読めない**ので、次の一手が決められなかった。
# 共通仕様3.4「届かない相手のことは、報告に実物を持って帰る」。
#
# 出すのは government の公開ページの URL と見出しだけ。個人の情報は入らない。
EV_SLICE = 700          # 1か所あたりの切り出しの長さ
EV_MAX = 12             # 1種類あたりの本数


def _uniq(xs):
    seen, out = set(), []
    for x in xs:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def evidence(html, pat):
    """報告に載せる実物。zip の直リンクが無いときに、次の一手を決めるためのもの。"""
    out = []

    cgis = _uniq(re.findall(r'(?:href|action|src)="([^"]*\.cgi[^"]*)"', html, re.I))
    out.append(f"- **`.cgi` の実物 {len(cgis)} 本**（数ではなく URL そのもの）:")
    for c in cgis[:EV_MAX]:
        out.append(f"  - `{c[:200]}`")
    if not cgis:
        out.append("  - （無し）")

    srcs = _uniq(re.findall(r'<script[^>]+src="([^"]+)"', html, re.I))
    out.append(f"- **script の src {len(srcs)} 本**（どれが URL を組み立てているか）:")
    for c in srcs[:EV_MAX]:
        out.append(f"  - `{c[:200]}`")

    # 府県の印（#prefecture27 など）の**まわりの実物**。
    # ここに zip の id や data-* が置かれていることがある
    for code in PREFS:
        for m in re.finditer(r'(?:id|name)="[^"]*(?:prefecture|pref)[^"]*%s[^"]*"' % code,
                             html, re.I):
            i = max(0, m.start() - 200)
            out.append(f"- **{code} の印のまわり**（前後を切り出した実物）:")
            out.append("  ```html")
            for ln in html[i:m.start() + EV_SLICE].splitlines():
                ln = ln.strip()
                if ln:
                    out.append("  " + ln[:200])
            out.append("  ```")
            break

    # 中に書かれている script で、zip や download に触れているところ
    inline = re.findall(r'<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>', html, re.S | re.I)
    hit = [t for t in inline if re.search(r"zip|download|cgi|\.csv|shape", t, re.I)]
    out.append(f"- **中に書かれた script {len(inline)} 個、うち zip/download に触れるもの {len(hit)} 個**")
    for t in hit[:3]:
        t = re.sub(r"\s+", " ", t).strip()
        out.append("  ```js")
        out.append("  " + t[:EV_SLICE])
        out.append("  ```")

    # 探している形（都道府県コード付きの zip）が、href 以外の場所に無いか。
    # JS の文字列や data-* に入っていることがある
    anywhere = _uniq(m.group(0) for m in pat.finditer(html))
    out.append(f"- **ページ全体（href に限らず）で、探している形に当たるもの {len(anywhere)} 本**:")
    for a in anywhere[:EV_MAX]:
        out.append(f"  - `{a[:200]}`")
    if not anywhere:
        out.append("  - （無し。**配り方が変わった**と見てよい）")
    return out


def main():
    force = "--force" in sys.argv
    dry = "--dry-run" in sys.argv
    if fresh() and not (force or dry):
        print(f"用途地域の元データは{MAX_AGE_DAYS}日以内に取っている。取りに行かない")
        return 0

    lines = [f"# 用途地域の元データ（{runday.today()} に見た）", ""]
    got, spent, meta = [], 0, {"fetched_on": runday.today(), "files": []}
    os.makedirs(OUT, exist_ok=True)

    for name, pages, pat in SOURCES:
      for pi, page in enumerate(pages):
        tag = f"{name}" if pi == 0 else f"{name}-{pi}"
        ok, why = check_robots(page)
        lines.append(f"## {tag}  {page}")
        lines.append(f"- robots: {why}")
        if not ok:
            lines.append("- **取りに行かない**（共通仕様3.4）")
            lines.append("")
            continue
        pm = {}
        try:
            raw = get(page, 20_000_000, pm)
            html = raw.decode("utf-8", "replace")
        except Exception as e:
            lines.append(f"- 一覧ページが読めなかった：{type(e).__name__} {e}")
            lines.append("")
            continue
        time.sleep(WAIT)

        # **ページの実物を金庫に置く。** 手元からは届かないので、
        # ここで持って帰らないと、なぜ見つからなかったのかを調べられない
        os.makedirs(OUT, exist_ok=True)
        with open(os.path.join(OUT, f"{tag}-page.html"), "wb") as f:
            f.write(raw)
        title = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
        lines.append(f"- HTTP {pm.get('status')} / {pm.get('content_type')} / {len(raw):,} バイト")
        if pm.get("final_url") and pm["final_url"] != page:
            lines.append(f"- **飛ばされた先**: {pm['final_url']}")
        lines.append(f"- title: {(title.group(1).strip()[:80] if title else '（無し）')}")
        hrefs = re.findall(r'href="([^"]+)"', html, re.I)
        srcs = re.findall(r'src="([^"]+)"', html, re.I)
        forms = re.findall(r'<form[^>]*>', html, re.I)
        lines.append(f"- a/link の href {len(hrefs)} 本 ／ script などの src {len(srcs)} 本 ／ form {len(forms)} 個")
        for f_ in forms[:3]:
            lines.append(f"  - form: `{f_[:120]}`")
        # 拡張子の内訳。zip がどこにも無いのか、別の形なのかを見る
        ext = {}
        for h in hrefs:
            m = re.search(r"\.([a-z0-9]{2,5})(?:[?#]|$)", h, re.I)
            ext[(m.group(1).lower() if m else "（拡張子なし）")] = \
                ext.get((m.group(1).lower() if m else "（拡張子なし）"), 0) + 1
        top = sorted(ext.items(), key=lambda x: -x[1])[:10]
        lines.append(f"- href の拡張子: {top}")
        # 府県コードらしきものを含むリンクを、拡張子を問わず拾う
        cand = [h for h in hrefs if re.search(r"(^|[^0-9])(27|28)([^0-9]|$)", h)][:10]
        lines.append(f"- 27／28 を含む href（拡張子を問わず）{len(cand)} 本:")
        for h in cand:
            lines.append(f"  - `{h[:110]}`")
        lines.append(f"- ページの実物を置いた → `{tag}-page.html`（金庫）")
        # 金庫は統括のセッションから読めない。**次の一手に要るものは、
        # この公開側の報告に持って帰る**（共通仕様3.4）
        lines += evidence(html, pat)

        found = links(html, page, pat)
        if not found and pi + 1 < len(pages):
            lines.append("- ここでは見つからなかった。次のページも見る")
            lines.append("")
            time.sleep(WAIT)
            continue
        all_zip = len(re.findall(r'href="[^"]+\.zip"', html, re.I))
        lines.append(f"- ページの中の zip リンク（全部）: {all_zip} 本")
        for code, label in PREFS.items():
            urls = found.get(code) or []
            lines.append(f"- {label}（{code}）: {len(urls)} 本")
            if not urls:
                lines.append("  - **見つからなかった。ページの作りが変わったかもしれない**")
                continue
            # 候補を全部出す。**どの年のものがあるか**が分からないと、
            # 「いちばん新しい」を選んだことを確かめられない
            for u in sorted(urls, key=_ver):
                lines.append(f"  - 候補: `{u}`")
            url = sorted(urls, key=_ver)[-1]      # いちばん新しいもの（数として比べる）
            lines.append(f"  - **選んだ**（いちばん新しい）:")
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
        break

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
