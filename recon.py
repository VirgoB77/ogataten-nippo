#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""大店立地法の届出ページを偵察する。

いきなり全部を集めようとすると、たいてい最初のページで詰まる。
なので先に「そのページが機械で読める形かどうか」だけを確かめる。

やること
  1. robots.txt を見て、取りに行ってよいか確かめる
  2. ページを取得して data/raw/<id>/<日付>.html に残す
  3. 中身が「HTMLの表」か「PDFの並び」かを判定して、レポートに書く

判定の見方
  表        … HTMLの表がある。いちばん楽。すぐ自動化できる
  Excel     … xlsx/xls が置いてある。実はいちばん楽なこともある
  PDF       … PDFのリンクが並んでいる。中を読むのに一手間かかる
  わからない … 自分の目で見に行く必要がある

Python 3 の標準ライブラリだけで動く。GitHub Actions でそのまま動く。
"""

import html
import json
import glob
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from html.parser import HTMLParser

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "common"))
import runday
from common.fetch import UA, check_robots, is_busy  # 名乗り・robots・混雑判定は common/fetch.py（共通仕様3.4）
from common import hikisu   # 知らない引数で止める（3.4）
from common import kado     # 取りに行く前の門。カードid = sources.json の id（共通指示書1）
WAIT = 5          # 同じ相手に続けて出すときに空ける秒数。迷惑をかけない
TIMEOUT = 40

# robots.txt を読む urllib.robotparser はタイムアウトを指定できず、
# 既定のままだと相手が黙ったときに永久に待つ。ソケット側で縛っておく。
socket.setdefaulttimeout(TIMEOUT)


# ---------------------------------------------------------------- 文字コード

def decide_charset(raw, content_type):
    """Content-Type と meta タグから文字コードを決める。

    自治体のページは UTF-8 のことが多いが、古いものは Shift_JIS が残っている。
    """
    m = re.search(r"charset=([\w\-]+)", content_type or "", re.I)
    if m:
        return m.group(1)
    head = raw[:4096].decode("ascii", "ignore")
    m = re.search(r'charset=["\']?([\w\-]+)', head, re.I)
    if m:
        return m.group(1)
    return "utf-8"


def ext_of(raw, content_type=""):
    """中身から拡張子を決める。**名前が中身と違うものを作らない。**

    2026-09-19、`data/raw/tokyo-ref/` に `%PDF` で始まる `.html` が40枚あった。
    バイトは無事だが、**名前が嘘をついている。** `*.html` を読む側が
    黙って読み違える（9節「名前が変わったことと、中身が変わったことは違う」）。

    見出し（Content-Type）ではなく**中身の先頭**を先に見る。
    見出しを付け忘れるサーバーがあるため。
    """
    head = raw[:5]
    if head[:4] == b"%PDF":
        return ".pdf"
    if head[:2] == b"PK":
        return ".zip"          # xlsx / docx もこれ。中を開くまで区別しない
    if head[:2] == b"\x1f\x8b":
        return ".gz"
    ct = (content_type or "").lower()
    for key, ext in (("pdf", ".pdf"), ("zip", ".zip"),
                     ("excel", ".zip"), ("sheet", ".zip"),
                     ("csv", ".csv"), ("json", ".json"), ("xml", ".xml")):
        if key in ct:
            return ext
    return ".html"


def to_text(raw, content_type):
    cs = decide_charset(raw, content_type)
    for enc in (cs, "utf-8", "cp932", "euc_jp"):
        try:
            return raw.decode(enc), enc
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", "replace"), "utf-8(replace)"


# ---------------------------------------------------------------- HTML を読む

class Scanner(HTMLParser):
    """表とリンクだけを拾う。中身の意味までは見ない。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []          # 表ごとの {rows, cols, header}
        self.links = []           # (href, 文字列)
        self._tstack = []
        self._row_cells = 0
        self._cell_buf = None
        self._href = None
        self._atext = []

    # -- 表
    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "table":
            self._tstack.append({"rows": 0, "cols": 0, "header": []})
        elif tag == "tr" and self._tstack:
            self._row_cells = 0
        elif tag in ("td", "th") and self._tstack:
            self._row_cells += 1
            self._cell_buf = []
        elif tag == "a":
            self._href = d.get("href")
            self._atext = []

    def handle_endtag(self, tag):
        if tag == "table" and self._tstack:
            self.tables.append(self._tstack.pop())
        elif tag == "tr" and self._tstack:
            t = self._tstack[-1]
            t["rows"] += 1
            t["cols"] = max(t["cols"], self._row_cells)
            if t["rows"] == 1:
                pass  # ヘッダは td/th の中身を集めた時点で入れてある
        elif tag in ("td", "th") and self._tstack and self._cell_buf is not None:
            t = self._tstack[-1]
            text = "".join(self._cell_buf).strip()
            if t["rows"] == 0 and len(t["header"]) < 12:
                t["header"].append(text[:24])
            self._cell_buf = None
        elif tag == "a" and self._href is not None:
            self.links.append((self._href, "".join(self._atext).strip()[:60]))
            self._href = None

    def handle_data(self, data):
        if self._cell_buf is not None:
            self._cell_buf.append(data)
        if self._href is not None:
            self._atext.append(data)


# ---------------------------------------------------------------- 取りに行く

# 本文の範囲を示す印。自治体の CMS がページに入れていることがある。
# 印が無いページでは、ページ全体を見る（今までどおり）
HONBUN_HAJIME = ("メインコンテンツここから", "本文ここから")
HONBUN_OWARI = ("メインコンテンツここまで", "本文ここまで")


def honbun(page):
    """リンクを選ぶ範囲を、本文の印のあいだに絞る。**横の欄を拾わない。**

    2026-09-24、堺市で分かった。本文の外の「このページも読まれています」の欄は、
    見た人の動きで**日ごとに中身が変わる。**そこに年度のページが出た日だけ
    それが先に並び、上限の枠の使われ方が変わって、取れる年度が日ごとに揺れた。
    中規模のページからは、この欄を通って大規模の年度ページへ迷い込んでいた。

    印が片方でも無ければ、ページ全体を返す（印の無いサイトは、今までどおり）。
    """
    hajime = [page.find(m) for m in HONBUN_HAJIME if m in page]
    if not hajime:
        return page
    a = min(hajime)
    owari = [i for i in (page.find(m, a) for m in HONBUN_OWARI) if i > a]
    if not owari:
        return page
    return page[a:max(owari)]


def follow_links(page, base_url):
    """目次ページから、年度別ページなど「その先」のリンクを選ぶ。

    堺市や和泉市のように、入口は目次だけで、実物は1階層下にあることが多い。
    ここで拾わないと「表が無いページ」に見えてしまう。

    **選ぶのは本文の中のリンクだけ**（`honbun()`）。
    """
    out, seen = [], set()
    for m in re.finditer(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', honbun(page), re.S | re.I):
        label = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group(2))).strip()
        if not label or len(label) > 60:
            continue
        if FOLLOW_SKIP.search(label):
            continue
        if not (FOLLOW_TEXT.search(label) and FOLLOW_TOPIC.search(label)):
            continue
        url = urllib.parse.urljoin(base_url, html.unescape(m.group(1)))
        if not url.startswith("http") or url in seen or url == base_url:
            continue
        # 同じサイトの中だけ辿る。よそへ出ていかない
        if urllib.parse.urlparse(url).netloc != urllib.parse.urlparse(base_url).netloc:
            continue
        seen.add(url)
        out.append((url, label))
    return out


def slug_of(url):
    """辿った先を保存するときのファイル名の一部。"""
    path = urllib.parse.urlparse(url).path
    name = re.sub(r"[^A-Za-z0-9._-]", "_", path.strip("/").replace("/", "-"))
    return (name or "page")[-60:]


# ---------------------------------------------------------------- その日の取得が、そろっていたか

def _owari_ga_aru(raw):
    """文書の終わりの印（</html>）があるか。途中で切れた保存を「そろった」と名乗らない。"""
    return b"</html>" in raw.lower()


def _hozon_saki(d, day, url):
    """辿った先を、その日に保存したファイル（`<日付>--<slug><拡張子>`）。無ければ None。"""
    mae = f"{day}--{slug_of(url)}"
    try:
        names = sorted(os.listdir(d))
    except FileNotFoundError:
        return None
    for name in names:
        if name.startswith(mae) and name[len(mae):len(mae) + 1] in ("", "."):
            return os.path.join(d, name)
    return None


def kanzen_hantei(src, day, raw_dir=None):
    """**その日の取得が、必要な範囲をそろえていたか**を、保存したものだけで決める。

    2026-09-24、堺市で分かった。2階層目の上限（FOLLOW_MAX_2）で年度のページを
    黙って切った日に、そのページの届出が「その日に無かった＝消えた」と数えられていた。
    相手の目次には毎日載っていた。**取らなかったことと、相手に無いことは別。**

    だから、差分の段が件数から推し量るのではなく、**取得の段の事実**で決める。
    上限で切った・取れなかった・保存できなかった、のどれも
    「保存が無い」という1つの事実に出るので、**保存を数えれば足りる。**
    取っていないページを推測で埋めない。

        入口に表がある     入口ページが最後まで（</html> まで）保存できていれば、そろった
        入口が目次         本文の中のリンク（`follow_links()`）の先を全部たどり、
                           その先も目次なら、もう一段（取得の段と同じ2段まで）。
                           **上限は掛けない。**必要なページが1本でも保存されていなければ、
                           そろっていない

    返り値は dict。**その日の入口が保存されていなければ None**（その日は観測が無い）。

        kanzen    True（そろった）／False（そろっていない）／None（ここでは確かめない）
        riyuu     ひとことの理由
        hitsuyou  辿るべきだったページの数（入口を除く）
        tarinai   保存が無かったページの見出し（先頭10件まで）
        tsukau    取り出しに使ってよい保存ファイル（入口と、辿るべきだったページ）。
                  本文の外の欄から迷い込んで保存したページは入らない
    """
    d = os.path.join(raw_dir or os.path.join(HERE, "data", "raw"), src["id"])
    try:
        names = sorted(os.listdir(d))
    except FileNotFoundError:
        return None
    iriguchi = next((os.path.join(d, n) for n in names
                     if n.startswith(day) and n[len(day):len(day) + 1] == "."), None)
    if not iriguchi:
        return None
    out = {"kanzen": None, "riyuu": "", "hitsuyou": 0, "tarinai": [], "tsukau": [iriguchi]}
    if not iriguchi.endswith((".html", ".htm")):
        out["riyuu"] = "入口が HTML でない。そろったかを、ここでは確かめない"
        return out
    with open(iriguchi, "rb") as f:
        raw = f.read()
    if not _owari_ga_aru(raw):
        out.update(kanzen=False, riyuu="入口ページの終わりの印（</html>）が無い。途中で切れた疑い")
        return out
    text, _ = to_text(raw, "")
    if analyze(text, src["url"])["verdict"] != "わからない":
        out.update(kanzen=True, riyuu="入口ページに表があり、最後まで保存できている")
        return out

    known, queue, tarinai = {src["url"]}, [], []

    def narabu(links, depth):
        for u, lb in links:
            if u not in known:
                known.add(u)
                queue.append((u, lb, depth))

    narabu(follow_links(text, src["url"]), 1)
    while queue:
        u, lb, depth = queue.pop(0)
        out["hitsuyou"] += 1
        p = _hozon_saki(d, day, u)
        if not p:
            tarinai.append(lb)
            continue
        with open(p, "rb") as f:
            raw2 = f.read()
        html2 = p.endswith((".html", ".htm"))
        if html2 and not _owari_ga_aru(raw2):
            tarinai.append(f"{lb}（途中で切れた疑い）")
            continue
        out["tsukau"].append(p)
        if depth < 2 and html2:
            t2, _ = to_text(raw2, "")
            if analyze(t2, u)["verdict"] == "わからない":
                narabu(follow_links(t2, u), depth + 1)
    if tarinai:
        out.update(kanzen=False, tarinai=tarinai[:10],
                   riyuu=(f"辿るべきページ {out['hitsuyou']}本のうち {len(tarinai)}本の保存が無い"
                          "（上限で切った・取れなかった・保存できなかった）"))
    else:
        out.update(kanzen=True, riyuu=f"辿るべきページ {out['hitsuyou']}本をすべて保存できている")
    return out


# check_robots は common/fetch.py に移した。こちらの名乗りで取り、429/503 を「許可」に倒さない


def fetch(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ja",
    })
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.status, r.headers.get("Content-Type", ""), r.read()


# ---------------------------------------------------------------- 判定する

KEYWORDS = ["新設", "変更", "廃止", "縦覧", "届出", "店舗面積", "開店"]

# 目次ページのリンク文字から、その先に一覧がありそうなものを選ぶ。
# 「令和N年度」だけを手がかりにすると、人権セミナーや中小企業支援の
# ページまで拾ってしまったので、届出か縦覧の語が入っていることを必須にする。
# 「届出」だけだと、アスベスト・騒音・水道・駐車場など市のあらゆる届出を
# 拾ってしまう（箕面市の窓口ページで実際に起きた）。
# 「届出か縦覧」であることに加えて、大規模小売店舗まわりの語が要る。
FOLLOW_TEXT = re.compile(r"届出|縦覧")
FOLLOW_TOPIC = re.compile(r"大規模|中規模|小売|大店|届出状況|縦覧状況|状況|第\s*\d+\s*条|年度")
# 様式のダウンロードや申請の入口に逃げないよう、明らかに違うものは弾く
FOLLOW_SKIP = re.compile(r"手引|様式|ワード|エクセル|\.doc|\.xls|要綱|申請書|"
                         r"お問い合わせ|電子申請|検索|一覧表示|ダウンロード")
FOLLOW_MAX = 12          # 1つの目次から辿る数の上限。相手に迷惑をかけないため
FOLLOW_MAX_2 = 4         # 2階層目はさらに絞る
FOLLOW_BUDGET = 32       # 1つの収集先で辿る総数の上限。堺市が25本必要だったので余裕をみた

# 相手ごとの頻度（共通仕様3.4）。sources.json の freq。無ければ毎日。
# 規約・案内・オープンデータの一覧のような、めったに変わらないページは四半期に1回でよい
FREQ_DAYS = {"daily": 0, "biweekly": 14, "quarterly": 90}


def last_saved(sid):
    """その収集先を最後に保存した日（data/raw/<id>/YYYY-MM-DD.*）。無ければ None。

    **拡張子で絞らない。** 2026-09-19 に「名前は中身から決める」に直したので、
    相手が PDF を返した日は `{日付}.pdf` になる。`.html` だけ見ていると
    **その日の分を「持っていない」と数えて、毎日取りに行く**（3.4 違反）。
    **直した日に、直したものを見ていた別の場所が壊れる**（9節）。
    """
    days = []
    for p in glob.glob(os.path.join(HERE, "data", "raw", sid, "????-??-??.*")):
        m = re.match(r"(\d{4}-\d{2}-\d{2})\.", os.path.basename(p))
        if m:
            days.append(m.group(1))
    if not days:
        return None
    y, mo, d = map(int, max(days).split("-"))
    return date(y, mo, d)


def analyze(text, base_url):
    s = Scanner()
    try:
        s.feed(text)
    except Exception as e:
        return {"error": f"HTMLの解析に失敗: {e}"}

    # 中身のある表だけを見る（2行2列以上）
    real = [t for t in s.tables if t["rows"] >= 2 and t["cols"] >= 2]
    real.sort(key=lambda t: t["rows"] * t["cols"], reverse=True)

    pdfs, excels = [], []
    for href, label in s.links:
        low = href.lower()
        full = urllib.parse.urljoin(base_url, href)
        if low.endswith(".pdf"):
            pdfs.append((full, label))
        elif low.endswith((".xlsx", ".xls", ".csv")):
            excels.append((full, label))

    found = [k for k in KEYWORDS if k in text]
    years = sorted(set(re.findall(r"(?:令和|平成)\s*\d{1,2}\s*年", text)))[:8]

    # 3行以上を「表」としていたが、それだと中身のある小さい表を見落とす。
    # 堺市の令和4年度の廃止は「見出し＋1件」の2行で、その1件が
    # 泉ヶ丘地区センター専門店街の閉店という立派な中身だった。
    # 行数ではなく、見出しに届出らしい項目が並んでいるかで見る。
    header_is_real = bool(real) and any(
        re.search(r"店舗|届出|縦覧|名称|所在地|設置者|面積|廃止|開店", h)
        for h in real[0]["header"])
    if real and (real[0]["rows"] >= 3 or (real[0]["rows"] >= 2 and header_is_real)):
        verdict = "表"
    elif excels:
        verdict = "Excel"
    elif len(pdfs) >= 3:
        verdict = "PDF"
    else:
        verdict = "わからない"

    return {
        "verdict": verdict,
        "tables": len(real),
        "biggest": real[0] if real else None,
        "pdf_count": len(pdfs),
        "pdf_sample": pdfs[:5],
        "excel_count": len(excels),
        "excel_sample": excels[:5],
        "keywords": found,
        "years": years,
        "links_total": len(s.links),
    }


# ---------------------------------------------------------------- レポート

def report_one(src, res):
    out = []
    out.append(f"### {src['name']}")
    out.append("")
    out.append(f"- URL: {src['url']}")
    if src.get("note"):
        out.append(f"- メモ: {src['note']}")

    if res.get("skipped"):
        out.append(f"- **結果: 取りに行かなかった（{res['skipped']}）**")
        out.append("")
        return "\n".join(out)

    if res.get("fetch_error"):
        out.append(f"- **結果: 取得できなかった — {res['fetch_error']}**")
        if res.get("busy_stop"):
            out.append(f"  - **HTTP {res['busy_stop']}（混んでいる）。この収集先は今回ここまで**（共通仕様3.4）")
        out.append("")
        return "\n".join(out)

    out.append(f"- robots.txt: {res['robots']}")
    out.append(f"- HTTP {res['status']} / {res['encoding']} / {res['bytes']:,} バイト")

    a = res["analysis"]
    if a.get("error"):
        out.append(f"- **{a['error']}**")
        out.append("")
        return "\n".join(out)

    out.append(f"- **判定: {a['verdict']}**")
    out.append(f"- 表 {a['tables']} 個 / PDFリンク {a['pdf_count']} 本 / Excel {a['excel_count']} 本")

    if a["biggest"]:
        b = a["biggest"]
        out.append(f"- いちばん大きい表: {b['rows']} 行 × {b['cols']} 列")
        if b["header"]:
            out.append(f"  - 見出しらしき行: {' | '.join(x for x in b['header'] if x)}")
    for label, items in (("PDF", a["pdf_sample"]), ("Excel", a["excel_sample"])):
        for url, text in items:
            out.append(f"  - {label}: {text or '(名前なし)'} → {url}")

    if a["keywords"]:
        out.append(f"- 出てきた言葉: {' / '.join(a['keywords'])}")
    if a["years"]:
        out.append(f"- 年度らしき表記: {' / '.join(a['years'])}")

    if res.get("followed"):
        cap = res.get("follow_capped")
        note = f"（{cap[0]}本見つかったが上限{cap[1]}本まで）" if cap else ""
        out.append(f"- **この先を辿った: {len(res['followed'])}本** {note}")
        for label, a2, depth, err in res["followed"]:
            mark = "  " * depth
            if err:
                out.append(f"  -{mark}{label[:34]} … 取れなかった（{err}）")
            else:
                extra = f" {a2['biggest']['rows']}行×{a2['biggest']['cols']}列" if a2.get("biggest") else ""
                pdf = f" PDF{a2['pdf_count']}本" if a2.get("pdf_count") else ""
                out.append(f"  -{mark}{label[:34]} … **{a2['verdict']}**{extra}{pdf}")
        if res.get("busy_stop") and not res.get("fetch_error"):
            out.append(f"  - **HTTP {res['busy_stop']}（混んでいる）。この収集先は今回ここまで**（共通仕様3.4）")
        elif res.get("budget_hit"):
            b, left = res["budget_hit"]
            out.append(f"  - （上限{b}本に達した。まだ{left}本残っている）")
    k = res.get("kanzen")
    if k:
        mark = {True: "そろった", False: "そろっていない", None: "確かめていない"}[k["kanzen"]]
        out.append(f"- **取得の完全性: {mark}**（{k['riyuu']}）")
        for lb in k["tarinai"]:
            out.append(f"  - 保存が無い: {lb[:40]}")
    out.append("")
    return "\n".join(out)


def main():
    with open(os.path.join(HERE, "sources.json"), encoding="utf-8") as f:
        sources = json.load(f)["sources"]

    # **知らない引数で止める**（common/hikisu.py）。打ち間違いが本番の収集になるのを防ぐ。
    #
    # **受け取るのは id だけではない。** 下の `only` は
    # `src["id"]` と `src["area"]` の**どちらとも**突き合わせている。
    # 2026-09-19 にここを id だけで作って、`recon.py hyogo` を落としていた
    # （監査 r1-36。毎朝の自動巡回は area が空なので無事だったが、
    # 手で `hyogo` `osaka` `ref` `youto` を指定する道が全部止まっていた）。
    #
    # **受け取る値は、実物（sources.json）から作る。手で並べない。**
    ukeru = {s["id"] for s in sources} | {
        s.get("area") for s in sources if s.get("area")}
    hikisu.check(ukeru,
                 tsukaikata="使い方: python3 recon.py [収集先のid または area]")
    only = sys.argv[1] if len(sys.argv) > 1 else None
    today = runday.today()
    raw_dir = os.path.join(HERE, "data", "raw")
    # **取りに行く前の門。** カードid = sources.json の id（共通指示書「この置き場の具体」）。
    K = kado.hajimeru(HERE, "ogataten-nippo", UA, today=runday.today())

    lines = [
        f"# 大店立地法 届出ページ 偵察レポート（{today}）",
        "",
        "「そのページが機械で読める形か」だけを見ている。",
        "判定が **表** か **Excel** なら自動化しやすい。**PDF** なら一手間、",
        "**わからない** なら自分の目で見に行く必要がある。",
        "",
    ]

    counts = {}

    def do_source(src, res):
        """1収集先ぶん。**カードの門を通ったセッションの中でだけ呼ぶ。**"""
        ok, why = check_robots(src["url"])
        res["robots"] = why
        if not ok:                     # False＝拒否、None＝robots.txt が混んでいる。どちらも今回は行かない
            res["skipped"] = why
            lines.append(report_one(src, res))
            counts["拒否"] = counts.get("拒否", 0) + 1
            return

        try:
            status, ctype, raw = fetch(src["url"])
        except urllib.error.HTTPError as e:
            res["fetch_error"] = f"HTTP {e.code}"
            if is_busy(e):
                # 入口で混んでいると言われた。この収集先は今回ここまで（辿りにも行かない）
                res["busy_stop"] = e.code
            lines.append(report_one(src, res))
            counts["失敗"] = counts.get("失敗", 0) + 1
            time.sleep(WAIT)
            return
        except Exception as e:
            res["fetch_error"] = f"{type(e).__name__}: {e}"
            lines.append(report_one(src, res))
            counts["失敗"] = counts.get("失敗", 0) + 1
            time.sleep(WAIT)
            return

        text, enc = to_text(raw, ctype)
        res.update(status=status, encoding=enc, bytes=len(raw))
        res["analysis"] = analyze(text, src["url"])
        counts[res["analysis"]["verdict"]] = counts.get(res["analysis"]["verdict"], 0) + 1

        # 生のまま残す。これがアーカイブの最初の1枚になる
        d = os.path.join(raw_dir, src["id"])
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, f"{today}{ext_of(raw, ctype)}"), "wb") as f:
            f.write(raw)

        # 入口が目次だけのことが多い（堺市・和泉市・阪南市など）。
        # 表が無いページはその先を見に行く。
        #
        # さらに、その先も目次のことがある。堺市は
        #   入口 → 届出の種類（新設・廃止・承継…） → 年度
        # と2段になっていて、1段だけでは廃止の中身に届かない。
        if res["analysis"]["verdict"] == "わからない":
            res["followed"] = []
            known = {src["url"]}          # 見たか、これから見る予定のURL
            queue = []

            def enqueue(links, depth, limit):
                """まだ見ていないものだけを、上限まで列に並べる。

                親ページへ戻るリンクが上限の枠を食うと、年度が取りこぼされる。
                数える前に既知のものを除いておく。
                """
                fresh = [(u, lb) for u, lb in links if u not in known]
                for u, lb in fresh[:limit]:
                    known.add(u)
                    queue.append((u, lb, depth))
                return len(fresh)

            n_found = enqueue(follow_links(text, src["url"]), 1, FOLLOW_MAX)
            if n_found > FOLLOW_MAX:
                res["follow_capped"] = (n_found, FOLLOW_MAX)

            while queue and len(res["followed"]) < FOLLOW_BUDGET:
                url2, label, depth = queue.pop(0)
                # 辿った先も robots.txt を見る（共通仕様3.4）。ホストごとに1回だけ取ってあるので追加の通信は無い
                ok2, why2 = check_robots(url2)
                if not ok2:
                    res["followed"].append((label, None, depth, why2 or "robots"))
                    continue
                time.sleep(WAIT)
                try:
                    st2, ct2, raw2 = fetch(url2)
                except Exception as e:
                    res["followed"].append((label, None, depth, f"{type(e).__name__}"))
                    if is_busy(e):
                        # 相手が「混んでいる」「今は受けない」と言っている。押し込まない。
                        # ここで break しないと、同じホストに最大 FOLLOW_BUDGET 本まで
                        # 5秒おきに当たり続ける（共通仕様3.4。他のスクリプトはみな止めている）
                        res["busy_stop"] = getattr(e, "code", None)
                        break
                    continue
                t2, _ = to_text(raw2, ct2)
                a2 = analyze(t2, url2)
                with open(os.path.join(d, f"{today}--{slug_of(url2)}{ext_of(raw2, ct2)}"),
                          "wb") as f:
                    f.write(raw2)
                res["followed"].append((label, a2, depth, None))
                counts[a2["verdict"]] = counts.get(a2["verdict"], 0) + 1

                # ここも目次だったら、もう一段だけ潜る
                if a2["verdict"] == "わからない" and depth < 2:
                    enqueue(follow_links(t2, url2), depth + 1, FOLLOW_MAX_2)

            if len(res["followed"]) >= FOLLOW_BUDGET and queue:
                res["budget_hit"] = (FOLLOW_BUDGET, len(queue))

        # 今日の取得が、必要な範囲をそろえていたか。**保存したものだけで決める**（上の kanzen_hantei）。
        # 同じ関数を parse.py も呼び、台帳にして merge.py へ渡す
        res["kanzen"] = kanzen_hantei(src, today, raw_dir)

        lines.append(report_one(src, res))
        time.sleep(WAIT)

    for src in sources:
        if only and only not in (src["id"], src.get("area", "")):
            continue
        res = {}

        if not src.get("enabled", True):
            res["skipped"] = src.get("note", "いまは対象外にしている")
            lines.append(report_one(src, res))
            continue

        # 相手ごとの頻度（共通仕様3.4）。前回からその日数たっていなければ取りに行かない
        # **知らない値を、いちばん頻繁な側に倒さない。** 綴りを間違えると
        # 「weekly」が毎日になる。相手のサーバーに出る回数なので、
        # 分からないときは止める（3.4「1日1回」。2026-09-19）
        freq = src.get("freq", "daily")
        if freq not in FREQ_DAYS:
            raise ValueError(
                f"{src['id']}: 知らない freq「{freq}」。"
                f"使えるのは {'/'.join(FREQ_DAYS)}。取りに行く回数なので黙って決めない")
        wait_days = FREQ_DAYS[freq]
        if wait_days:
            last = last_saved(src["id"])
            if last and (runday.today_date() - last).days < wait_days:
                res["skipped"] = f"{src.get('freq')}：前回 {last.isoformat()} から {wait_days} 日たっていないので今回は見ない（共通仕様3.4）"
                lines.append(report_one(src, res))
                continue

        # **取得先1つ（カード1枚）ごとに、通信の前にカードの門を見る。**
        # 通ったら、その取得先の通信は全部このセッションの中で行う（共通指示書1）。
        hozon_saki = os.path.join(raw_dir, src["id"])
        try:
            with K.sesshon(src["id"], hozon_saki=hozon_saki):
                do_source(src, res)
        except kado.Tomeru as e:
            res["skipped"] = "門で止めた：" + "／".join(e.riyuu)
            lines.append(report_one(src, res))
            counts["門で止めた"] = counts.get("門で止めた", 0) + 1

    summary = " / ".join(f"{k} {v}件" for k, v in sorted(counts.items())) or "対象なし"
    lines.insert(2, f"**まとめ: {summary}**")
    lines.insert(3, "")

    text = "\n".join(lines)
    os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
    with open(os.path.join(HERE, "data", "recon-report.md"), "w", encoding="utf-8") as f:
        f.write(text)
    print(text)

    # GitHub Actions の画面にも出す
    gh = os.environ.get("GITHUB_STEP_SUMMARY")
    if gh:
        with open(gh, "a", encoding="utf-8") as f:
            f.write(text)


if __name__ == "__main__":
    main()
