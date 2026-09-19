#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""data/all.json から、見せるページを作る。

1つのHTMLで全部を描くJSのアプリにはしない。検索に拾われるには、店ごと・
市区町村ごとに独立したページが要る。ここで静的なHTMLを1件ずつ書き出す。

出力（すべて shutten/ の下、GitHub Pages でそのまま配信される）
  index.html        … 入口。これから起きる予定・最近の廃止・最近の新設・市区町村と種類の一覧・検索
  a/<市区町村>.html  … その市区町村の届出一覧
  k/<種類>.html      … 種類別（新設・廃止・承継・変更・中規模）
  s/<key>.html       … 届出1件の詳細。全項目と出典
  search.json       … 入口の検索で使う軽い索引
  sitemap.xml / robots.txt

外部のCSSやJSは読まない（1ファイルで完結させる作りに合わせる）。
"""

import html
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import privacy   # 3.2 の小さい数の伏せ。件数を画面に出す所は全部ここを通す
from common import addr as addrlib   # 4節。index.json の city_code / addr_key を作る


def n_(v):
    """画面に出す件数。1〜2件は "1-2"、0 は "–"（共通仕様 3.2）。"""
    return privacy.bucket_count(v) if v else "–"

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "common"))
import runday
ALL = os.path.join(HERE, "data", "all.json")
SOURCES = os.path.join(HERE, "sources.json")
# 公開URL。既定は CNAME ファイルから読む。CNAME は GitHub Pages が
# 独自ドメインを知るために置いているもので、公開先の正本はここしかない。
#
# 以前は既定を古いURLの文字列で書いていた。ワークフローは環境変数で
# 正しいURLを渡していたが、手元で build_site.py を走らせると既定に戻り、
# 4,921本のURLと全ページの canonical が引っ越し前のホストを指したまま
# コミットされた。既定を持たせず、CNAME を見るようにする。
def _default_site_url():
    path = os.path.join(HERE, "CNAME")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            host = f.read().strip()
        if host:
            return f"https://{host}/"
    # CNAME が無いときだけ、リポジトリ名から組み立てる（独自ドメインを
    # 付ける前の状態）。ここに固定のURLを書き足さないこと
    return "https://virgob77.github.io/ogataten-nippo/"


SITE_URL = (os.environ.get("SITE_URL") or _default_site_url()).rstrip("/") + "/"
HOST = SITE_URL.split("/", 3)[0] + "//" + SITE_URL.split("/", 3)[2]   # https://virgob77.github.io
BASE = "/" + SITE_URL.split("/", 3)[3]                                  # /ic-log/shutten/
SITE_NAME = "大型店日報"   # ドメインは ogataten-nippo.com の予定。「出店ウォッチ」は既存メディアと同名で使えない
CONTACT_URL = "https://forms.gle/pp93tSJ5p8SAMEMk8"   # 訂正・削除の依頼フォーム（Googleフォーム）
OPERATOR = "鯨屋（くじらや）"      # 運営者名（屋号のみ。氏名は載せない → docs/kyotsu-shiyo.md 7節）
OPERATOR_DESC = "大阪府・兵庫県で行政が公開する一次情報を、消える前に記録しています。"   # 7節の共通文面の2行目
# 大阪府の移譲市町（20）の数え方。sources.json の note と同じことをここに書く。
WINDOW_COVERS = {"minoh-2shi2cho": ["池田市", "豊能町", "能勢町"]}   # 箕面市の窓口のページに載る3市町
NOT_DELEGATED = {"吹田市", "高槻市"}     # 移譲先ではなく府が受理する（sources.json の note）
DELEGATED_MISSING = ["岬町"]              # 移譲先だが届出ページが見つからず、府のページに載る分だけ拾う
SITE_START = "2026-09-11"   # このサイトが自分で取りに行き始めた日。これより前の日付は Internet Archive の保存から
# 訂正履歴（7節「氏名の代わりに信用を作るもの」の3つめ）。いつ・何を・なぜ。氏名は書かない
TEISEI = [
    ("2026-09-19", "全ての届出ページの「取得日」が、実際に取りに行った日より1日早く出ていたのを直した。"
     "毎朝の巡回が日付をまたぐ時刻に走っていたため、取りに行った時刻と記録した時刻で日付が違っていた。",
     "共通仕様3.5。取得日は「こちらが取った日」なので、1つの実行の中で2つになってはいけない。"
     "走り始めに1回だけ決める形にした。"),
    ("2026-09-19", "大阪府の届出33件で、延床面積の数字が「備考」として表示されていたのを直し、"
     "同じ33件に落ちていた用途地域を表示するようにした。用途地域の書き方（「第１種住居」「第一種住居地域」など31通り）をそろえた。",
     "大阪府の一覧は見出しが2段で、「備考欄」の下に「延床面積」「施設の用途地域」が"
     "ぶら下がっている。上の段しか読んでいなかったため（共通仕様4節）。"),
    ("2026-09-15", "設置者が個人の届出で、氏名が検索用の欄に、地番が所在地に残っていたのを伏せ直した（22件）。",
     "共通仕様3.1（個人は「個人」と書き、所在地は町丁目まで）。自治体のページは数か月で消えるが、このサイトは消えないため。"),
    ("2026-09-16", "法人なのに個人と判定していた設置者（15件）を法人に直し、地番の丸めを戻した。",
     "判定を一度きりにせず、値が入るたびにやり直すようにした（共通仕様5節）。"),
    ("2026-09-16", "全ての届出ページに出典のURLと取得日を付けた（2,185ページで取得日が空だった）。1〜2件の数字は「1-2」と伏せた。",
     "共通仕様3.5（出典と取得日）と3.2（小さい母数）。"),
    ("2026-09-16", "存在しない市区町村「神崎郡市」のページを直し、同じ町が2つに割れていた市区町村ページ（猪名川町など4件）をまとめた。八尾市・堺市の「中規模」が市条例の届出であることを全ページに注記した。",
     "住所から市区町村名を切り出す規則の誤り（共通仕様4節）。"),
    ("2026-09-16", "大阪市の届出1,419件の「取得日」が、一覧ファイルの日付（2026-06-30）になっていたのを、実際にダウンロードした日に直した。一覧の日付は別に書くようにした。",
     "共通仕様3.5。取得日は「こちらが取った日」であって、自治体の一覧の日付ではない。"),
]
CONTACT_EMAIL = "info@ogataten-nippo.com" # 返信用のメールアドレス
REPLY_DAYS = 7     # 返答のめやす（日）
REPO_ISSUES = "https://github.com/VirgoB77/ogataten-nippo/issues/new"
DISCLAIMER = "届出時点の内容です。届出のあとに変更や取下げがあることがあり、実際の開店日・閉店日と異なる場合があります。"
TAGLINE = "大阪・兵庫の大型店の開店・閉店を、届出が出た日に。"

KIND_ORDER = ["新設", "廃止", "承継", "変更", "中規模", "不明", "意見・勧告"]
KIND_COLOR = {"新設": "#1a7f37", "廃止": "#b42318", "承継": "#6e40c9", "変更": "#4b5563",
              "中規模": "#0e7490", "不明": "#6b7280", "意見・勧告": "#92400e"}
KIND_DESC = {
    "新設": "新しく大型店（店舗面積1,000㎡超）ができる届出。開店の8か月以上前に出る。",
    "廃止": "店舗面積が1,000㎡以下になる届出。大型店でなくなる＝閉店・縮小・建て替え。",
    "承継": "建物の設置者（持ち主）が変わった届出。売買や合併で出る。",
    "変更": "店名・小売業者・営業時間・駐車場などの変更届出。",
    "中規模": "1,000㎡以下の店について、市が独自に求めている届出。",
    "不明": "ページに種類が書かれていなかった届出。",
    "意見・勧告": "市が意見や勧告を出した記録。",
}


def esc(s):
    return html.escape(str(s if s is not None else ""), quote=True)


def jp_date(s):
    if not s or len(s) < 10:
        return s or ""
    y, m, d = s[:4], int(s[5:7]), int(s[8:10])
    return f"{y}年{m}月{d}日"


def fmt_area(v):
    if v in (None, "", 0):
        return ""
    try:
        return f"{int(round(float(v))):,}㎡"
    except (TypeError, ValueError):
        return str(v)


def slug(s):
    return re.sub(r"[\\/:*?\"<>|\s]", "_", s)


# ---------------------------------------------------------------- 骨組み

CSS = """
:root{--bg:#faf9f6;--card:#fff;--ink:#1f2328;--sub:#59636e;--rule:#e5e2db;--key:#1a5cff;--soft:#f1efe9}
@media (prefers-color-scheme:dark){:root{--bg:#141517;--card:#1d1f23;--ink:#e8e6e1;--sub:#a1a7b0;--rule:#2e3138;--key:#7aa2ff;--soft:#24272d}}
*{box-sizing:border-box}html{color-scheme:light dark}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.7 -apple-system,"Hiragino Sans","Noto Sans JP","Yu Gothic UI",Meiryo,sans-serif;padding:0 16px 48px}
a{color:var(--key);text-decoration:none;overflow-wrap:anywhere}a:hover{text-decoration:underline}
.wrap{max-width:880px;margin:0 auto}
header.top{padding:20px 0 8px;border-bottom:1px solid var(--rule);margin-bottom:20px}
header.top .name{font-weight:700;font-size:15px;letter-spacing:.02em}
header.top .name a{color:var(--ink)}
header.top .tag{color:var(--sub);font-size:13px;margin-top:2px}
h1{font-size:24px;line-height:1.35;margin:8px 0 6px}
h2{font-size:17px;margin:32px 0 10px;padding-bottom:6px;border-bottom:1px solid var(--rule)}
.lead{color:var(--sub);font-size:14px;margin:0 0 14px}
.badge{display:inline-block;font-size:12px;font-weight:700;color:#fff;padding:1px 8px;border-radius:999px;vertical-align:middle;line-height:1.6;white-space:nowrap}
table{width:100%;border-collapse:collapse;font-size:14px}
th,td{text-align:left;padding:8px 6px;border-bottom:1px solid var(--rule);vertical-align:top}
th{color:var(--sub);font-weight:600;font-size:12px;white-space:nowrap}
td.n{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
td.d{white-space:nowrap;color:var(--sub);font-size:13px}
.list{list-style:none;padding:0;margin:0}
.list li{padding:10px 0;border-bottom:1px solid var(--rule);overflow-wrap:anywhere}
.list .m{color:var(--sub);font-size:13px;margin-top:2px}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin:8px 0}
.chips a{background:var(--soft);color:var(--ink);padding:4px 12px;border-radius:999px;font-size:14px}
.chips a b{color:var(--sub);font-weight:500;margin-left:4px}
.kv{display:grid;grid-template-columns:8.5em 1fr;gap:6px 12px;font-size:15px}
.kv dt{color:var(--sub)}.kv dd{margin:0;overflow-wrap:anywhere}
.card{background:var(--card);border:1px solid var(--rule);border-radius:12px;padding:16px 18px;margin:12px 0}
.stat{display:flex;gap:18px;flex-wrap:wrap;margin:14px 0}
.stat div{background:var(--card);border:1px solid var(--rule);border-radius:12px;padding:10px 16px;min-width:120px}
.stat b{display:block;font-size:22px;line-height:1.2}.stat span{font-size:12px;color:var(--sub)}
.note{font-size:13px;color:var(--sub);background:var(--soft);border-radius:10px;padding:10px 14px;margin:14px 0}
footer{margin-top:44px;padding-top:16px;border-top:1px solid var(--rule);font-size:12px;color:var(--sub);line-height:1.8}
input.q{width:100%;font:inherit;padding:10px 12px;border:1px solid var(--rule);border-radius:10px;background:var(--card);color:var(--ink)}
#hits li{padding:8px 0}
@media (max-width:560px){h1{font-size:21px}.kv{grid-template-columns:1fr}.kv dt{margin-top:6px}th.hide,td.hide{display:none}}
"""


def page(title, body, rel, desc="", canonical="", extra_css=""):
    """共通の外枠。rel はこのページから見た shutten/ への相対パス（'' か '../'）。

    **CSS は外に出す。** 埋め込むと、1行直すたびに4,809ページが変わる。
    1ページの55%がCSSで、同じものが14MB分ぶら下がっていた（2026-09-19）。
    外に出すと、読む人のブラウザは1回だけ取って使い回す。
    2ページしか使わない分（絞り込み）は、そのページの中に置く。
    """
    d = esc(desc or TAGLINE)
    extra = f"\n<style>{extra_css}</style>" if extra_css else ""
    can = f'<link rel="canonical" href="{SITE_URL}{canonical}">' if canonical is not None else ""
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{d}">
{can}
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{d}">
<meta property="og:type" content="website">
<link rel="stylesheet" href="{rel}style.css">{extra}
</head>
<body><div class="wrap">
<header class="top"><div class="name"><a href="{rel}index.html">{esc(SITE_NAME)}</a></div><div class="tag">{esc(TAGLINE)}</div></header>
{body}
<footer>
<p>出典：各自治体が大規模小売店舗立地法に基づいて公告・縦覧している届出（大阪府・大阪市・堺市・兵庫県・神戸市と、大阪府から権限移譲を受けた市町）。八尾市・堺市の「中規模」は、法ではなく市の条例に基づく届出です。各届出ページに出典のURLと取得日を載せています。兵庫県・神戸市の過去分には、Internet Archive（Wayback Machine）の保存から積み直したものを含みます（各ページにその旨を書いています）。
毎朝1回とりに行き、自治体のページから消えた届出もこのサイトには残しています。</p>
<p>{esc(DISCLAIMER)} 写し間違いもありえます。正確な内容は各届出ページの「出典」から自治体のページをご確認ください。</p>
<p><a href="{rel}about.html">このサイトについて・出典と利用規約</a> ／ <a href="{rel}contact.html">訂正・削除のご依頼</a></p>
</footer>
</div></body></html>"""


def badge(kind):
    return f'<span class="badge" style="background:{KIND_COLOR.get(kind, "#6b7280")}">{esc(kind)}</span>'


def row_link(r, rel, show_area=True):
    when = r.get("event_on") or r.get("planned_on") or ""
    area = f'<td class="hide">{esc(r["area"])}</td>' if show_area else ""
    return (f'<tr><td class="d">{esc(r["notified_on"])}</td><td>{badge(r["kind"])}</td>'
            f'<td><a href="{rel}s/{r["key"]}.html">{esc(r["store"])}</a></td>{area}'
            f'<td class="d hide">{esc(when)}</td><td class="n">{fmt_area(r.get("area_m2"))}</td></tr>')


def table(rows, rel, show_area=True, limit=None):
    head = "<tr><th>届出日</th><th>種類</th><th>店舗</th>" + ("<th class=\"hide\">市区町村</th>" if show_area else "") + "<th class=\"hide\">予定日</th><th>面積</th></tr>"
    body = "".join(row_link(r, rel, show_area) for r in (rows[:limit] if limit else rows))
    return f"<table>{head}{body}</table>"


# ---------------------------------------------------------------- 各ページ

def detail_page(r, by_ref, src_meta):
    rel = "../"
    kv = []

    def add(k, v):
        if v not in (None, "", [], 0):
            kv.append(f"<dt>{esc(k)}</dt><dd>{v}</dd>")

    add("種類", badge(r["kind"]) + (f' <span style="color:var(--sub);font-size:13px">{esc(r.get("article",""))}</span>' if r.get("article") else ""))
    add("届出日", esc(jp_date(r["notified_on"])))
    ev = r.get("event_on") or r.get("planned_on")
    if ev:
        label = {"新設": "開店予定日", "廃止": "廃止日", "承継": "承継日", "変更": "変更日"}.get(r["kind"], "予定日")
        add(label, esc(jp_date(ev)))
    if r.get("opened_on"):
        add("開店日", esc(jp_date(r["opened_on"])))
    addr_note = ""
    if r.get("address_redacted"):
        # 「個人だから伏せた」と「誰か確かめられないから伏せた」は別のこと。
        # 読者にどちらか分かるように書き分ける
        disp = r.get("operator_display") or ""
        why = ("設置者が個人のため" if disp == "個人"
               else "届出の一覧の設置者の欄に住所だけが書かれていて名称が読めないため" if r.get("operator_suspect") == "address"
               else "設置者を確かめられないため")
        addr_note = f'<span class="note">（{why}町丁目まで）</span>'
    if r.get("address_suspect"):
        addr_note += '<span class="note">（自治体の表の所在地欄に別の県の住所が入っていたため、店舗の所在地としては表示していません）</span>'
    add("所在地", esc(r.get("address") or r.get("area")) + addr_note)
    add("店舗面積", esc(fmt_area(r.get("area_m2"))))
    add("延床面積", esc(fmt_area(r.get("floor_area_m2"))))
    # _display は merge.py が付ける画面用の値。個人は「個人」と書いてある。
    # 空欄にすると「取れなかった」のか「伏せた」のか読者に分からない（共通仕様3.1）
    add("設置者", esc(r.get("operator_display") or r.get("operator")))
    add("新設置者", esc(r.get("new_operator_display") or r.get("new_operator")))
    add("小売業者", esc(r.get("retailer_display") or r.get("retailer")))
    add("内容", esc(r.get("content")))
    if r.get("parking") or r.get("bicycle"):
        add("駐車・駐輪", esc(f"{r.get('parking') or '–'}台 / {r.get('bicycle') or '–'}台"))
    if r.get("open_time") or r.get("close_time"):
        add("営業時間", esc(f"{r.get('open_time') or ''}〜{r.get('close_time') or ''}"))
    add("用途地域", esc(r.get("zoning")))
    add("説明会", esc(r.get("meeting")))
    add("住民等の意見", esc(r.get("citizen_opinion")))
    add("市の意見", esc(r.get("city_opinion") or r.get("pref_opinion")))
    add("勧告", esc(r.get("city_recommendation") or r.get("recommendation")))
    add("備考", esc(r.get("note")))
    if r.get("review_from") or r.get("review_to"):
        add("縦覧期間", esc(f"{jp_date(r.get('review_from'))}〜{jp_date(r.get('review_to'))}"))

    hist = ""
    if r.get("history"):
        links = []
        for h in r["history"]:
            t = by_ref.get(h)
            if t and t["key"] != r["key"]:
                links.append(f'<li><a href="{t["key"]}.html">{esc(t["notified_on"])} {badge(t["kind"])} {esc(t.get("content") or t["store"])}</a></li>')
            elif t is None and h not in ("既存店",):
                links.append(f"<li>{esc(h)}</li>")
        if links:
            hist = f"<h2>同じ店の届出の流れ</h2><ul class=\"list\">{''.join(links)}</ul>"

    src_ids = r.get("sources") or [r["source"]]
    src_items = []
    for i in src_ids:
        m = src_meta.get(i, {})
        # 合流した記録は収集先ごとの取得日（fetched_by）。無ければ記録の取得日
        got = (r.get("fetched_by") or {}).get(i) or r.get("fetched_on") or r.get("last_seen") or r.get("first_seen") or ""
        first = r.get("first_seen") if i == r.get("source") else ""
        # サイトが自分で取りに行き始めた日より前の日付は、Internet Archive の保存から積み直したもの
        via_archive = bool(m.get("wayback")) and bool(got) and got < SITE_START
        when = (f"{got}時点の保存（Internet Archive）から取得" if via_archive else
                f"{got}取得" if got else "取得日の記録なし")
        # Excel から取り出したもの（asof がある）は first_seen が一覧の日付そのものなので、
        # 「最初に確認した日」とは書かず「自治体の一覧の日付」とだけ書く
        if first and first != got and not r.get("asof"):
            when += f"、最初に確認した日 {first}"
        if r.get("asof"):
            when += f"、自治体の一覧の日付 {r['asof']}"
        if m.get("url"):
            line = (f'出典：「{esc(m["name"])}」（<a href="{esc(m["url"])}">{esc(m["url"])}</a>、{esc(when)}）を加工して作成')
        else:
            line = f"出典：{esc(i)}（{esc(when)}）"
        sub = []
        if m.get("license"):
            sub.append(f'ライセンス：{esc(m["license"])}')
        if m.get("terms"):
            sub.append(f'利用規約：<a href="{esc(m["terms"])}">{esc(m.get("terms_name") or m["terms"])}</a>')
        if not m.get("license") and not m.get("terms"):
            sub.append("利用規約：確認中")
        src_items.append(f"<li>{line}" + (f'<div class="m">{" ／ ".join(sub)}</div>' if sub else "") + "</li>")
    src_block = '<ul class="list" style="font-size:14px">' + "".join(src_items) + "</ul>"
    status = ""
    if r.get("mode") == "snapshot":
        status = ("いまも自治体のページに載っています" if r.get("listed") else
                  f"自治体のページには載らなくなりました（最後に確認した日 {esc(r.get('last_seen'))}）")
        status = f'<p class="note">{status}。このサイトには残しています。</p>'
    ocr_note = ""
    if r.get("from_ocr"):
        names = {"address": "所在地", "operator": "設置者", "content": "内容", "area_m2": "店舗面積"}
        ocr_note = ('<p class="note">' + "・".join(names.get(k, k) for k in r["from_ocr"]) +
                    "は、自治体の資料（紙をスキャンしたPDF）を文字認識で読み取ったものです。読み違いがありえます。</p>")
    docs = ""
    if r.get("docs"):
        docs = "<h2>自治体の資料</h2><ul class=\"list\">" + "".join(
            f'<li><a href="{esc(u)}">{esc(u.rsplit("/",1)[-1])}</a></li>' for u in r["docs"][:8]) + "</ul>"

    title = f"{r['store']}（{r['area']}）の{r['kind']}届出 {jp_date(r['notified_on'])}"
    desc = f"{r['area']}の{r['store']}について、{jp_date(r['notified_on'])}に大規模小売店舗立地法の{r['kind']}届出。"
    if r.get("area_m2"):
        desc += f" 店舗面積{fmt_area(r['area_m2'])}。"
    if ev:
        desc += f" {jp_date(ev)}予定。"
    body = f"""
<p class="lead"><a href="{rel}a/{esc(slug(r['area']))}.html">{esc(r['area'])}</a>{'<span class="note">（所在地は店名から推定）</span>' if r.get('place_guess') else ''} › <a href="{rel}k/{esc(r['kind'])}.html">{esc(r['kind'])}</a></p>
<h1>{esc(r['store'])}</h1>
<div class="card"><dl class="kv">{''.join(kv)}</dl></div>
<p class="note">{esc(DISCLAIMER)} 内容に誤りがある場合は<a href="{rel}contact.html">訂正・削除のご依頼</a>からお知らせください。</p>
{status}
{ocr_note}
{hist}
{docs}
<h2>出典</h2>
{src_block}
<p style="font-size:13px;color:var(--sub)">出典の書き方は各自治体の利用規約に合わせています（<a href="{rel}about.html">出典と利用規約</a>）。</p>
"""
    return page(title, body, rel, desc, canonical=f"s/{r['key']}.html")


def area_page(area, rows):
    rel = "../"
    kinds = Counter(r["kind"] for r in rows)
    chips = "".join(f'<a href="{rel}k/{esc(k)}.html">{esc(k)}<b>{n_(kinds[k])}</b></a>' for k in KIND_ORDER if kinds.get(k))
    rows = sorted(rows, key=lambda r: r["notified_on"], reverse=True)
    latest = rows[0]["notified_on"] if rows else ""
    oldest = rows[-1]["notified_on"] if rows else ""
    body = f"""
<h1>{esc(area)}の大型店の届出</h1>
<p class="lead">{n_(len(rows))}件。最新の届出は{esc(jp_date(latest))}。収録は{esc(oldest[:4])}年から（収集先が公表している範囲。市区町村どうしで件数は比べられません）。</p>
<div class="chips">{chips}</div>
{table(rows, rel, show_area=False)}
"""
    desc = f"{area}で公表された大規模小売店舗立地法の届出{n_(len(rows))}件。新設{n_(kinds.get('新設',0))}・廃止{n_(kinds.get('廃止',0))}・変更{n_(kinds.get('変更',0))}。"
    return page(f"{area}の大型店の開店・閉店届出一覧", body, rel, desc, canonical=f"a/{slug(area)}.html")


def kind_page(kind, rows):
    rel = "../"
    rows = sorted(rows, key=lambda r: r["notified_on"], reverse=True)
    areas = Counter(r["area"] for r in rows)
    chips = "".join(f'<a href="{rel}a/{esc(slug(a))}.html">{esc(a)}<b>{n_(n)}</b></a>' for a, n in areas.most_common(30))
    body = f"""
<h1>{badge(kind)} {esc(kind)}の届出</h1>
<p class="lead">{esc(KIND_DESC.get(kind,''))} 全{n_(len(rows))}件。</p>
<p class="note">市区町村の数字は届出の件数で、収録の始まりが市区町村ごとに違うため、比べられる数ではありません。</p>
<div class="chips">{chips}</div>
{table(rows, rel)}
"""
    return page(f"{kind}の届出一覧（大阪・兵庫の大型店）", body, rel, f"{KIND_DESC.get(kind,'')} 大阪府・兵庫県で{n_(len(rows))}件。", canonical=f"k/{kind}.html")


def about_page(src_meta, today):
    rel = ""
    main_ids = ["osaka-pref", "osaka-city", "sakai-city", "hyogo-pref-juran", "kobe-city"]
    rows = []
    for i in main_ids:
        m = src_meta.get(i)
        if not m:
            continue
        t = (f'<a href="{esc(m["terms"])}">{esc(m.get("terms_name") or "利用規約")}</a>' if m.get("terms") else "—")
        lic = esc(m.get("terms_summary") or m.get("license") or "確認中")
        rows.append(f'<tr><td><a href="{esc(m["url"])}">{esc(m["name"])}</a></td><td>{t}</td><td>{lic}</td></tr>')
    cities = [m for i, m in src_meta.items()
              if m.get("enabled") and m.get("area") == "osaka" and i not in main_ids and m.get("url")]
    city_items = "".join(f'<li><a href="{esc(m["url"])}">{esc(m["name"])}</a></li>' for m in sorted(cities, key=lambda m: m["name"]))
    operator_rows = ""
    if OPERATOR:
        operator_rows += f"<dt>運営者</dt><dd>{esc(OPERATOR)}<br>{esc(OPERATOR_DESC)}</dd>\n"
    # 連絡先はフォームを先に（7節）。メールは contact.html にも書いてある
    if CONTACT_URL:
        operator_rows += (f'<dt>連絡先</dt><dd><a href="{rel}contact.html">訂正・削除の依頼フォーム</a>'
                          f'（{REPLY_DAYS}日以内にご返信します）')
        if CONTACT_EMAIL:
            operator_rows += f'　／　<a href="mailto:{esc(CONTACT_EMAIL)}">{esc(CONTACT_EMAIL)}</a>'
        operator_rows += "</dd>\n"
    elif CONTACT_EMAIL:
        operator_rows += f'<dt>連絡先</dt><dd><a href="mailto:{esc(CONTACT_EMAIL)}">{esc(CONTACT_EMAIL)}</a></dd>\n'
    operator_rows += f'<dt>訂正履歴</dt><dd><a href="{rel}teisei.html">いつ・何を・なぜ直したか</a></dd>\n'
    # 大阪府から権限移譲を受けた20市町のうち、見ている市町を数える（収集先の数ではなく市町の数）。
    # 箕面市は2市2町（箕面・池田・豊能・能勢）の幹事で、池田市・豊能町・能勢町のぶんは箕面市の窓口の
    # ページに載る（sources.json の minoh-2shi2cho）。吹田市・高槻市は移譲先ではなく府が受理する
    # （sources.json の note）ので、この数には入れず、府のページから拾う
    covered = set()
    for i, m in src_meta.items():
        if m.get("area") == "osaka" and m.get("enabled") and i not in main_ids:
            covered.add(m["name"].split()[0])
            covered |= set(WINDOW_COVERS.get(i, []))
    covered -= NOT_DELEGATED
    n_delegated = len(covered)
    not_seen = sorted(DELEGATED_MISSING)
    body = f"""
<h1>このサイトについて</h1>

<h2>運営者情報</h2>
<div class="card"><dl class="kv">
{operator_rows}
<dt>サイトの目的</dt><dd>大規模小売店舗立地法にもとづく届出を、届出が出た日にわかる形で公開し、自治体のページから消えたあとも残すこと。</dd>
<dt>データの出どころ</dt><dd>大阪府・大阪市・堺市・兵庫県・神戸市と、大阪府から権限移譲を受けた市町が公表している届出、および兵庫県公報の公告。各届出ページに出典のURLと取得日を書いています。</dd>
<dt>更新頻度</dt><dd>毎朝1回、自動で取得しています。兵庫県・神戸市の過去分（{esc(SITE_START)}より前の日付のもの）は、Internet Archive（Wayback Machine）に残っていた自治体ページの保存から積み直したもので、各ページにその旨を書いています。</dd>
<dt>訂正・削除</dt><dd><a href="{rel}contact.html">訂正・削除のご依頼</a>から受け付けます。原則{REPLY_DAYS}日以内に返信します。</dd>
</dl></div>

<h2>このサイトがしていること</h2>
<p>{esc(SITE_NAME)}は、大規模小売店舗立地法（大店立地法）にもとづいて自治体が公表している「届出」を毎朝1回とりに行き、
店舗面積1,000㎡を超える大型店の新設・変更・廃止・承継を、届出が出た日に一覧にしているサイトです。
自治体のページでは縦覧期間（4か月）が過ぎると消えてしまう届出も、このサイトには残しています。</p>
<p>対象はいま大阪府と兵庫県です。届出先は都道府県と政令指定都市で、大阪府では20の市町に届出先が移譲されているため、そのうち{n_delegated}市町のページを見ています（池田市・豊能町・能勢町は、箕面市が2市2町の窓口として公表しているページで見ています）。{'・'.join(esc(x) for x in not_seen)}は届出のページが見つからないため、府のページに載る分だけ拾っています。吹田市・高槻市は移譲先ではなく府が受理するため、府のページから拾っています。</p>

<h2>やらないと決めたこと</h2>
<ul class="list">
<li><b>設置者が個人のときは、氏名を「個人」と書き、所在地は町丁目までにしています。</b> 自治体のページは数か月で消えますが、このサイトは消えないので、氏名と地番を恒久的に結びつけないためです。法人は名称をそのまま載せます。</li>
<li><b>載せるのは店舗の届出だけで、人の住まいそのものは対象に入りません。</b> 店舗の所在地は届出のとおり載せますが、設置者が個人のときは町丁目までにします。</li>
<li><b>市区町村ごとの件数など、1〜2件の小さい数字は「1-2」と伏せています。</b> 個別の届出ページと突き合わせて特定できないようにするためです。</li>
<li><b>大規模集客施設の基本計画書など、届出より前の段階の情報は扱いません。</b></li>
<li><b>民間の団体や事業者がまとめた一覧は転載しません。</b> 載せるのは行政が法律にもとづいて公表した一次情報だけです。</li>
<li><b>届出の良し悪しを評価しません。</b> 件数と事実を並べるだけで、順位付けや優劣の言葉は使いません。</li>
</ul>

<h2>出典と利用規約</h2>
<p>載せている内容はすべて自治体が公表している届出の一覧・資料からとったもので、このサイトで表の形・並び順・表記をそろえる加工をしています。
各届出ページに、どの自治体のどのページから、いつとったかを書いています。出典の表記は各自治体の利用規約に従い、
<b>「出典：『ページ名』（URL、取得日）を加工して作成」</b>の形にしています。</p>
<div style="overflow-x:auto"><table>
<tr><th>届出先</th><th>利用規約のページ</th><th>利用条件</th></tr>
{''.join(rows)}
</table></div>
<p style="font-size:14px">大阪市の届出一覧は <a href="https://creativecommons.org/licenses/by/4.0/deed.ja">CC BY 4.0</a> で、
神戸市のサイトのコンテンツは政府標準利用規約（第2.0版）準拠（CC BY 4.0 と互換）で提供されています。
このサイトでは列の選択・並べ替え・表記の統一という加工をしています。</p>
<p style="font-size:14px">大阪府・兵庫県・堺市のサイト全体の著作権ページは、無断での複製・転用を認めていません（2026年9月12日に確認）。
兵庫県のオープンデータカタログ（CC BY 4.0）に届出の一覧は登録されていません（同日に確認）。
このサイトが載せているのは、法律にもとづいて自治体が公告している届出の「店舗名・所在地・面積・日付・届出の種類」という事実の一覧で、
写真・図面・文章などの著作物は載せていません。事実の一覧や公告は著作権法上の著作物に当たらないと考え、出典を明記したうえで掲載しています。
自治体から掲載方法について求めがあれば従います。ご指摘は<a href="{rel}contact.html">訂正・削除のご依頼</a>からお願いします。</p>
<p style="font-size:14px">大阪府から権限移譲を受けた市町の届出ページ（各市町のサイト利用規約に従います）：</p>
<ul class="list" style="font-size:14px">{city_items}</ul>

<h2>免責</h2>
<p>{esc(DISCLAIMER)} 数値や日付は自治体の公表をそのまま写していますが、写し間違いがありえます。
紙をスキャンしたPDFを文字認識で読んだ項目には、その旨を各ページに書いています。
正確な内容は、各届出ページの「出典」から自治体のページをご確認ください。このサイトの内容を利用したことによる損害について、運営者は責任を負いかねます。</p>

<h2>訂正・削除のご依頼</h2>
<p>届出をした事業者の方や関係者の方で、内容の訂正や削除を望まれる場合は、<a href="{rel}contact.html">訂正・削除のご依頼</a>をご覧ください。</p>
<p style="font-size:13px;color:var(--sub)">このページの更新日：{esc(today)}</p>
"""
    return page(f"このサイトについて・出典と利用規約｜{SITE_NAME}", body, rel,
                desc=f"{SITE_NAME}の出典、各自治体の利用規約、免責、訂正・削除のご依頼について。", canonical="about.html")


def contact_page(today):
    rel = ""
    mail = (f'<p>メールでも受け付けます：<a href="mailto:{esc(CONTACT_EMAIL)}">{esc(CONTACT_EMAIL)}</a></p>'
            if CONTACT_EMAIL else "")
    if CONTACT_URL:
        route = (f'<p><a href="{esc(CONTACT_URL)}" style="display:inline-block;background:var(--key);color:#fff;'
                 f'padding:10px 18px;border-radius:10px;font-weight:700">依頼フォームを開く</a></p>' + mail)
    elif CONTACT_EMAIL:
        route = mail
    else:
        route = ('<p class="note">専用の依頼フォームを準備しています。用意でき次第このページに載せます。'
                 f'それまでは <a href="{esc(REPO_ISSUES)}">GitHub の Issue</a>（GitHubのアカウントが必要です）でもお受けします。</p>')
    body = f"""
<h1>訂正・削除のご依頼</h1>
<p>{esc(SITE_NAME)}に載っている届出の内容について、訂正や削除のご依頼を受け付けています。
届出をした事業者の方、その代理の方、届出に名前が載っている方からのご依頼を優先して対応します。</p>

<h2>ご依頼に書いていただきたいこと</h2>
<ul class="list">
<li>対象のページのURL（このサイトの「s/」で始まるページ）</li>
<li>店舗名と届出日</li>
<li>訂正か削除か。訂正の場合は、正しい内容</li>
<li>根拠（自治体の公表と食い違っている、届出を取り下げた、公表期間が終わっている、など）</li>
<li>ご依頼者のお名前・所属と、返信先</li>
</ul>

<h2>対応のしかた</h2>
<ul class="list">
<li>内容を確認のうえ、原則として{REPLY_DAYS}日以内に返信します。</li>
<li>自治体の公表と食い違っている場合は、公表に合わせて直します。</li>
<li>自治体の公表そのものの訂正は、このサイトではできません。届出先の自治体窓口へお願いします。</li>
<li>削除のご依頼は、公表期間が終わった届出や、個人の氏名が含まれる場合などを中心に、個別に判断します。</li>
</ul>

<h2>送り先</h2>
{route}
<p style="font-size:13px;color:var(--sub)">このページの更新日：{esc(today)}</p>
"""
    return page(f"訂正・削除のご依頼｜{SITE_NAME}", body, rel,
                desc=f"{SITE_NAME}に載っている届出の訂正・削除のご依頼について。", canonical="contact.html")


KOHO = os.path.join(HERE, "data", "koho", "hyogo-notices.json")
KOHO_KINDS = ["新設", "変更", "廃止", "市町の意見", "その他"]


def _mokuroku_fetched():
    """目録の Excel をダウンロードした日（data/files/fetched.json）。ビルドした日ではない（3.5）。"""
    try:
        with open(os.path.join(HERE, "data", "files", "fetched.json"), encoding="utf-8") as f:
            led = json.load(f)
    except Exception:
        return ""
    days = [v for k, v in led.items() if k.startswith("hyogo-koho-mokuroku/") and v]
    return max(days) if days else ""


def teisei_page(today):
    """訂正履歴。いつ・何を・なぜ（7節）。氏名は書かない。"""
    rel = ""
    items = "".join(f"<tr><td style=\"white-space:nowrap\">{esc(d)}</td><td>{esc(what)}</td><td>{esc(why)}</td></tr>"
                    for d, what, why in sorted(TEISEI, reverse=True))
    body = f"""
<h1>訂正履歴</h1>
<p class="lead">このサイトの内容や出し方を直したときの記録です。いつ・何を・なぜ直したかを書きます。個人の氏名はここにも書きません。</p>
<div style="overflow-x:auto"><table>
<tr><th>日付</th><th>何を直したか</th><th>なぜ</th></tr>
{items}
</table></div>
<p style="font-size:14px">訂正や削除のご依頼は<a href="{rel}contact.html">こちら</a>から。原則{REPLY_DAYS}日以内に返信します。</p>
<p style="font-size:13px;color:var(--sub)">このページの更新日：{esc(today)}</p>
"""
    return page(f"訂正履歴｜{SITE_NAME}", body, rel, desc=f"{SITE_NAME}の訂正履歴。いつ・何を・なぜ直したか。", canonical="teisei.html")


def koho_page(notices, src_meta, today):
    """兵庫県公報の目録から数えた、大店立地法の公告の件数（2007年〜）。"""
    rel = ""
    by_year = defaultdict(Counter)
    by_month = defaultdict(Counter)
    for n in notices:
        if not n.get("date"):
            continue
        k = n["kind"] if n["kind"] in KOHO_KINDS else "その他"
        by_year[n["date"][:4]][k] += 1
        by_month[n["date"][:7]][k] += 1

    def row(label, c, href=None):
        cells = "".join(f'<td class="n">{n_(c.get(k, 0))}</td>' for k in KOHO_KINDS)
        parts = [c.get(k, 0) for k in ("新設", "変更", "廃止")]
        # 1〜2件のセルを伏せても、合計から他を引けば戻ってしまう（3.2「引き算で戻せる」）。
        # 伏せたセルが1つでもある行は、合計も出さない
        total = "–" if any(privacy.masked(v) is None for v in parts) else str(sum(parts))
        lab = f'<a href="{href}">{esc(label)}</a>' if href else esc(label)
        return f"<tr><td>{lab}</td>{cells}<td class=\"n\"><b>{total}</b></td></tr>"

    head = "<tr><th></th>" + "".join(f"<th>{esc(k)}</th>" for k in KOHO_KINDS) + "<th>届出の合計</th></tr>"
    years = "".join(row(f"{y}年", by_year[y]) for y in sorted(by_year, reverse=True))
    months = "".join(row(f"{ym[:4]}年{int(ym[5:])}月", by_month[ym]) for ym in sorted(by_month, reverse=True)[:24])
    total = sum(sum(c.get(k, 0) for k in ("新設", "変更", "廃止")) for c in by_year.values())
    first = min(n["date"] for n in notices if n.get("date"))
    last = max(n["date"] for n in notices if n.get("date"))
    # **出典は既定値で埋めない。** 控えが無いのに出典が出ると、
    # 読者には「ここから取った」に見えるが、取っていない。
    # 8節の「指定された出典表記」は、控えから出すもの（2026-09-19）
    m = src_meta.get("hyogo-koho-mokuroku") or {}
    for k in ("name", "url"):
        if not m.get(k):
            raise ValueError(
                f"兵庫県公報のページを作れない：出典の {k} が控えに無い。"
                "既定値で埋めない（8節）")
    body = f"""
<p class="lead"><a href="{rel}index.html">トップ</a> › 兵庫県の推移</p>
<h1>兵庫県の大型店の届出、2007年からの推移</h1>
<p>兵庫県が出している<b>県公報の目録</b>には、大規模小売店舗立地法にもとづく公告が 1 件 1 行で載っています。
公告の件名には店舗名がありませんが、「新設」「変更」「廃止」の別と公告日（縦覧が始まる日）が分かるので、
兵庫県（神戸市を除く）で年にどれだけ届出が出ているかを {first[:4]} 年から数えられます。</p>
<div class="stat"><div><b>{total:,}</b><span>届出の公告（{first[:4]}〜{last[:4]}年）</span></div>
<div><b>{sum(c.get("新設", 0) for c in by_year.values()):,}</b><span>うち新設</span></div>
<div><b>{sum(c.get("廃止", 0) for c in by_year.values()):,}</b><span>うち廃止</span></div></div>
<p class="note">「市町の意見」は、届出に対して市や町が出した意見の公告で、届出そのものではないので合計に入れていません。
神戸市の届出は神戸市が別に公告するため、ここには含まれません。</p>
<h2>年ごと</h2>
<div style="overflow-x:auto"><table>{head}{years}</table></div>
<h2>月ごと（目録にある最新 {last[:4]}年{int(last[5:7])}月 までの 24 か月）</h2>
<p class="note">目録に載っているのは {esc(last)} の号までです。それより後の月は、県がまだ目録を出していないので数えられません。</p>
<div style="overflow-x:auto"><table>{head}{months}</table></div>
<h2>この数字の元</h2>
<p style="font-size:14px">出典：「{esc(m["name"])}」（<a href="{esc(m["url"])}">{esc(m["url"])}</a>、{esc(_mokuroku_fetched() or today)}取得）を加工して作成。
目録の「公告」シートから件名に「大規模小売」を含む行を数えました。公告の本文（店舗名・所在地など）は公報の本体にあり、順に読み取っていく予定です。</p>
"""
    return page(f"兵庫県の大型店の届出、2007年からの推移｜{SITE_NAME}", body, rel,
                desc=f"兵庫県公報の目録から数えた、大規模小売店舗立地法の新設・変更・廃止の届出の件数。{first[:4]}年から。",
                canonical="hyogo-koho.html")


# ---------------------------------------------------------------- まとめた一覧
# 届出そのものではなく、届出をまとめて作った2つの一覧。
# **見出しは「そのデータが何であるか」を書く。何に使えるかではない**（共通仕様3.3）。

FILTER_CSS = """
/* 長い表のための絞り込み。**行を隠す**ので、ブラウザの検索（Ctrl+F）とも噛み合う */
.tools{position:sticky;top:0;z-index:2;background:var(--bg);padding:10px 0 8px;border-bottom:1px solid var(--rule);margin-bottom:4px}
.tools .q{margin-bottom:8px}
.facets{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.facets label{background:var(--soft);color:var(--sub);padding:4px 12px;border-radius:999px;font-size:13px;cursor:pointer;user-select:none;border:1px solid transparent}
.facets label:has(input:checked){background:var(--key);color:#fff;border-color:var(--key)}
.facets input{position:absolute;opacity:0;width:0;height:0}
.facets .n{margin-left:auto;font-size:13px;color:var(--sub);font-variant-numeric:tabular-nums}
.facets select{font:inherit;font-size:13px;padding:4px 10px;border-radius:999px;border:1px solid var(--rule);background:var(--card);color:var(--ink);max-width:11em}
th.s{cursor:pointer;user-select:none;white-space:nowrap}
/* 並べ替えできる見出しの印。**場所取りに見えない文字を使わない**
   （em space は font によって□で出た。2026-09-19 に実機幅で確かめた） */
th.s::after{content:"";display:inline-block;width:.9em;color:var(--rule);text-align:right}
th.s[data-o="1"]::after{content:"\25B2";color:var(--key)}
th.s[data-o="-1"]::after{content:"\25BC";color:var(--key)}
tr.off{display:none}
.empty{padding:24px 0;color:var(--sub);font-size:14px}
/* 長い表は、幅が足りないと横スクロールになる。**画面の外に出た列は無いのと同じ。**
   狭い画面では列を減らし、長い文字は折り返す（2026-09-19 に実機幅390pxで確かめた） */
table.wide td{overflow-wrap:anywhere}
/* .d は日付用に nowrap だが、**長い語が入る欄は折り返さないと画面から出る。**
   折り返してよい欄には .w を付ける（taiten の「町丁目のみ（店名が違う）」） */
table.wide td.w{white-space:normal}
@media (max-width:560px){table.wide th.hide2,table.wide td.hide2{display:none}
  table.wide{font-size:13px}table.wide th,table.wide td{padding:8px 4px}
  /* **見出しが折り返さないと、見出しの長さが列の幅を決めてしまう。**
     「建物を用意した人」の8文字で105px取っていた（320px幅で12pxはみ出した） */
  table.wide th{white-space:normal}}
"""


FILTER_JS = """
<script>
(function(){
  var box=document.querySelector('.tools'); if(!box) return;
  var q=box.querySelector('.q'), out=box.querySelector('.n'),
      city=box.querySelector('.city'),
      facets=[].slice.call(box.querySelectorAll('.facets input')),
      tb=document.querySelector('tbody'),
      rows=[].slice.call(tb.rows), total=rows.length,
      empty=document.getElementById('empty');
  function norm(s){return (s||'').toLowerCase().replace(/[\s　,]/g,'')}
  rows.forEach(function(r,i){ r._t=norm(r.textContent); r._i=i });
  function run(){
    var v=norm(q.value), on=facets.filter(function(f){return f.checked}), n=0;
    rows.forEach(function(r){
      var ok=(!v||r._t.indexOf(v)>=0)
             &&(!city||!city.value||r.dataset.city===city.value)
             &&on.every(function(f){return r.dataset[f.value]==='1'});
      r.classList.toggle('off',!ok); if(ok) n++;
    });
    out.textContent = (n===total) ? total.toLocaleString()+'件'
                                  : n.toLocaleString()+' / '+total.toLocaleString()+'件';
    if(empty) empty.style.display = n ? 'none' : '';
  }
  q.addEventListener('input',run);
  if(city) city.addEventListener('change',run);
  facets.forEach(function(f){ f.addEventListener('change',run) });
  var ths=[].slice.call(document.querySelectorAll('th.s'));
  ths.forEach(function(th){
    th.addEventListener('click',function(){
      var o = th.dataset.o==='1' ? -1 : 1;
      ths.forEach(function(x){ x.dataset.o='' });
      th.dataset.o=String(o);
      var k=th.dataset.k;
      rows.slice().sort(function(a,b){
        var x=a.dataset[k]||'', y=b.dataset[k]||'';
        if(x===y) return a._i-b._i;
        if(x==='') return 1;
        if(y==='') return -1;
        var nx=parseFloat(x), ny=parseFloat(y);
        if(!isNaN(nx)&&!isNaN(ny)) return (nx-ny)*o;
        return (x<y?-1:1)*o;
      }).forEach(function(r){ tb.appendChild(r) });
    });
  });
  run();
})();
</script>
"""


def tools_bar(placeholder, facets, cities=None):
    """長い表の上に置く絞り込み。facets は (data の名前, 見出し) の並び。

    **行を隠す形にする。** 別の一覧に出し直すと、ブラウザの検索（Ctrl+F）で
    見つけたものと画面が食い違う。並べ替えも、元の順番に戻せるようにする。

    市は数が多い（58）ので札ではなくプルダウンにする。**札を58個並べると、
    絞り込みの帯のほうが表より高くなる。**
    """
    ch = "".join(f'<label><input type="checkbox" value="{esc(k)}">{esc(v)}</label>'
                 for k, v in facets)
    sel = ""
    if cities:
        opts = "".join(f'<option value="{esc(c)}">{esc(c)}（{n_(n)}）</option>'
                       for c, n in cities)
        sel = f'<select class="city"><option value="">市区町村ぜんぶ</option>{opts}</select>'
    return (f'<div class="tools"><input class="q" type="search" placeholder="{esc(placeholder)}" '
            f'autocomplete="off"><div class="facets">{sel}{ch}<span class="n"></span></div></div>')


def _load(name):
    path = os.path.join(HERE, "data", name)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _m2(v):
    return f"{v:,.0f}" if isinstance(v, (int, float)) else "–"


def taiten_page():
    """閉じた届出の一覧。**「撤退」とは書かない**（3.3・評価しない）。"""
    doc = _load("taiten.json")
    if not doc:
        return None
    rows = doc["records"]
    rel = ""
    years = [r["closed_on"][:4] for r in rows if r.get("closed_on")]
    lasted = [r for r in rows if r.get("lasted_days")]
    near = [r for r in rows if r.get("near_candidates")]

    head = f"""<h1>大型店が閉じた届出の一覧</h1>
<p class="lead">大規模小売店舗立地法の廃止の届出を、公告された日の順に並べたものです。
{esc(years and min(years) or "")}年から{esc(years and max(years) or "")}年まで。
大型店の出退店を追う方のために作りました。</p>

<div class="stat">
  <div><b>{n_(len(rows))}</b><span>閉じた届出</span></div>
  <div><b>{n_(sum(1 for r in rows if r.get("area_m2")))}</b><span>店舗面積が書かれていた</span></div>
  <div><b>{n_(len(lasted))}</b><span>開店日までつながった</span></div>
</div>

<div class="note"><b>開店日までつながったのは {n_(len(lasted))} 件だけです。</b>
残りは、始まりの側の届出が手元にありません。役所の縦覧は数か月で消えるので、
こちらが集め始める前に閉じた店は、あとから取りに行っても埋まりません。
<b>平均何年もったか、は出しません。</b>{n_(len(lasted))}件の平均は、
一覧全体について何も言っていないからです。<br>
つながらないのは過去の分だけです。<b>これから開店の届出を取れた店は、
閉じるときにつながります。</b>年数の欄は空のまま持っておきます。</div>

<div class="note">個人が設置者の届出には、<b>何年そこにいたかを出していません。</b>
所在地も町丁目までにしています（<a href="{rel}about.html">このサイトについて</a>）。</div>
"""
    if near:
        head += f"""<div class="note">「町丁目のみ（店名が違う）」は、<b>同じ町丁目に開店の届出はあったが、
店名が一致しなかった</b>ものです（{n_(len(near))}件）。同じ町丁目に別の店があるだけかもしれないので、
つないでいません。<b>当たらなかったことも消さずに残しています。</b></div>"""

    tr = []
    for r in rows:
        y = ""
        if r.get("lasted_days"):
            y = f'{r["lasted_days"] // 365}年' if r["lasted_days"] >= 365 else f'{r["lasted_days"]}日'
        op = esc(r.get("operator") or "")
        # f-string の中にバックスラッシュを入れられないので、先に組み立てる
        ret = f'<br><span class="d">{esc(r["retailer"])}</span>' if r.get("retailer") else ""
        tsubo = f'<br><span class="d">{r["area_tsubo"]:,.0f}坪</span>' if r.get("area_tsubo") else ""
        tr.append(
            f'<tr data-city="{esc(r.get("city") or "")}"'
            f' data-closed="{esc(r.get("closed_on") or "")}" data-area="{r.get("area_m2") or ""}"'
            f' data-hasarea="{1 if r.get("area_m2") else 0}"'
            f' data-lasted="{1 if r.get("lasted_days") else 0}"'
            f' data-near="{1 if r.get("near_candidates") else 0}">'
            f'<td class="d">{esc(r.get("closed_on") or "")}</td>'
            f'<td><a href="{rel}s/{esc(r["id"])}.html">{esc(r["store"])}</a>'
            f'<br><span class="d">{esc(r.get("addr") or "")}</span></td>'
            f'<td class="n">{_m2(r.get("area_m2"))}{tsubo}</td>'
            f'<td class="hide">{op}{ret}</td>'
            f'<td class="d w">{esc(y)}{("<br>" + esc(r["match"])) if r.get("match") else ""}</td></tr>')

    body = head + f"""
<h2>一覧（{n_(len(rows))}件）</h2>
{tools_bar("店名・所在地・会社名でしぼる（表に出ている語なら何でも）", [
    ("hasarea", "店舗面積あり"), ("lasted", "何年いたか分かる"), ("near", "近い候補あり")],
    cities=Counter(r.get("city") for r in rows if r.get("city")).most_common())}
<table class="wide"><thead><tr><th class="s" data-k="closed">閉じた日</th><th>店名・所在地</th>
<th class="s n" data-k="area">店舗面積<br>（㎡）</th>
<th class="hide">設置者<br>店をやる人</th><th>何年いたか<br>つなぎ方</th></tr></thead>
<tbody>{"".join(tr)}</tbody></table>
<p class="empty" id="empty" style="display:none">当てはまるものがありませんでした。</p>
{FILTER_JS}"""
    return page("大型店が閉じた届出の一覧（大阪・兵庫）", body, rel,
                f"大規模小売店舗立地法の廃止の届出 {len(rows)}件。大阪府・兵庫県。公告された日の順。",
                canonical="taiten.html", extra_css=FILTER_CSS)


def settisha_page():
    """建物を用意した人と、店をやる人が別の届出。

    **「賃貸物件の一覧」とは書かない**（共通仕様3.3「見出しで性質が変わる」）。
    デベロッパーと核テナント、同じ企業グループ内の分社も同じように見える。
    """
    doc = _load("settisha.json")
    if not doc:
        return None
    rows = doc["stores"]
    rel = ""
    oc = sum(1 for r in rows if r.get("operator_changes"))
    rc = sum(1 for r in rows if r.get("retailer_changes"))
    ar = sum(1 for r in rows if r.get("area_m2"))
    zo = sum(1 for r in rows if r.get("zoning_norm"))

    head = f"""<h1>建物を用意した人と、店をやる人が別の届出</h1>
<p class="lead">大規模小売店舗立地法の届出には「設置者」と「小売業者」が別の欄で入ります。
その2つが別の名前になっている届出を、店ごとにまとめたものです。
大型店の出退店を追う方のために作りました。</p>

<div class="note"><b>これは賃貸物件の一覧ではありません。</b>
建物を用意した会社と店をやる会社が別に書かれている、というだけです。
デベロッパーと核テナントの関係も、同じ企業グループの中で会社が分かれている形も、
届出の上では同じように見えます。<b>「建物を用意した人と店をやる人が別」までが、
このデータが言っていることです。</b></div>

<div class="stat">
  <div><b>{n_(len(rows))}</b><span>店</span></div>
  <div><b>{n_(oc)}</b><span>設置者の表記が変わった</span></div>
  <div><b>{n_(rc)}</b><span>小売業者の表記が変わった</span></div>
  <div><b>{n_(ar)}</b><span>店舗面積あり</span></div>
  <div><b>{n_(zo)}</b><span>用途地域あり</span></div>
</div>

<div class="note"><b>「表記が変わった」であって、「持ち主が変わった」ではありません。</b>
商号変更・合併・持株会社化でも名前は変わります。届出だけでは売買と見分けられません
（見分けるには法人番号が要ります）。<br>
書き方の違いだけのもの（<code>近鉄不動産(株)</code> と <code>近鉄不動産株式会社</code>）は
数えていません。ただし「ほか◯者」が付いたり消えたりしたものは、
<b>共有者が変わったか書き落としたかのどちらか</b>なので数えています。</div>

<div class="note">店舗面積は {n_(len(rows) - ar)} 店、用途地域は {n_(len(rows) - zo)} 店で
<b>届出に書かれていません。</b>欄のある自治体とない自治体があります。
用途地域は、届出の書き方をそろえた形で出しています（書かれていた形もデータに残しています）。</div>
"""
    tr = []
    for r in rows:
        z = "、".join(r.get("zoning_norm") or []) or "–"
        tsubo = f'<br><span class="d">{r["area_tsubo"]:,.0f}坪</span>' if r.get("area_tsubo") else ""
        ch = []
        if r.get("operator_changes"):
            ch.append(f'設置者{r["operator_changes"]}回')
        if r.get("retailer_changes"):
            ch.append(f'小売{r["retailer_changes"]}回')
        co = []
        if r.get("operator_co_owners"):
            co.append("設置者に共有者")
        if r.get("retailer_co_owners"):
            co.append("小売業者に共有者")
        sub = "<br>".join(f'<span class="d">{esc(x)}</span>' for x in ("、".join(ch), "、".join(co)) if x)
        tr.append(
            f'<tr data-city="{esc(r.get("city") or "")}"'
            f' data-last="{esc(r.get("last_on") or "")}" data-area="{r.get("area_m2") or ""}"'
            f' data-notices="{r.get("notices") or 0}"'
            f' data-hasarea="{1 if r.get("area_m2") else 0}"'
            f' data-haszoning="{1 if r.get("zoning_norm") else 0}"'
            f' data-changed="{1 if (r.get("operator_changes") or r.get("retailer_changes")) else 0}"'
            f' data-shared="{1 if (r.get("operator_co_owners") or r.get("retailer_co_owners")) else 0}">'
            f'<td>{esc(r["store"])}<br><span class="d">{esc(r.get("addr") or "")}</span></td>'
            f'<td>{esc(r.get("operator_now") or "")}</td>'
            f'<td>{esc(r.get("retailer_now") or "")}</td>'
            f'<td class="n">{_m2(r.get("area_m2"))}{tsubo}</td>'
            f'<td class="hide">{esc(z)}</td>'
            f'<td class="d hide2">{esc(r.get("last_on") or "")}<br>届出{n_(r.get("notices") or 0)}件{("<br>" + sub) if sub else ""}</td></tr>')

    body = head + f"""
<h2>一覧（{n_(len(rows))}店）</h2>
{tools_bar("店名・所在地・会社名でしぼる（表に出ている語なら何でも）", [
    ("changed", "名前が変わった"), ("shared", "共有者あり"),
    ("hasarea", "店舗面積あり"), ("haszoning", "用途地域あり")],
    cities=Counter(r.get("city") for r in rows if r.get("city")).most_common())}
<table class="wide"><thead><tr><th>店名・所在地</th><th>建物を用意した人</th><th>店をやる人</th>
<th class="s n" data-k="area">店舗面積<br>（㎡）</th><th class="hide">用途地域</th>
<th class="s hide2" data-k="last">最後の届出</th></tr></thead>
<tbody>{"".join(tr)}</tbody></table>
<p class="empty" id="empty" style="display:none">当てはまるものがありませんでした。</p>
{FILTER_JS}"""
    return page("建物を用意した人と、店をやる人が別の届出（大阪・兵庫）", body, rel,
                f"大規模小売店舗立地法の届出で、設置者と小売業者が別の名前になっている店 {len(rows)}件。",
                canonical="settisha.html", extra_css=FILTER_CSS)


def index_page(all_recs, today):
    rel = ""
    future = sorted([r for r in all_recs if (r.get("event_on") or r.get("planned_on") or "") > today],
                    key=lambda r: r.get("event_on") or r.get("planned_on"))
    recent_close = sorted([r for r in all_recs if r["kind"] == "廃止"], key=lambda r: r["notified_on"], reverse=True)[:12]
    recent_new = sorted([r for r in all_recs if r["kind"] == "新設"], key=lambda r: r["notified_on"], reverse=True)[:12]
    gone = sorted([r for r in all_recs if r.get("mode") == "snapshot" and not r.get("listed")],
                  key=lambda r: r.get("last_seen") or "", reverse=True)[:12]
    kinds = Counter(r["kind"] for r in all_recs)
    areas = Counter(r["area"] for r in all_recs)
    area_chips = "".join(f'<a href="a/{esc(slug(a))}.html">{esc(a)}<b>{n_(n)}</b></a>' for a, n in sorted(areas.items(), key=lambda x: -x[1]))
    kind_chips = "".join(f'<a href="k/{esc(k)}.html">{badge(k)} <b>{n_(kinds[k])}</b></a>' for k in KIND_ORDER if kinds.get(k))
    yrs = [r["notified_on"][:4] for r in all_recs if r.get("notified_on")]   # 件数と同じ母集団で数える
    law_yrs = [r["notified_on"][:4] for r in all_recs if r.get("notified_on") and r["kind"] != "中規模"]
    # 大店立地法は 2000 年施行。それより前の年は八尾市・堺市の条例による中規模の届出なので、その場に書く（3.3）
    yr_note = (f"。{int(min(law_yrs)) - 1}年以前は市の条例による中規模の届出"
               if law_yrs and min(yrs) < min(law_yrs) else "")
    body = f"""
<h1>大阪・兵庫の大型店、これからの開店とこれまでの閉店</h1>
<p class="lead">大規模小売店舗立地法の届出（店舗面積1,000㎡超）を、各自治体の公表ページから毎朝あつめています。届出は開店の8か月以上前に出るので、ニュースになる前に分かります。</p>
<div class="stat"><div><b>{len(all_recs):,}</b><span>届出（{min(yrs)}〜{max(yrs)}年{yr_note}）</span></div><div><b>{kinds.get('新設',0)}</b><span>新設</span></div><div><b>{kinds.get('廃止',0)}</b><span>廃止</span></div><div><b>{len(areas)}</b><span>市区町村</span></div></div>
<input class="q" id="q" type="search" placeholder="店名・市区町村でさがす（例：イオン、枚方市）" autocomplete="off"><ul class="list" id="hits"></ul>

<h2>届出をまとめた一覧</h2>
<p class="lead">届出を1件ずつではなく、店ごと・出来事ごとにまとめ直したもの。</p>
<div class="chips">
<a href="taiten.html">大型店が閉じた届出の一覧</a>
<a href="settisha.html">建物を用意した人と、店をやる人が別の届出</a>
</div>

<h2>これから起きる予定（{len(future)}件）</h2>
<p class="lead">届出に書かれた開店・変更・廃止の予定日が、今日より先のもの。</p>
{table(future, rel)}

<h2>最近の廃止の届出</h2>
<p class="lead">店舗面積が1,000㎡以下になる届出。閉店・縮小・建て替えのいずれか。理由が書かれているものは各ページに。</p>
{table(recent_close, rel)}

<h2>最近の新設の届出</h2>
{table(recent_new, rel)}

{"<h2>自治体のページから消えた届出</h2><p class='lead'>縦覧期間（4か月）が終わって元のページには載らなくなったもの。ここには残ります。</p>" + table(gone, rel) if gone else ""}

<h2>市区町村から</h2>
<p class="lead">数字は届出の件数です（同じ店の変更の届出も1件ずつ数えます。店の数ではありません）。収録の始まりは市区町村ごとに違うので、市区町村どうしで比べられる数ではありません（各市区町村のページに「収録は何年から」を書いています）。</p>
<div class="chips">{area_chips}</div>
<p style="font-size:14px">兵庫県は届出のページに過去分が無いため、<a href="hyogo-koho.html">県公報の目録から数えた 2007 年からの推移</a>を別に載せています。</p>

<h2>種類から</h2>
<div class="chips">{kind_chips}</div>

<p class="note">更新：毎朝7時ごろ（最終 {esc(today)}）。大阪府・大阪市・堺市・兵庫県・神戸市と、大阪府から事務を移譲されている市町のページが対象です。</p>
<script>
(function(){{var q=document.getElementById('q'),ul=document.getElementById('hits'),idx=null;
function norm(s){{return (s||'').toLowerCase().replace(/[\\s　]/g,'')}}
q.addEventListener('input',function(){{var v=norm(q.value);if(v.length<2){{ul.innerHTML='';return}}
if(!idx){{fetch('search.json').then(function(r){{return r.json()}}).then(function(j){{idx=j;run(v)}});return}}run(v)}});
function run(v){{var out=[];for(var i=0;i<idx.length&&out.length<30;i++){{var r=idx[i];if(norm(r.s).indexOf(v)>=0||norm(r.a).indexOf(v)>=0)out.push(r)}}
ul.innerHTML=out.map(function(r){{return '<li><a href="s/'+r.k+'.html">'+r.s+'</a><div class="m">'+r.a+' · '+r.d+' · '+r.t+'</div></li>'}}).join('')||'<li class="m">見つかりませんでした</li>'}}
}})();
</script>
"""
    return page(f"{SITE_NAME}｜大阪・兵庫の大型店の開店・閉店を届出の日に", body, rel,
                f"大阪府・兵庫県の大規模小売店舗立地法の届出{len(all_recs):,}件。これから開く店、閉まる店を、自治体の公表から毎朝あつめています。", canonical="")


# ---------------------------------------------------------------- 書き出し

# ---------------------------------------------------------------- index.json（共通仕様6節）
# 姉妹サイトと横断ハブが読む。records は個票（伏せ済みの値だけ）、counts_by_city は升。
INDEX_KIND = {
    "新設": "大店立地法/新設", "変更": "大店立地法/変更", "廃止": "大店立地法/廃止",
    "承継": "大店立地法/承継", "意見・勧告": "大店立地法/意見・勧告",
    "中規模": "中規模小売店舗（市条例）/届出",     # 八尾市・堺市の条例。法の届出ではない
}


def index_kind(kind):
    return INDEX_KIND.get(kind) or f"大店立地法/{kind}"


def build_index(recs, today):
    records = []
    cells = Counter()
    label = {}
    for r in recs:
        city = r.get("area") if r.get("area") not in (None, "", "所在地不明") else ""
        n = addrlib.normalize(r.get("pref", ""), city, r.get("address", ""))
        kind = index_kind(r.get("kind", ""))
        date_ = r.get("notified_on") or ""
        records.append({
            "id": f"ogataten:{r.get('source','')}:{date_}:{r['key']}",
            "title": f"{r.get('store','')} {r.get('kind','')}" + ("" if r.get("kind") == "意見・勧告" else "届出"),
            "kind": kind,
            "date": date_,
            "pref": r.get("pref", ""),
            "city": city,
            "city_code": n["city_code"],
            "addr": n["addr"],
            "addr_key": n["addr_key"],
            "addr_key_town": n["addr_key_town"],
            "party": r.get("operator") or "",            # index 用。個人は空文字（5節 party_for_index の値）
            "party_kind": r.get("operator_kind") or "individual",
            "url": f"{SITE_URL}s/{r['key']}.html",
            "source_url": r.get("source_url", ""),
            "fetched_on": r.get("fetched_on", ""),
        })
        if city and date_:
            # 升の期間は年。月にすると 3,713 升のうち 95% が 1〜2件になり、伏せ字だらけで
            # 意味をなさない（3.2「ほとんどが伏せ字になる層は、期間を長くまとめる」）。
            # 月と年の両方は出さない。粗さが2つあると引き算で伏せた値が戻る（3.2）
            k = (n["city_code"], city, kind, date_[:4])
            cells[k] += 1
    counts = []
    for (code, city, kind, period), c in sorted(cells.items(), key=lambda x: (x[0][1], x[0][2], x[0][3]), reverse=False):
        counts.append({"city_code": code, "city": city, "kind": kind, "period": period,
                       "count": privacy.masked(c),
                       "count_label": privacy.bucket_count(c)})
    return {"site": "ogataten-nippo", "site_name": SITE_NAME, "generated_at": today,
            "records": records, "counts_by_city": counts}


def main():
    with open(ALL, encoding="utf-8") as f:
        recs = json.load(f)
    with open(SOURCES, encoding="utf-8") as f:
        src_meta = {s["id"]: s for s in json.load(f)["sources"]}
    today = runday.today()

    for d in ("a", "k", "s"):
        os.makedirs(os.path.join(HERE, d), exist_ok=True)
        for old in os.listdir(os.path.join(HERE, d)):      # 消えた市区町村などの古いページを残さない
            os.remove(os.path.join(HERE, d, old))

    by_ref = {r["ref"]: r for r in recs if r.get("ref")}
    urls = []
    # まとめた一覧。**作っただけでは誰も辿りつけない。** index からのリンクと
    # sitemap の両方に入れる（片方だけだと、人か機械のどちらかが見つけられない）

    for r in recs:
        with open(os.path.join(HERE, "s", f"{r['key']}.html"), "w", encoding="utf-8") as f:
            f.write(detail_page(r, by_ref, src_meta))
        urls.append(f"s/{r['key']}.html")

    by_area = defaultdict(list)
    for r in recs:
        r["area"] = r.get("area") or "所在地不明"      # 空だと a/.html という名前の無いページができる（監査）
        by_area[r["area"]].append(r)
    for area, rows in by_area.items():
        with open(os.path.join(HERE, "a", f"{slug(area)}.html"), "w", encoding="utf-8") as f:
            f.write(area_page(area, rows))
        urls.append(f"a/{slug(area)}.html")

    by_kind = defaultdict(list)
    for r in recs:
        by_kind[r["kind"]].append(r)
    for kind, rows in by_kind.items():
        with open(os.path.join(HERE, "k", f"{kind}.html"), "w", encoding="utf-8") as f:
            f.write(kind_page(kind, rows))
        urls.append(f"k/{kind}.html")

    with open(os.path.join(HERE, "style.css"), "w", encoding="utf-8") as f:
        f.write(CSS.strip() + "\n")

    # まとめた一覧（届出そのものではなく、届出から作ったもの）
    made = []
    for fn, fnc in (("taiten.html", taiten_page), ("settisha.html", settisha_page)):
        # 変数名に html を使わない。**標準の html モジュールを隠す**（同じ関数の
        # 下のほうで html.escape を呼んでいる）。9節「標準ライブラリと同じ名前」の、
        # ファイル名ではなく変数名の版（2026-09-19）
        doc_html = fnc()
        if doc_html:
            with open(os.path.join(HERE, fn), "w", encoding="utf-8") as f:
                f.write(doc_html)
            made.append(fn)

    urls += made

    with open(os.path.join(HERE, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_page(recs, today))
    if made:
        print("まとめた一覧: " + " / ".join(made))
    with open(os.path.join(HERE, "about.html"), "w", encoding="utf-8") as f:
        f.write(about_page(src_meta, today))
    with open(os.path.join(HERE, "contact.html"), "w", encoding="utf-8") as f:
        f.write(contact_page(today))
    with open(os.path.join(HERE, "teisei.html"), "w", encoding="utf-8") as f:
        f.write(teisei_page(today))
    urls += ["about.html", "contact.html", "teisei.html"]
    if os.path.exists(KOHO):
        with open(KOHO, encoding="utf-8") as f:
            notices = json.load(f)
        if notices:
            with open(os.path.join(HERE, "hyogo-koho.html"), "w", encoding="utf-8") as f:
                f.write(koho_page(notices, src_meta, today))
            urls.append("hyogo-koho.html")

    idx = [{"k": r["key"], "s": r["store"], "a": r["area"], "d": r["notified_on"], "t": r["kind"]}
           for r in sorted(recs, key=lambda r: r["notified_on"], reverse=True)]
    with open(os.path.join(HERE, "search.json"), "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, separators=(",", ":"))

    # 共通仕様6節。sitemap には入れない（ページではない）
    index = build_index(recs, today)
    with open(os.path.join(HERE, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, separators=(",", ":"))
    coded = sum(1 for x in index["records"] if x["city_code"])
    print(f"index.json: 個票 {len(index['records'])} / 升 {len(index['counts_by_city'])} / city_code あり {coded}"
          + ("" if coded else "（data/ref/jis-codes.json がまだ無い。初回の自動実行で埋まる）"))

    host = SITE_URL
    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
          f"<url><loc>{host}</loc><lastmod>{today}</lastmod><changefreq>daily</changefreq></url>"]
    for u in urls:
        sm.append(f"<url><loc>{host}{html.escape(u)}</loc><lastmod>{today}</lastmod></url>")
    sm.append("</urlset>")
    with open(os.path.join(HERE, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write("\n".join(sm))
    with open(os.path.join(HERE, "robots.txt"), "w", encoding="utf-8") as f:
        f.write(f"User-agent: *\nDisallow: {BASE}data/\nSitemap: {host}sitemap.xml\n")

    print(f"ページを書いた: 詳細{len(recs)} / 市区町村{len(by_area)} / 種類{len(by_kind)} / index / sitemap({len(urls)+1} URL)")


if __name__ == "__main__":
    main()
