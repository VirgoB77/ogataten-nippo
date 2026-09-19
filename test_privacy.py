#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""共通仕様 3.1 / 3.2 を守れているかの検査。

  https://github.com/VirgoB77/ogataten-nippo/blob/main/docs/kyotsu-shiyo.md

前半は common/privacy.py そのものの検査。
後半が本体で、公開する生成物を全部走査して、privacy.py を迂回した値が
1件でも残っていないかを見る（5節「迂回検査」）。

  python3 test_privacy.py

落ちたら、データを取りに行く前に止まる。

この検査に実在の氏名は書かない。書くとリポジトリに氏名が残り、
git の履歴は消せない。人の名前の形をした架空の文字列だけを使う。
"""

import glob
from collections import Counter
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from common import privacy

fails = []


def eq(got, want, what):
    if got != want:
        fails.append(f"{what}\n      出た値: {got!r}\n      ほしい値: {want!r}")


# ---------------------------------------------------------------- is_corp
def test_is_corp():
    corps = [
        "株式会社あいうえ", "㈱あいうえ", "(株)あいうえ", "（株）あいうえ",
        "有限会社かきくけ", "㈲かきくけ", "(有）かきくけ",      # 括弧が半角と全角で混ざる実物がある
        "株かきくけ商店",                                    # ㈱が潰れた表記
        "合同会社さしすせ", "さしすせ特定目的会社", "たちつて投資法人",
        "なにぬね生命保険(相)", "はひふへ生活協同組合", "まみむめ協同組合",
        "学校法人やゆよ", "医療法人らりるれ", "社会福祉法人わをん",
        "大阪市", "兵庫県", "堺市", "大阪市交通局", "○○町教育委員会",
        "あいう産業会館", "アオヤマ", "オークワ　ほか", "F.O.B COOP",
        "IKEA Property,S.L", "かきく・エルエルシー", "さしすホールディングス",
    ]
    for n in corps:
        eq(privacy.is_corp(n), True, f"法人と見てほしい: {n}")

    # 人名の形をした架空の文字列。実在の氏名は書かない
    people = ["山田太郎", "山田　太郎", "佐藤花子　ほか", "鈴木一郎　ほか９者", "田中　健"]
    for n in people:
        eq(privacy.is_corp(n), False, f"個人と見てほしい: {n}")


# ---------------------------------------------------------------- 名前の出し方
def test_names():
    eq(privacy.redact_name("株式会社あいう"), "株式会社あいう", "法人は画面にそのまま")
    eq(privacy.redact_name("山田太郎"), "個人", "個人は画面に「個人」")
    eq(privacy.redact_name("個人"), "個人", "すでに伏せてあるものは二重にしない")
    eq(privacy.redact_name(""), "", "空は空のまま")
    eq(privacy.redact_name("未定"), "未定", "名前でない文言は「個人」に変えない")
    eq(privacy.redact_name("（未定）"), "（未定）", "括弧つきの未定も同じ")
    eq(privacy.redact_name("物品販売業を営む店舗"), "物品販売業を営む店舗", "業種の説明も同じ")

    eq(privacy.party_for_index("株式会社あいう"), "株式会社あいう", "法人は index にそのまま")
    eq(privacy.party_for_index("山田太郎"), "", "個人は index に空文字")
    eq(privacy.party_for_index("個人"), "", "「個人」という文字列を index に入れない")
    eq(privacy.party_for_index("未定"), "", "名前でない文言も index には入れない")

    eq(privacy.party_kind("株式会社あいう"), "corp", "corp")
    eq(privacy.party_kind("山田太郎"), "individual", "individual")
    eq(privacy.party_kind("あいう", disclosed=False), "undisclosed", "undisclosed")
    eq(privacy.party_kind(None), "none", "none")
    # ここが 121件の件。読めていないだけかもしれないので undisclosed にしない
    eq(privacy.party_kind(""), "individual", "空欄は個人に倒す（undisclosed にしない）")


# ---------------------------------------------------------------- 所在地
def test_addr():
    cases = [
        ("あいう市かきく九丁目300番１ほか", "あいう市かきく九丁目"),
        ("あいう区かきく一丁目1663番1外7筆", "あいう区かきく一丁目"),
        ("あいう区かきく町１丁目15-1", "あいう区かきく町１丁目"),
        ("あいう市かきく下町３７７番１ほか", "あいう市かきく下町"),     # 丁目が無い
        ("あいう市かきく町2463番地の１ほか", "あいう市かきく町"),
        ("あいう区かきく4丁目15番1他2筆", "あいう区かきく4丁目"),
        ("あいう市かきく字さし163", "あいう市かきく字さし"),          # 番も無い
        ("あいう区かきく1-1-1", "あいう区かきく1丁目"),             # 数字3つは丁目-番-号
        ("あいう町329-1", "あいう町"),                          # 数字2つは番地-枝番
        ("あいう市かきく町四丁401番地１", "あいう市かきく町四丁"),      # 堺市は「丁」
        # 住所が2つつながっている取りこぼし。丁目の前に地番が残るので安全側に倒す
        ("あいう区かきく21あいう都かきく市さしす六丁目", "あいう区かきく"),
    ]
    for src, want in cases:
        got = privacy.redact_addr(src, "individual")
        eq(got, want, f"個人の所在地を丸める: {src}")
        # もう一度通しても同じ値。そうでないと実行のたびに削れていく
        eq(privacy.redact_addr(got, "individual"), got, f"2回通しても同じ: {src}")
        eq(privacy.redact_addr(src, "corp"), src, f"法人はそのまま: {src}")
        eq(privacy.redact_addr(src, "undisclosed"), src, f"undisclosed はそのまま: {src}")


# ---------------------------------------------------------------- 3.2
def test_small_numbers():
    eq(privacy.bucket_count(1), "1-2", "1件は 1-2")
    eq(privacy.bucket_count(2), "1-2", "2件は 1-2")
    eq(privacy.bucket_count(3), "3", "3件はそのまま")
    eq(privacy.bucket_count(0), "0", "0件はそのまま")
    eq(privacy.suppress_rate(5, 400), True, "人口500人未満は率を出さない")
    eq(privacy.suppress_rate(2, 5000), True, "件数2件以下は率を出さない")
    eq(privacy.suppress_rate(3, 500), False, "人口500・件数3なら出してよい")


# ---------------------------------------------------------------- 迂回検査（本体）
PARTY_FIELDS = ("operator", "new_operator", "retailer")
# 代表者の肩書き。法人名のうしろにこれが付いていたら、その後ろは
# 個人の氏名である可能性が高い（共通仕様3.1）
_TITLE = re.compile(
    r"(代表取締役|代表執行役|執行役|取締役|代表社員|代表者名|代表者|代表理事"
    r"|組合長理事|組合長|理事長|監事|会長|社長|支配人)")
# 丸めたあとに残ってよい数字は「丁目」「丁」の直前の1つだけ
_CHOME_TAIL = re.compile(r"[0-9０-９一二三四五六七八九十]+\s*(丁目|丁)$")
_ONLY_NUM = re.compile(r"^[0-9０-９]+$")
_HAS_NUM = re.compile(r"[0-9０-９]")


def test_all_json():
    """data/all.json は公開している。privacy.py を通っていない値がないか見る。"""
    import merge
    path = os.path.join(HERE, "data", "all.json")
    if not os.path.exists(path):
        print("  data/all.json が無いので迂回検査は飛ばした")
        return
    with open(path, encoding="utf-8") as f:
        recs = json.load(f)

    for r in recs:
        key = r.get("key", "?")

        for f_ in PARTY_FIELDS:
            if f_ not in r:
                continue
            v = (r.get(f_) or "").strip()
            # index 用の値は「法人名か、空」のどちらかしかありえない
            if v and not privacy.is_corp(v):
                fails.append(f"{key}: {f_} に法人でない値が残っている: {v!r}")
            kind = r.get(f_ + "_kind")
            if kind not in (None, "corp", "individual", "undisclosed", "none"):
                fails.append(f"{key}: {f_}_kind が知らない値: {kind!r}")
            if kind == "corp" and v and not privacy.is_corp(v):
                fails.append(f"{key}: {f_}_kind=corp なのに法人でない: {v!r}")
            # 逆も見る。値が法人名なのに個人と記録されていたら、判定が
            # 古いまま持ち回られている（値はあとから埋まることがある）
            if v and privacy.is_corp(v) and kind not in (None, "corp"):
                fails.append(f"{key}: {f_} は法人名なのに {f_}_kind={kind!r}: {v!r}")
            # 法人名のうしろに代表者の氏名がくっついていないか。
            # OCRから補ったとき、肩書きごと1行に入ってくることがある。
            # ただし合同会社の代表社員は法人のことがあるので
            # （「合同会社○○ 代表社員 株式会社△△」）、肩書きの後ろが
            # 法人ならそのままでよい
            m = _TITLE.search(v) if v else None
            if m:
                rest = v[m.end():].strip(" 　:：")
                if rest and not privacy.is_corp(rest):
                    fails.append(
                        f"{key}: {f_} の肩書きのうしろが法人でない"
                        f"（個人の氏名が入っている疑い）: {v!r}")

        # 設置者が個人なら、所在地に地番が残っていてはいけない
        if r.get("address_redacted"):
            a = (r.get("address") or "").strip()
            rest = _CHOME_TAIL.sub("", a)
            if _HAS_NUM.search(rest):
                fails.append(f"{key}: 丸めたのに地番が残っている: {a!r}")

        if r.get("operator_kind") == "individual" and (r.get("address") or "").strip():
            a = r["address"].strip()
            if privacy.redact_addr(a, "individual") != a:
                fails.append(f"{key}: 設置者が個人なのに所在地が丸まっていない: {a!r}")


def test_generated_pages():
    """出来上がったHTMLと search.json に、個人名らしき値が出ていないか見る。

    data/all.json を正として、そこで個人と判定した値が1つでも
    ページに出ていたら落とす。all.json 側が正しいことは上で見ている。
    """
    import merge
    path = os.path.join(HERE, "data", "all.json")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        recs = json.load(f)

    # 画面用の値のうち、法人でも「個人」でも定型文でもないものがあれば、
    # それは伏せそこねている
    for r in recs:
        for f_ in PARTY_FIELDS:
            d = (r.get(f_ + "_display") or "").strip()
            if not d or d == "個人" or d == merge.ADDR_IN_NAME_DISPLAY:
                continue
            if privacy.is_corp(d) or privacy.is_placeholder(d):
                continue
            fails.append(f"{r.get('key','?')}: {f_}_display に伏せそこねた値: {d!r}")
    # 住所の形の設置者は、値そのものを残さない（住所の前に氏名が付いていることがある）。
    # この検査は上の continue の先にあって一度も届いていなかった（審査で見つかった）
    for r in recs:
        for f_ in PARTY_FIELDS:
            if r.get(f_ + "_suspect_value"):
                fails.append(f"{r.get('key','?')}: {f_}_suspect_value が残っている（値は載せない決まり）")
    # 知らない列（extra）も公開するので、地番が生で残っていないこと
    for r in recs:
        for k_, v_ in (r.get("extra") or {}).items():
            v_ = str(v_ or "")
            if re.search(r"[0-9０-９一二三四五六七八九十]+\s*(番地|番|号)", v_):
                fails.append(f"{r.get('key','?')}: extra[{k_!r}] に地番が残っている: {v_[:20]!r}")
                break
    # サイトが自分で取りに行き始めた日より前の取得日は、Internet Archive の保存から取れる収集先にしか付かない
    try:
        with open(os.path.join(HERE, "sources.json"), encoding="utf-8") as f:
            wb = {x["id"] for x in json.load(f)["sources"] if x.get("wayback")}
    except Exception:
        wb = set()
    early = [r for r in recs if (r.get("fetched_on") or "9") < "2026-09-11" and r.get("source") not in wb]
    if early:
        fails.append(f"サイト開始前の取得日なのに Internet Archive の収集先でない記録が {len(early)} 件（例 {early[0].get('source')} {early[0].get('fetched_on')}）")


def test_public_urls():
    """出来上がったページと sitemap.xml が、CNAME のホストだけを指しているか。

    公開URLの正本は CNAME ファイル。ここと違うホストが出力に混ざったら、
    引っ越し前のURLが残っているか、手元の実行が既定値で上書きしたか。

    実際に起きた：build_site.py の既定が古いURLのままで、手元で走らせた
    ぶんが 4,921本のURLと全ページの canonical を引っ越し前のホストに
    書き換えてコミットされた。Google はそちらを正規URLとして扱うので、
    独自ドメインのほうが落ちる。
    """
    cname = os.path.join(HERE, "CNAME")
    if not os.path.exists(cname):
        print("  CNAME が無いので公開URLの検査は飛ばした")
        return
    with open(cname, encoding="utf-8") as f:
        host = f.read().strip()
    if not host:
        return

    bad = {}
    targets = [os.path.join(HERE, "sitemap.xml")]
    for pat in ("*.html", os.path.join("s", "*.html"), os.path.join("a", "*.html"),
                os.path.join("k", "*.html")):
        targets += glob.glob(os.path.join(HERE, pat))

    other = re.compile(r'(?:href|src|content)="https://([a-z0-9.\-]+)/', re.I)
    loc = re.compile(r"<loc>https://([a-z0-9.\-]+)/", re.I)
    # 外に向けたふつうのリンク（出典・自治体・GitHub）は当然ある。
    # 見るのは canonical・og:url・sitemap の loc だけ
    canon = re.compile(r'rel="canonical"\s+href="https://([a-z0-9.\-]+)/', re.I)
    ogurl = re.compile(r'property="og:url"\s+content="https://([a-z0-9.\-]+)/', re.I)

    for path in targets:
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8", errors="ignore") as f:
            t = f.read()
        hosts = set(canon.findall(t)) | set(ogurl.findall(t)) | set(loc.findall(t))
        wrong = {h for h in hosts if h != host}
        if wrong:
            bad.setdefault(",".join(sorted(wrong)), []).append(os.path.relpath(path, HERE))

    for wrong, files in bad.items():
        fails.append(
            f"公開URLが CNAME（{host}）と違うホストを指している: {wrong}"
            f"／{len(files)}ファイル（例 {files[0]}）")




# ---------------------------------------------------------------- 監査で見つかった穴の見張り
def test_late_name_is_still_redacted():
    """伏せたあとに名前が入り直しても、privacy を通ること（merge.py のガードの穴）。

    scrub 済みのレコード（operator は空、画面用は「個人」）に、OCR や収集先の
    合流であとから氏名が入ると、以前は「もう伏せた」と判断して素通りし、
    氏名が index 用の欄に残った。監査が架空名で再現した。ここでは架空名で守る。
    """
    import merge
    rec = {"source": "osaka-city", "key": "demo",
           "operator": "架空　太郎", "operator_display": "個人", "operator_kind": "individual",
           "address": "大阪市北区梅田1-1-1"}
    merge.apply_privacy([rec])
    eq(rec["operator"], "", "あとから入った氏名は index 用の欄に残さない")
    eq(rec["operator_display"], "個人", "画面用は「個人」のまま")
    eq(rec["operator_kind"], "individual", "個人のまま")
    # 逆に、あとから入ったのが法人名なら法人に直る（三菱UFJ信託銀行の件）
    rec2 = {"source": "osaka-city", "key": "demo2",
            "operator": "株式会社かきく", "operator_display": "個人", "operator_kind": "individual",
            "address": "大阪市北区梅田1-1-1"}
    merge.apply_privacy([rec2])
    eq(rec2["operator_kind"], "corp", "あとから法人名が入ったら法人に直す")
    eq(rec2["operator_display"], "株式会社かきく", "法人名は画面にそのまま")
    eq(rec2.get("address_redacted"), None, "法人の地番は丸めない")
    # 空のままなら「個人」の字が消えない（冪等）
    rec3 = {"source": "osaka-city", "key": "demo3",
            "operator": "", "operator_display": "個人", "operator_kind": "individual", "address": "大阪市北区梅田1丁目"}
    merge.apply_privacy([rec3]); merge.apply_privacy([rec3])
    eq(rec3["operator_display"], "個人", "空のレコードを何度通しても「個人」は消えない")


_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def test_every_record_has_source():
    """共通仕様 3.5：全レコードに source_url と fetched_on。監査で 4,790 件とも無かった。"""
    path = os.path.join(HERE, "data", "all.json")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        recs = json.load(f)
    no_url = [r for r in recs if not str(r.get("source_url", "")).startswith("http")]
    no_when = [r for r in recs if not _DATE.match(str(r.get("fetched_on", "")))]
    from collections import Counter
    if no_url:
        c = Counter(r.get("source") for r in no_url)
        fails.append(f"source_url が無い（またはURLでない）レコード {len(no_url)} 件: {dict(c.most_common(5))}")
    if no_when:
        c = Counter(r.get("source") for r in no_when)
        fails.append(f"fetched_on が無い（または日付でない）レコード {len(no_when)} 件: {dict(c.most_common(5))}")


# 件数を出している場所の形。ここに 1 か 2 がそのまま出ていたら 3.2 違反
_RAW_SMALL = re.compile(
    r"<b>[12]</b></a>"                 # チップ（市区町村・種別）
    r"|<td class=\"n\">[12]</td>"       # 公報の表のセル
    r"|<td class=\"n\"><b>[12]</b>"     # 公報の表の合計
    r"|class=\"lead\">[12]件"           # 市区町村ページ・種別ページの先頭行
    r"|届出[12]件。"                     # meta description
    r"|(?:新設|廃止|変更)[12][・。]"      # meta description の内訳
)


def test_no_raw_small_counts_in_pages():
    """共通仕様 3.2 の迂回検査：出来上がったページに 1〜2 件が実数で出ていないか。

    監査で index のチップ13個・公報の表48セル・市区町村ページ多数に出ていた。
    bucket_count() が一度も呼ばれていない死んだコードだった。
    """
    targets = [os.path.join(HERE, "index.html"), os.path.join(HERE, "hyogo-koho.html")]
    targets += glob.glob(os.path.join(HERE, "a", "*.html")) + glob.glob(os.path.join(HERE, "k", "*.html"))
    bad = []
    for path in targets:
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8", errors="ignore") as f:
            t = f.read()
        n = len(_RAW_SMALL.findall(t))
        if n:
            bad.append((os.path.relpath(path, HERE), n))
    if bad:
        total = sum(n for _, n in bad)
        fails.append(f"1〜2件が実数のまま出ている箇所 {total}（{len(bad)}ファイル。例 {bad[:3]}）。bucket_count を通すこと")


def test_no_empty_fetch_date_in_pages():
    """各届出ページの出典に取得日が入っているか。監査で 2,185 ページが「（URL、取得）」と空だった。"""
    bad = 0
    for path in glob.glob(os.path.join(HERE, "s", "*.html")):
        with open(path, encoding="utf-8", errors="ignore") as f:
            if "、取得）" in f.read():
                bad += 1
    if bad:
        fails.append(f"出典の取得日が空「、取得）」のページ {bad} 枚。fetched_on が届いていない")


# ---------------------------------------------------------------- 取得の作法（3.4）の部品
def _load_koho():
    import importlib.util
    spec = importlib.util.spec_from_file_location("koho_pdf", os.path.join(HERE, "koho_pdf.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_fetch_etiquette():
    """robots の判定・混雑の判定・恒久失敗の扱い・目録の年ずれの復旧・空本文の見張り。ネットには出ない。"""
    import urllib.error
    from datetime import date as _d
    from common import fetch
    eq(fetch.robots_allows("User-agent: *\nDisallow: /kk32/", "https://x/kk32/a.pdf"), False, "robots が拒否する")
    eq(fetch.robots_allows("User-agent: *\nDisallow: /private/", "https://x/kk32/a.pdf"), True, "robots が許す")
    eq(fetch.robots_allows("", "https://x/a"), True, "robots が空なら許可")
    eq(fetch.is_busy(urllib.error.HTTPError("u", 429, "", {}, None)), True, "429 は混んでいる")
    eq(fetch.is_busy(urllib.error.HTTPError("u", 503, "", {}, None)), True, "503 は混んでいる")
    eq(fetch.is_busy(urllib.error.HTTPError("u", 404, "", {}, None)), False, "404 は混んでいるではない")
    eq("kujiraya archive bot (+https://" in fetch.UA and "forms.gle" in fetch.UA, True, "UA に about と連絡フォーム")

    k = _load_koho()
    L = {"a": {"status": "月ページに号が無い", "when": "2026-09-01"},
         "b": {"status": "月ページに号が無い", "when": "2026-07-01"},
         "c": {"status": "failed: 文字なし", "when": "2026-09-10"},
         "d": {"status": "failed: HTTP 404"},
         "e": {"status": "failed: URLError"},
         "f": {"status": "done", "v": 2}, "g": {"status": "done", "v": 1},
         "h": {"status": "月ページに号が無い"}}
    t = _d(2026, 9, 16)
    eq(k.needs_fetch("a", L, t), False, "恒久的な失敗は30日は叩かない")
    eq(k.needs_fetch("b", L, t), True, "30日たったら1回だけ確かめ直す")
    eq(k.needs_fetch("c", L, t), False, "文字なしも恒久扱い")
    eq(k.needs_fetch("d", L, t), False, "404 は二度と行かない")
    eq(k.needs_fetch("e", L, t), True, "一時的な失敗は次回やり直す")
    eq(k.needs_fetch("f", L, t), False, "全文ありは取り直さない")
    eq(k.needs_fetch("g", L, t), True, "抜粋だけの古い号は取り直す")
    eq(k.needs_fetch("h", L, t), True, "いつ調べたか不明なら一度だけ")
    eq(k.text_ok(0, ""), False, "空の本文を done にしない")
    eq(k.text_ok(1, "あ" * 300), False, "pdftotext が失敗したら done にしない")
    eq(k.text_ok(0, "あ" * 300), True, "文字があれば OK")
    saved = k.month_links
    try:
        k.month_links = lambda ym, murl, lines: {"1-14-2252": "https://x/2252.pdf"} if ym == "2011-01" else {}
        eq(k.find_in_neighbor_year("2010-01-14", "2252", {"2010-01": "u", "2011-01": "u"}, []),
           ("2011-01-14", "https://x/2252.pdf"), "目録の年が1年前にずれた号を翌年で見つける")
        eq(k.find_in_neighbor_year("2010-01-14", "9999", {"2010-01": "u", "2011-01": "u"}, []),
           (None, None), "無いものは無い")
    finally:
        k.month_links = saved


# ---------------------------------------------------------------- 市区町村名（4節・監査）
def test_place_names():
    """郡の有無で割れない・「神崎郡市」にならない・空の市区町村ページを作らない・他県の住所を店舗所在地にしない。"""
    import merge
    fake = [{"source": "hyogo-koho", "address": "神崎郡市川町西川辺字的場479", "store": "x"},
            {"source": "hyogo-koho", "address": "川辺郡猪名川町松尾台1", "store": "x"},
            {"source": "hyogo-pref-juran", "address": "", "store": "○○猪名川店", "city": ""}]
    guns = merge.gun_table(fake)
    eq(guns.get(("兵庫県", "市川町")), "神崎郡", "データから 市川町→神崎郡 が取れる")
    pref, city, ward, guess = merge.place_of(fake[0])
    eq(merge.with_gun(pref, city, guns), "神崎郡市川町", "市川町の「市」で切れない")
    pref, city, ward, guess = merge.place_of(fake[2])
    eq(merge.with_gun(pref, city, guns), "川辺郡猪名川町", "店名から当てた町にも郡が付く（割れない）")
    eq(guess, True, "店名から当てたら印が付く")
    r = {"source": "kaizuka-city", "address": "", "store": "x"}
    pref, city, ward, guess = merge.place_of(r)
    eq((pref, city), ("大阪府", "貝塚市"), "貝塚市の届出は貝塚市（26件が名前の無いページになっていた）")
    r = {"source": "hyogo-pref-juran", "address": "愛媛県松山市大街道二丁目", "store": "イオン山崎ショッピングセンター"}
    pref, city, ward, guess = merge.place_of(r)
    eq(r.get("address"), "", "別の県の住所は店舗所在地として使わない")
    eq(r.get("address_suspect"), "愛媛県松山市大街道二丁目", "捨てずに退避する")
    eq(city, "", "別の県の市を市区町村にしない")
    # 出来上がりの側：名前の無い市区町村ページが無いこと
    a_dir = os.path.join(HERE, "a")
    if os.path.isdir(a_dir):
        eq(os.path.exists(os.path.join(a_dir, ".html")), False, "a/.html（名前の無い市区町村ページ）を作らない")
        eq(os.path.exists(os.path.join(a_dir, "神崎郡市.html")), False, "存在しない市「神崎郡市」のページを作らない")


def test_parse_keeps_unknown_columns():
    """共通仕様9：知らない列は extra に残し、parse-unknown.md に書き出す（黙って捨てない）。"""
    import parse
    parse.CURRENT["source"] = "test-src"
    page = ("<h2>新設届出</h2><table><tr><th>店舗名称</th><th>届出日</th><th>謎の列</th></tr>"
            "<tr><td>テスト店</td><td>令和6年5月1日</td><td>ここは読めない値</td></tr></table>")
    recs = parse.extract_generic(page, "https://example.test/", "heading")
    eq(len(recs), 1, "表から1件取れる")
    eq((recs[0].get("extra") or {}).get("謎の列"), "ここは読めない値", "知らない列の値を extra に残す")
    eq(parse.UNKNOWN["test-src"][("読まなかった列", "謎の列")] >= 1, True, "読まなかった列を書き留める")


# ---------------------------------------------------------------- 4節 addr.py と 6節 index.json
def test_addr_normalize():
    """共通仕様4節のテスト値をそのまま通す。期待値は具体的に書く。"""
    from common import addr
    codes = {("大阪府", "大阪市北区"): "27127", ("兵庫県", "尼崎市"): "28202", ("兵庫県", "西宮市"): "28204",
             ("大阪府", "豊中市"): "27203", ("兵庫県", "三田市"): "28219", ("大阪府", "大阪市淀川区"): "27123"}
    r = addr.normalize("大阪府", "大阪市北区", "梅田一丁目１番１号", codes)
    eq(r["addr"], "大阪市北区梅田1-1-1", "4節 1件目 addr")
    eq(r["town"], "梅田1", "4節 1件目 town（丁目を含む）")
    eq(r["addr_key"], "27127|梅田1-1-1", "4節 1件目 addr_key")
    eq(r["addr_key_town"], "27127|梅田1", "4節 1件目 addr_key_town")
    r = addr.normalize("兵庫県", "尼崎市", "潮江1丁目3番1号", codes)
    eq(r["addr_key"], "28202|潮江1-3-1", "4節 2件目 addr_key")
    eq(r["addr_key_town"], "28202|潮江1", "4節 2件目 addr_key_town")
    r = addr.normalize("兵庫県", "西宮市", "大字上ケ原　二番町3-5", codes)
    eq(r["addr_key"], "28204|上ケ原2番町3-5", "4節 3件目：「番町」の番を置き換えない")
    eq(r["addr_key_town"], "", "4節 3件目：一覧が無いうちは空（③）。「上ケ原2番町3」にしない")
    r = addr.normalize("大阪府", "大阪市北区", "大阪市北区梅田1-1-1 ○○ビル3F", codes)
    eq(r["addr_key"], "27127|梅田1-1-1", "建物名の数字を地番に混ぜない（6.）")
    r = addr.normalize("大阪府", "豊中市", "服部西町一丁目８４７番地の１ほか", codes)
    eq(r["addr_key"], "27203|服部西町1-847-1", "番地の「の」と全角数字と「ほか」")
    eq(r["addr_key_town"], "27203|服部西町1", "town は丁目まで")
    r = addr.normalize("大阪府", "大阪市淀川区", "十三本町1-2-3", codes)
    eq(r["addr_key"], "27123|十三本町1-2-3", "地名の漢数字（十三）を壊さない")
    r = addr.normalize("兵庫県", "三田市", "三田市天神1丁目", codes)
    eq(r["addr_key_town"], "28219|天神1", "地名の漢数字（三田）を壊さず、先頭の市名を落とす")
    r = addr.normalize("大阪府", "豊中市", "", codes)
    eq((r["addr_key"], r["addr_key_town"]), ("", ""), "住所が無ければ鍵も無い")


def test_jis_rows():
    """総務省の Excel の行 → コード表。区の親を取り違えない。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location("ref_jis", os.path.join(HERE, "ref_jis.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    rows = [["団体コード", "都道府県名（漢字）", "市区町村名（漢字）", "都道府県名（カナ）", "市区町村名（カナ）"],
            ["270008", "大阪府", "", "", ""], ["271004", "大阪府", "大阪市", "", ""],
            ["271208", "大阪府", "住吉区", "", ""], ["271276", "大阪府", "北区", "", ""],
            ["271403", "大阪府", "堺市", "", ""], ["271411", "大阪府", "堺区", "", ""],
            ["272027", "大阪府", "岸和田市", "", ""], ["281000", "兵庫県", "神戸市", "", ""],
            ["281018", "兵庫県", "神戸市東灘区", "", ""], ["282022", "兵庫県", "尼崎市", "", ""]]
    got = {r["code"]: r["city"] for r in m.rows_to_codes(rows)}
    eq(got.get("27127"), "大阪市北区", "「北区」に親の市を付ける")
    eq(got.get("27120"), "大阪市住吉区", "0で終わる区（住吉区）を市と読み違えない")
    eq(got.get("27141"), "堺市堺区", "堺の区の親は堺市（大阪市ではない）")
    eq(got.get("27202"), "岸和田市", "普通の市には何も付けない")
    eq(got.get("28101"), "神戸市東灘区", "もとから市が付いていれば二重にしない")
    eq("27000" in got, False, "都道府県の行は入れない")
    c = m.find_code_file('<p>都道府県コード及び市区町村コード</p><a href="/main_content/x.xlsx">一覧（Excel）</a>'
                         '<a href="/y.xlsx">政令指定都市の区</a>', m.PAGE)
    eq(c[0][1].endswith("/main_content/x.xlsx"), True, "一覧の Excel を先頭に選ぶ")


def test_index_json():
    """共通仕様6節：index.json の形と、伏せ・升の整合。"""
    path = os.path.join(HERE, "index.json")
    if not os.path.exists(path):
        # 検査はワークフローの最初（ページを作る前）に走る。初めて index.json を
        # 作る回はまだ無いので、無いことは咎めない。あれば中身を全部見る
        print("index.json がまだ無い（6節）。ページを作ったあとにできる")
        return
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    for k in ("site", "site_name", "generated_at", "records", "counts_by_city"):
        if k not in d:
            fails.append(f"index.json に {k} が無い")
    need = ["id", "title", "kind", "date", "pref", "city", "city_code", "addr", "addr_key",
            "addr_key_town", "party", "party_kind", "url", "source_url", "fetched_on"]
    cname = os.path.join(HERE, "CNAME")
    host = open(cname, encoding="utf-8").read().strip() if os.path.exists(cname) else ""
    bad = Counter()
    for r in d.get("records", []):
        for k in need:
            if k not in r:
                bad[f"{k} が無い"] += 1
        if r.get("party") and not privacy.is_corp(r["party"]):
            bad["party に法人でない値"] += 1
        if r.get("party_kind") not in ("corp", "individual", "undisclosed", "none"):
            bad["party_kind が4値以外"] += 1
        if host and not str(r.get("url", "")).startswith(f"https://{host}/"):
            bad["url が絶対URLでない／別ホスト"] += 1
        if not _DATE.match(str(r.get("fetched_on", ""))):
            bad["fetched_on が日付でない"] += 1
        cc = r.get("city_code", "")
        if cc and not re.fullmatch(r"[0-9]{5}", cc):
            bad["city_code が5桁でない"] += 1
        for k in ("addr_key", "addr_key_town"):
            v = r.get(k, "")
            if v and (not cc or not v.startswith(cc + "|")):
                bad[f"{k} が city_code| で始まらない"] += 1
        if "/" not in str(r.get("kind", "")):
            bad["kind が <制度>/<種別> でない"] += 1
    for c in d.get("counts_by_city", []):
        n, lab = c.get("count"), c.get("count_label")
        if n is None and lab != "1-2":
            bad["count が null なのに label が 1-2 でない"] += 1
        if isinstance(n, int) and (1 <= n <= 2 or str(n) != lab):
            bad["1〜2件が伏せられていない／label 不一致"] += 1
        if "period" not in c or "kind" not in c or "city" not in c:
            bad["升に city/kind/period が無い"] += 1
    for k, v in bad.items():
        fails.append(f"index.json: {k}: {v} 件")
    # コード表があるなら、市区町村が分かる個票の9割以上に city_code が付くこと
    if os.path.exists(os.path.join(HERE, "data", "ref", "jis-codes.json")):
        known = [r for r in d.get("records", []) if r.get("city")]
        coded = sum(1 for r in known if r.get("city_code"))
        if known and coded / len(known) < 0.9:
            # データの質の話で privacy の検査ではないので、止めずに知らせるだけにする。
            # 止めると、その日の取得と公開が丸ごと飛ぶ
            print(f"注意: index.json で city_code が付いた個票は {coded}/{len(known)}（9割未満）。"
                  "コード表と市区町村名の突き合わせ（common/addr.py の city_code_of）を見る")


# ---------------------------------------------------------------- 監査その5
def test_rowspan_colspan():
    """共通仕様9節：表の rowspan / colspan を展開して、列の位置がずれないこと。"""
    import parse
    # 見出しだけ colspan：2列ぶんに広がる
    t1 = ("<table><tr><th colspan='2'>店舗</th><th>届出日</th></tr>"
          "<tr><td>A店</td><td>大阪市</td><td>令和6年5月1日</td></tr></table>")
    rows = parse.rows_of(t1, "https://example.test/")
    eq([len(c) for c, _, _ in rows], [3, 3], "colspan の見出しが2列に広がり、行の長さが揃う")
    eq(rows[0][0], ["店舗", "店舗", "届出日"], "colspan は同じ文字を繰り返す")
    eq(rows[0][2][0] == rows[0][2][1], True, "colspan で広げた2列は同じセルから来たと分かる")
    eq(rows[0][2][1] == rows[0][2][2], False, "別のセルは別の出どころになる")
    # 本文に rowspan：2行目の先頭に1行目の値が下りてくる
    t2 = ("<table><tr><th>市</th><th>店舗</th><th>届出日</th></tr>"
          "<tr><td rowspan=\"2\">大阪市</td><td>A店</td><td>令和6年5月1日</td></tr>"
          "<tr><td>B店</td><td>令和6年6月1日</td></tr></table>")
    rows = parse.rows_of(t2, "https://example.test/")
    eq([c for c, _, _ in rows][1:], [["大阪市", "A店", "令和6年5月1日"], ["大阪市", "B店", "令和6年6月1日"]],
       "rowspan の値が次の行の同じ列位置に入る")
    eq(rows[1][2][0] == rows[2][2][0], True, "rowspan で下りてきた値は、元のセルの出どころを持ち回る")


def test_stale_party_marks_are_dropped():
    """5節：欄そのものが無い記録に、合流で運ばれた古い印（_kind/_display）を残さない。"""
    import merge
    rec = {"source": "kobe-city", "key": "demo-stale", "store": "テスト店",
           "operator_kind": "undisclosed", "operator_display": "個人", "address": "神戸市中央区1-1-1",
           "operator_suspect": "address", "operator_suspect_value": "大阪市北区梅田1丁目"}
    merge.apply_privacy([rec])
    eq("operator_kind" in rec, False, "欄が無いのに古い kind が残っている")
    eq("operator_display" in rec, False, "欄が無いのに古い display が残っている")
    eq("operator_suspect" in rec or "operator_suspect_value" in rec, False, "欄が無いのに古い印（住所の形）が残っている")


def test_address_shaped_operator_is_flagged():
    """5節「個人に化けてはいけないもの」：住所の形の値が設置者の欄に来たら、伏せたうえで記録に残す。"""
    import merge
    rec = {"source": "hirakata-city", "key": "demo-addr", "store": "テスト店",
           "operator": "枚方市大垣内町2丁目1番20号", "address": "枚方市大垣内町2丁目1番20号"}
    merge.apply_privacy([rec])
    eq(rec["operator"], "", "住所の形の値は index 用の欄に残さない")
    eq(rec["operator_kind"], "individual", "伏せる側（individual）に倒す")
    eq("個人" in rec["operator_display"], False, "画面に「個人」とは書かない（事実と違う）")
    eq("住所" in rec["operator_display"], True, "理由（設置者の欄に住所）を書く")
    eq(rec.get("operator_suspect"), "address", "列ずれの疑いの印が付く")
    eq("operator_suspect_value" in rec, False, "記録用の値は残さない（氏名が前に付いていることがある）")
    # 空白なしで氏名と住所がくっついた値でも、氏名がどこにも残らないこと
    rec9 = {"source": "osaka-pref", "key": "demo-addr9", "store": "テスト店",
            "operator": "架空太郎大阪市北区梅田一丁目1番1号", "address": "吹田市山田西二丁目1番30"}
    merge.apply_privacy([rec9])
    eq("架空太郎" in json.dumps(rec9, ensure_ascii=False), False, "氏名＋住所（空白なし）でも氏名が残らない")
    disp = rec["operator_display"]
    merge.apply_privacy([rec]); merge.apply_privacy([rec])
    eq(rec["operator_display"], disp, "伏せたあとに何度通しても文言と印が消えない")
    eq(rec.get("operator_suspect"), "address", "印も残る")
    # 「氏名 住所」が1つの欄に入っているものは先頭が住所ではないので拾わず、従来どおり「個人」。氏名はどこにも残らない
    rec2 = {"source": "hirakata-city", "key": "demo-addr2", "store": "テスト店",
            "operator": "架空　太郎　枚方市大垣内町2丁目1番20号", "address": "枚方市大垣内町2丁目1番20号"}
    merge.apply_privacy([rec2])
    eq(rec2.get("operator_suspect"), None, "氏名＋住所は住所の形として拾わない")
    eq(rec2["operator_display"], "個人", "氏名＋住所は「個人」")
    eq("架空" in json.dumps(rec2, ensure_ascii=False), False, "氏名がどの欄にも残らない")
    # 屋号・姓に数字＋番が入るもの（先頭が住所ではない）
    for nm in ("一番館", "二丁目食堂", "一番ヶ瀬架空"):
        rec3 = {"source": "x", "key": "k", "store": "s", "operator": nm, "address": "大阪市北区梅田1-1-1"}
        merge.apply_privacy([rec3])
        eq(rec3.get("operator_suspect"), None, f"{nm} は住所の形ではない")
    # 漢数字の地番は丸められないので、記録用の値を残さない
    rec4 = {"source": "x", "key": "k4", "store": "s", "operator": "神戸市中央区加納町三番一号", "address": "神戸市中央区加納町三番一号"}
    merge.apply_privacy([rec4])
    eq(rec4.get("operator_suspect"), "address", "漢数字の地番も住所の形として拾う")
    eq("operator_suspect_value" in rec4, False, "記録用の値は残さない")


def test_teisei_and_about_pages():
    """7節：訂正履歴のページがあり about から辿れる。8節：「やらないと決めたこと」が about にある。"""
    about = os.path.join(HERE, "about.html")
    teisei = os.path.join(HERE, "teisei.html")
    if not (os.path.exists(about) and os.path.exists(teisei)):
        print("about.html / teisei.html がまだ無い（ページを作ったあとに見る）")
        return
    a = open(about, encoding="utf-8").read()
    t = open(teisei, encoding="utf-8").read()
    eq("teisei.html" in a, True, "about から訂正履歴に辿れる")
    eq("やらないと決めたこと" in a, True, "about に「やらないと決めたこと」がある")
    eq(t.count("<tr>") >= 2, True, "訂正履歴に1件以上ある")
    eq("依頼フォーム" in a.split("連絡先")[1][:200] if "連絡先" in a else False, True, "連絡先はフォームが先")


def test_excel_fetched_on_is_download_day():
    ALL = os.path.join(HERE, "data", "all.json")
    """3.5：Excel から取り出した記録の取得日は、ダウンロードした日（自治体の一覧の日付ではない）。"""
    if not os.path.exists(ALL):
        return
    with open(ALL, encoding="utf-8") as f:
        recs = json.load(f)
    bad = [r for r in recs if r.get("source") == "osaka-city" and r.get("asof")
           and r.get("fetched_on") and r["fetched_on"] < r["asof"]]
    eq(len(bad), 0, f"大阪市の取得日が一覧の日付より前になっている {len(bad)} 件")
    same = [r for r in recs if r.get("source") == "osaka-city" and r.get("asof") and r.get("fetched_on") == r["asof"]]
    if same:
        # データの質の話で privacy の見張りではない。止めるとその日の取得と公開が丸ごと飛ぶ
        print(f"注意: 大阪市の取得日が一覧の日付そのものの記録が {len(same)} 件。"
              "data/files/fetched.json にその Excel の行があるか見る（3.5）")


def test_koho_extra_issues():
    """号外を取る：目録の番号の揃え方、月ページの見出しの読み方、ファイル名、追いついたら月2回（3.4）。"""
    import koho
    from datetime import date as _d
    k = _load_koho()
    eq(koho.norm_issue_no("423"), "423", "定期号はそのまま")
    eq(koho.norm_issue_no("号外"), "g1", "「号外」は g1")
    eq(koho.norm_issue_no("第2号外"), "g2", "「第2号外」は g2")
    eq(koho.norm_issue_no("第１２号外"), "g12", "全角の数字も読む")
    eq(koho.norm_issue_no("-"), "", "欠番は空")
    eq(k.issue_no_of_label("12月19日第679号"), (12, 19, "679"), "定期号の見出し")
    eq(k.issue_no_of_label("12月1日号外"), (12, 1, "g1"), "号外の見出し")
    eq(k.issue_no_of_label("12月3日第2号外"), (12, 3, "g2"), "第2号外の見出し（第2号と読み違えない）")
    eq(k.issue_no_of_label("12月3日号外第2号"), (12, 3, "g2"), "「号外第2号」の順でも第2号外")
    eq(k.issue_no_of_label("１２月１９日第６７９号"), (12, 19, "679"), "全角の数字も半角にして読む")
    eq(k.issue_no_of_label("12月19日 第679号"), (12, 19, "679"), "空白が入っていても読む")
    eq(k.issue_no_of_label("12月19日第679号PDF（250KB）"), (12, 19, "679"), "うしろに何か付いていても読む")
    eq(k.issue_no_of_label("目次"), None, "見出しでないものは None")
    eq(k.issue_no_of_label("12月の公報"), None, "日が無いものは None")
    eq(k.stem_of({"date": "2025-12-19", "no": "g2"}), "2025-12-19-g2", "号外のファイル名")
    # 書いた名前を読み返せること（書く側だけ号外に直して、読む側が取り残されていた）
    import tempfile
    d = tempfile.mkdtemp()
    for no in ("679", "g1", "g2", "g39"):
        name = k.stem_of({"date": "2025-12-19", "no": no}) + ".txt"
        with open(os.path.join(d, name), "w", encoding="utf-8") as f:
            f.write("# https://example.test/a.pdf\n")
        eq(k.parse_text_file(os.path.join(d, name)) is not None, True, f"{name} を読み返せる")
    with open(os.path.join(d, "へんな名前.txt"), "w", encoding="utf-8") as f:
        f.write("# x\n")
    eq(k.parse_text_file(os.path.join(d, "へんな名前.txt")), None, "読めない名前は None（落ちない）")
    # 号外は通し番号ではないので、年ずれの復旧を当てない
    eq(k.find_in_neighbor_year("2025-12-19", "g2", {}, []), (None, None), "号外に年ずれ復旧を当てない")
    eq(k.no_label("679"), "第679号", "人が読む文（定期号）")
    eq(k.no_label("g1"), "号外", "人が読む文")
    eq(k.no_label("g2"), "第2号外", "人が読む文")
    eq(k.fetch_today(500, _d(2026, 9, 20)), True, "積み直しの間は毎日")
    eq(k.fetch_today(5, _d(2026, 9, 20)), False, "追いついたら 1日・15日以外は取りに行かない")
    eq(k.fetch_today(5, _d(2026, 10, 1)), True, "追いついても 1日は取りに行く")
    eq(k.fetch_today(5, _d(2026, 9, 20), force=True), True, "手で押したときは取りに行く")
    # 号外は日ごとに番号が振り直されるので、発行日のまとめ直し（年ずれの復旧）の対象にしない
    fixed, merged = koho.merge_issue_dates({
        "2025-01-10#g1": {"date": "2025-01-10", "no": "g1", "titles": 1, "topics": {}},
        "2025-02-10#g1": {"date": "2025-02-10", "no": "g1", "titles": 1, "topics": {}},
        "2025-01-10#423": {"date": "2025-01-10", "no": "423", "titles": 3, "topics": {}},
        "2026-01-10#423": {"date": "2026-01-10", "no": "423", "titles": 1, "topics": {}},
    })
    eq(sorted(fixed), ["2025-01-10#423", "2025-01-10#g1", "2025-02-10#g1"], "号外は別々のまま、定期号の年ずれはまとまる")
    eq(len(merged), 1, "まとめたのは定期号の1件だけ")


def test_parsed_is_scrubbed():
    """5節：data/parsed も公開するので、伏せ処理を通っていること。

    apply_privacy は何度通しても同じ（冪等）なので、もう一度通して値が変わるなら
    その日ごとのファイルは伏せ処理を通っていない。生成物だけ手で作り直して
    commit した日に、地番が公開側に戻るのを止める。
    """
    import copy
    import merge
    paths = sorted(glob.glob(os.path.join(HERE, "data", "parsed", "*", "*.json")))
    if not paths:
        return
    bad = Counter()
    for p in paths:
        with open(p, encoding="utf-8") as f:
            try:
                recs = json.load(f)
            except Exception:
                continue
        if not isinstance(recs, list):
            continue
        for r in recs:
            if not isinstance(r, dict):
                continue
            again = copy.deepcopy(r)
            merge.apply_privacy([again])
            if again != r:
                bad[os.path.relpath(p, HERE)] += 1
    for k_, v in bad.most_common(5):
        fails.append(f"data/parsed が伏せ処理を通っていない: {k_} で {v} 件（merge.py を通してから commit する）")
    if len(bad) > 5:
        fails.append(f"…ほか {len(bad) - 5} ファイル")


# ---------------------------------------------------------------- 監査その5の再審査

def test_note_row_is_not_a_notice():
    """3.1：結合セルで書かれた注記の行を、届出1件として読まない。

    「全列が同じ値」だけでは足りない。上の行から rowspan で年度などが1列だけ
    下りてくると値が2種類になり、ガードをすり抜けて注記の本文（氏名や地番を
    含みうる）が店名と所在地になった記録ができる（監査で再現された穴）。
    """
    import parse
    head = ("<table><tr><th>年度</th><th>店舗名称</th><th>所在地</th>"
            "<th>設置者</th><th>届出日</th></tr>")
    note = "※令和7年4月1日から様式が変わりました。問い合わせは架空市役所まで"
    # (a) 上から rowspan で「令和7年度」が1列だけ下りてくる注記の行
    t = (head
         + "<tr><td rowspan='2'>令和7年度</td><td>アイウ店</td><td>架空市1丁目</td>"
           "<td>株式会社カブシキ</td><td>令和7年5月1日</td></tr>"
         + f"<tr><td colspan='4'>{note}</td></tr></table>")
    recs = parse.extract_generic(t, "https://example.test/", "見出し")
    eq([r["store"] for r in recs], ["アイウ店"], "rowspan が下りてくる注記の行を届出として読んでいる")
    # (b) 全幅の注記の行（今までも飛ばせていた形）
    t2 = head + f"<tr><td colspan='5'>{note}</td></tr></table>"
    eq(parse.extract_generic(t2, "https://example.test/", "見出し"), [],
       "全幅の注記の行を届出として読んでいる")
    # (c) ふつうの行は飛ばさない
    t3 = (head + "<tr><td>令和7年度</td><td>エオ店</td><td>架空市2丁目</td>"
          "<td>株式会社カブシキ</td><td>令和7年6月1日</td></tr></table>")
    eq([r["store"] for r in parse.extract_generic(t3, "https://example.test/", "見出し")],
       ["エオ店"], "ふつうの行まで注記として飛ばしている")
    # (d) 飛ばした行の本文を data/parse-unknown.md の例に書かない
    for src, ex in parse.EXAMPLE.items():
        for (kind, name), v in ex.items():
            if "注記とみなして飛ばした" in kind:
                fails.append(f"注記の本文を parse-unknown.md に書いている: {src} {name} {v[:30]}")


def test_extra_is_scrubbed_like_a_party():
    """3.1：知らない列（extra）に当事者が入っていても、privacy を通す。

    伏せたあとの値で「他の欄の複製か」を見ていたため、個人の氏名（空文字に
    なっている）が一覧に入らず、extra に残った同じ氏名が素通りしていた。
    """
    import merge, copy
    rec = {"source": "demo", "key": "demo-extra", "store": "アイウ店",
           "address": "架空市架空町1丁目1番1号", "operator": "架空太郎",
           "extra": {"届出者": "架空太郎",                 # 設置者の複製 → 消す
                     "備考": "架空市別町5-6-7",            # ハイフンの地番 → 丸める
                     "所在": "架空市架空町1-2-3",          # 丸めると所在地と同じ → 消す
                     "摘要": "代表者 架空花子",             # 頭が人を指す語 → 名前だけ伏せる
                     "小売業者": "株式会社カブシキ",         # 名前の列だが法人 → そのまま
                     "設置者（氏名）": "架空三郎",           # 括弧つきの名前の列 → 伏せる
                     "小売業者 （名称）": "架空四郎",         # 空白＋括弧 → 伏せる
                     "備考2": "代表者：架空五郎",            # コロン区切り → 名前だけ伏せる
                     "備考3": "代表取締役 架空 六郎",        # 姓名の間に空白 → 名前だけ伏せる
                     "変更理由": "代表者変更のため",         # 名前ではない文 → そのまま
                     "設置者対応": "ー",                    # 名前の列ではない → そのまま
                     "受理 番号": "862"}}
    merge.apply_privacy([rec])
    ex = rec.get("extra", {})
    eq("届出者" in ex, False, "設置者と同じ氏名が extra に残っている")
    eq(any("架空太郎" in str(v) for v in ex.values()), False, "伏せた氏名が extra のどこかに残っている")
    eq(any("架空花子" in str(v) for v in ex.values()), False, "「代表者 ○○」の氏名が extra に残っている")
    eq(ex.get("摘要"), "代表者 個人", "「代表者 ○○」の伏せ方が違う")
    eq(ex.get("小売業者"), "株式会社カブシキ", "法人名まで伏せている")
    eq(ex.get("設置者（氏名）"), "個人", "括弧つきの名前の列（設置者（氏名））をすり抜けている")
    eq(ex.get("小売業者 （名称）"), "個人", "空白＋括弧の名前の列をすり抜けている")
    eq(ex.get("備考2"), "代表者 個人", "コロン区切りの「代表者：○○」をすり抜けている")
    eq(ex.get("備考3"), "代表取締役 個人", "姓名の間に空白のある「代表取締役 姓 名」をすり抜けている")
    for bad in ("架空三郎", "架空四郎", "架空五郎", "六郎"):
        eq(any(bad in str(v) for v in ex.values()), False, f"{bad} が extra に残っている")
    eq(ex.get("変更理由"), "代表者変更のため", "名前ではない文まで伏せている")
    eq(ex.get("設置者対応"), "ー", "名前の列でない「設置者対応」を伏せている")
    eq(ex.get("受理 番号"), "862", "関係のない列を消している")
    eq(ex.get("備考"), "架空市別町5丁目", "ハイフンの地番を丸めていない")
    eq("所在" in ex, False, "丸めたら所在地と同じになる列を消していない（足すと二重に持つ）")
    # 個人が入る列なら「個人」に落ちる
    rec2 = {"source": "demo", "key": "demo-extra2", "store": "エオ店", "address": "架空市2丁目",
            "operator": "株式会社カブシキ", "extra": {"設置者の代表者氏名": "架空次郎"}}
    merge.apply_privacy([rec2])
    eq(rec2.get("extra", {}).get("設置者の代表者氏名"), "個人", "名前の列の個人名を伏せていない")
    # 何回通しても同じ
    once = copy.deepcopy(rec)
    merge.apply_privacy([rec])
    eq(rec, once, "apply_privacy を2回通すと extra の中身が変わる（冪等でない）")


def test_hyphen_banchi_is_an_address():
    """3.1：ハイフンで書いた地番も住所として扱う（「番地」の語が無い形）。"""
    import merge
    # 設置者の欄に住所だけが書かれている形（ハイフン）も拾う
    eq(merge.looks_like_address("架空市架空町1-2-3"), True, "住所だけの設置者名（ハイフン）を見逃している")
    eq(merge.looks_like_address("株式会社カブシキ"), False, "法人名を住所と見ている")
    eq(merge.looks_like_address("架空市架空町1丁目1番1号"), True, "「番地」の形の住所を見逃している")
    # OCR の「変更した事項」から住所を拾わない入口フィルタも、この形を見ていること
    eq(bool(re.search(r"氏名|代表者", "架空市架空町1-2-3")
            or merge.ADDR_SHAPE.search("架空市架空町1-2-3")
            or merge.ADDR_HYPHEN.search("架空市架空町1-2-3")), True,
       "OCR の入口フィルタがハイフンの地番を素通りさせる")
    for a in ("架空市架空町1-2-3", "架空市架空町1-2", "架空区架空町1－27－9"):
        eq(bool(merge.ADDR_HYPHEN.search(a)), True, f"ハイフンの地番を住所と見ていない: {a}")
    for a in ("2026-09-16", "令和8年7月3日から令和8年11月4日", "862", "9-12時"):
        eq(bool(merge.ADDR_HYPHEN.search(a)), False, f"住所でないものを住所と見ている: {a}")


# ---------------------------------------------------------------- 監査その5の再審査（続き）

def test_recon_stops_when_busy():
    """3.4：相手が 429/503 と言ったら、その収集先は今回そこで終わる。

    辿った先で混雑を受けても止めずに次のURLへ行っていたので、同じホストに
    上限（FOLLOW_BUDGET=32）まで5秒おきに当たり続けていた（監査で見つかった）。
    ネットには出ない。fetch と robots と sleep を差し替えて、回数だけ数える。
    """
    import recon, json, tempfile, urllib.error, time, io as _io, contextlib
    ENTRY = "https://example.test/"
    got = []

    def fake_fetch(url):
        got.append(url)
        if url == ENTRY:
            # 表もExcelもPDFも無いページ＝「わからない」→ この先を辿りに行く
            return 200, "text/html; charset=utf-8", "<html><body>目次</body></html>".encode()
        raise urllib.error.HTTPError(url, 429, "Too Many Requests", {}, None)

    keep = (recon.HERE, recon.fetch, recon.check_robots, recon.follow_links, time.sleep)
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "sources.json"), "w", encoding="utf-8") as f:
            json.dump({"sources": [{"id": "demo", "name": "架空市", "url": ENTRY}]}, f)
        recon.HERE = d
        recon.fetch = fake_fetch
        recon.check_robots = lambda u: (True, "許可")
        recon.follow_links = lambda page, base: [(f"{ENTRY}y{i}", f"令和{i}年度") for i in range(10)]
        time.sleep = lambda *_a, **_k: None
        try:
            with contextlib.redirect_stdout(_io.StringIO()):
                recon.main()
        finally:
            recon.HERE, recon.fetch, recon.check_robots, recon.follow_links, time.sleep = keep

    # 入口1本 ＋ 辿った先の1本目で 429 → そこで終わる
    eq(len(got), 2, f"混んでいると言われたのに押し込んでいる（{len(got)}回 要求した。2回で止まるはず）")


def test_every_fetcher_stops_when_busy():
    """3.4：取りに行くスクリプトは全部、429/503 でその回を中止すること。

    recon.py だけ is_busy を見ていなかった。1本忘れると、そこだけ押し込む。
    """
    for name in ("recon.py", "files.py", "wayback.py", "koho_pdf.py"):
        src = open(os.path.join(HERE, name), encoding="utf-8").read()
        eq("is_busy" in src, True, f"{name} が 429/503 を見ていない（共通仕様3.4）")
        stops = re.search(r"if is_busy\(e\):(?:[^\n]*\n){1,8}?[ \t]*(break|raise|return)", src)
        eq(bool(stops), True, f"{name} は 429/503 を見ているが、そこで止めていない")


# ---------------------------------------------------------------- 監査：#37 の再審査

def test_party_column_is_judged_in_one_place():
    """3.1：列の見出しが「名前の欄」かの判定は、1か所だけに置く。

    parse.py（例を書かない）と merge.py（値を伏せる）が別々に持っていて、
    落とす記号が違ったため「設置者（氏名）」が merge 側だけすり抜けた。
    表記のゆれ（空白・括弧・中黒）で破れないこと。
    """
    from common import privacy
    import parse, merge
    NAME = ("設置者", "小売業者", "設置者氏名", "設置者（氏名）", "設置者(氏名)",
            "小売業者 （名称）", "設置者・代表者", "設置者の氏名又は名称",
            "氏名（法人にあっては名称）", "代表取締役", "届出者（代表者）")
    NOT = ("設置者対応", "設 置 者 対 応", "変更理由", "縦覧場所 （県民局等）",
           "受理 番号", "店舗面積", "年度", "公告", "勧告", "届出書の概要",
           "営業時間", "取扱品目", "駐車台数 (駐輪台数)", "基準面積以下となる日", "No")
    for k in NAME:
        eq(privacy.is_party_column(k), True, f"名前の列を見落としている: {k}")
    for k in NOT:
        eq(privacy.is_party_column(k), False, f"名前の列でないものを名前の列と見ている: {k}")
    # 2つのファイルが同じ判定を使っていること（別々の正規表現を持たない）
    src = open(os.path.join(HERE, "merge.py"), encoding="utf-8").read()
    src += open(os.path.join(HERE, "parse.py"), encoding="utf-8").read()
    eq("EXTRA_PARTY_KEY" in src or "PARTY_COL" in src, False,
       "名前の列の判定が common/privacy.py の外にも残っている（2か所あると食い違う）")


def test_empty_rows_are_not_called_notes():
    """9節：中身が空なだけの行を「注記」と書かない（公開する報告書なので）。

    阪南市の縦長の表を横に倒すと空の行ができる。実データで75件あり、
    どれも data/parse-unknown.md に「注記とみなして飛ばした」と載っていた。
    """
    import parse
    parse.EXAMPLE.clear(); parse.UNKNOWN.clear()
    parse.CURRENT["source"] = "demo-empty"
    # 阪南市の形：「項目名 | 値」の縦長の表。横に倒すと、値が全部空の行になる
    t = ("<table>"
         "<tr><td>店舗の名称</td><td></td></tr>"
         "<tr><td>所在地</td><td></td></tr>"
         "<tr><td>届出年月日</td><td></td></tr>"
         "<tr><td>設置者</td><td></td></tr>"
         "</table>")
    parse.extract_generic(t, "https://example.test/", "見出し")
    kinds = [k for (k, _n) in parse.UNKNOWN.get("demo-empty", {})]
    eq(any("注記" in k for k in kinds), False, f"中身が空の行を注記と呼んでいる: {kinds}")
    eq(any("中身が空" in k for k in kinds), True, f"空の行を書き留めていない: {kinds}")


def test_placeholder_is_not_a_duplicate():
    """3.1：「―」「なし」は値ではなく文言。複製として消すと、列があったことまで消える。"""
    import merge
    rec = {"source": "demo", "key": "demo-ph", "store": "アイウ店", "address": "架空市1丁目",
           "operator": "株式会社カブシキ", "retailer": "―",
           "extra": {"小売業者": "―", "店舗面積": "919平方メートル"}}
    merge.apply_privacy([rec])
    eq(rec.get("extra", {}).get("小売業者"), "―", "「―」の列が黙って消えている")


# ---------------------------------------------------------------- 巡回の実測から

def test_month_page_is_not_refetched_after_refusal():
    """3.4：一度「取り直さない」と決めた月を、同じ実行の中で何度も取りに行かない。

    月ページの取り直しで定期号が減っていたら控えを書かずに返す（作りが変わった
    疑い）。印を付けないと、その月は次に呼ばれてもまた「古い版」に見えるので、
    その月の号の数だけ県のサーバーに行く。
    実測（2026-09-17 の巡回）：2025-12 に27回、4か月で40回＝取り直しの枠ぜんぶ。
    ネットには出ない。get を差し替えて回数だけ数える。
    """
    import koho_pdf, json as _json, tempfile, time, os as _os
    YM = "2025-12"
    PAGE = ('<a href="/a/202512-560.pdf">12月3日第560号</a>')   # 定期号は1つだけ
    calls = []

    def fake_get(url, limit=None):
        calls.append(url)
        return PAGE.encode()

    keep = (koho_pdf.MONTHS, koho_pdf.get, dict(koho_pdf._month_failed),
            koho_pdf._month_refreshed, koho_pdf._asked, time.sleep)
    with tempfile.TemporaryDirectory() as d:
        koho_pdf.MONTHS = d
        with open(_os.path.join(d, f"{YM}.json"), "w", encoding="utf-8") as f:
            _json.dump({"_v": 1, "12-3-560": "u1", "12-6-561": "u2", "12-9-562": "u3"}, f)
        koho_pdf.get = fake_get
        koho_pdf._month_failed.clear()
        koho_pdf._month_refreshed = 0
        koho_pdf._asked = 0
        time.sleep = lambda *_a, **_k: None
        lines = []
        try:
            for _ in range(5):                       # その月の号を5つ処理したつもり
                koho_pdf.month_links(YM, "https://example.test/m", lines)
        finally:
            (koho_pdf.MONTHS, koho_pdf.get, _f,
             koho_pdf._month_refreshed, koho_pdf._asked, time.sleep) = keep
            koho_pdf._month_failed.clear(); koho_pdf._month_failed.update(_f)

    eq(len(calls), 1, f"断った月を何度も取りに行っている（{len(calls)}回。1回で止まるはず）")
    eq(sum(1 for l in lines if "減った" in l), 1,
       f"同じ警告を報告に何度も書いている（{sum(1 for l in lines if '減った' in l)}回）")


def test_masked_splits_zero_from_hidden():
    """3.2「伏せた升と本当に0件の升は見た目で分ける」の count 側。

    masked() は機械が持つ値、bucket_count() は人に見せる文字列。
    6節の count / count_label の2本立てと同じ分け方。
    """
    eq(privacy.masked(0), 0, "0件は 0 のまま（伏せた升と分ける）")
    eq(privacy.masked(1), None, "1件は None（伏せる）")
    eq(privacy.masked(2), None, "2件は None（伏せる）")
    eq(privacy.masked(3), 3, "3件はそのまま")
    eq(privacy.masked(None), 0, "値が無いときは 0")


def test_zero_count_keeps_its_rate():
    """0件は率を伏せない。3.2 が心配しているのは小さい母数で率が跳ね上がること。

    0件を伏せると、本当に0件の升が「率を出していない」側に落ちて、
    伏せた升と見分けがつかなくなる。2026-09-17 に正本が直ったが、
    ここの実装は「件数2件以下」のままだった（率は本番未使用で実害は無かった）。
    """
    eq(privacy.suppress_rate(0, 10000), False, "0件は率を出してよい")
    eq(privacy.suppress_rate(1, 10000), True, "1件は率を出さない")
    eq(privacy.suppress_rate(2, 10000), True, "2件は率を出さない")
    eq(privacy.suppress_rate(3, 10000), False, "3件は率を出してよい")
    eq(privacy.suppress_rate(0, 400), True, "人口が足りなければ0件でも出さない")


_HAND_WRITTEN_SUPPRESS = re.compile(
    r"1\s*<=\s*\w+\s*<=\s*2"          # 1 <= c <= 2
    r"|\w+\s+in\s*\(\s*1\s*,\s*2\s*\)"   # c in (1, 2)
)


def test_count_side_goes_through_masked():
    """伏せる判断を privacy の外に手で書いていないか（共通仕様5節）。

    masked() が無かったあいだ、3つのサイトが同じ判断をそれぞれ手で書いていた。
    たまたま3つとも合っていたので誰も気づかなかった。次に書く人が外す。
    判断は1か所に置き、出力する経路は必ずそこを通す（2026-09-17）。
    """
    bad = []
    targets = glob.glob(os.path.join(HERE, "*.py")) + glob.glob(os.path.join(HERE, "common", "*.py"))
    for path in targets:
        name = os.path.basename(path)
        if name.startswith("test_") or name == "privacy.py":
            continue   # 検査そのものと、判断を持っている当人は除く
        with open(path, encoding="utf-8", errors="ignore") as f:
            for i, line in enumerate(f, 1):
                if _HAND_WRITTEN_SUPPRESS.search(line):
                    bad.append(f"{os.path.relpath(path, HERE)}:{i}")
    if bad:
        fails.append(f"伏せる判断を privacy の外に手で書いている箇所 {len(bad)}"
                     f"（{bad[:4]}）。privacy.masked() を通すこと")


def test_taiten_hides_how_long_individuals_stayed():
    """退店の一覧で、個人の設置者に「何年いたか」を出していないか（3.1）。

    「誰がいつまでそこにいたか」になる。一覧には出すが、年数は出さない。
    住所は merge の時点で町丁目まで丸めてある。
    """
    path = os.path.join(HERE, "data", "taiten.json")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        rows = json.load(f)["records"]

    bad = [r for r in rows
           if r.get("operator_kind") == "individual" and r.get("lasted_days")]
    if bad:
        fails.append(f"個人の設置者に在店年数が出ている {len(bad)}件。3.1")

    ban = re.compile(r"[0-9０-９]+\s*[-‐−－ー―]\s*[0-9０-９]+|[0-9０-９]+番地?[0-9０-９]*号?")
    addr_bad = [r for r in rows
                if r.get("operator_kind") == "individual" and ban.search(r.get("addr", ""))]
    if addr_bad:
        fails.append(f"個人の記録に地番が残っている {len(addr_bad)}件。3.1")

    name_bad = [r for r in rows
                if r.get("operator_kind") == "individual"
                and r.get("operator") not in ("個人", "", "非公開", None)]
    if name_bad:
        fails.append(f"個人の設置者名がそのまま出ている {len(name_bad)}件。3.1")


def test_taiten_matches_only_on_store_name():
    """突き合わせが「町丁目だけ」で繋がっていないか。

    同じ町丁目の別の店を拾う。実測で、町丁目の一致 55件のうち
    店名まで一致したのは 9件だけだった（2026-09-19）。
    繋いだものには必ず店名の一致を含める。
    """
    path = os.path.join(HERE, "data", "taiten.json")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        rows = json.load(f)["records"]
    bad = [r for r in rows if r.get("lasted_days") and "店名" not in (r.get("match") or "")]
    if bad:
        fails.append(f"店名の一致なしで在店年数を出している {len(bad)}件")


def _settisha_rows():
    path = os.path.join(HERE, "data", "settisha.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)["stores"]


def test_settisha_hides_individual_parties():
    """設置者と小売業者の一覧に、個人の名前や地番が出ていないか（3.1）。

    この一覧は「建物を用意した人」と「店をやる人」を並べる。片方が個人なら、
    そこは住まいかもしれない。作った時点では両方の欄が法人だけだったので
    地番まで出している（2026-09-19）。出どころが変わればすぐ個人が混ざる。
    混ざった日に鳴るように、ここに置いておく（9節）。
    """
    rows = _settisha_rows()
    if not rows:
        return

    def hidden(kind, shown):
        if kind not in ("individual", "undisclosed"):
            return True
        n = (shown or "").strip()
        return (not n) or n in ("個人", "非公開") or privacy.is_placeholder(n)

    bad = [r for r in rows
           if not hidden(r.get("operator_kind"), r.get("operator_now"))
           or not hidden(r.get("retailer_kind"), r.get("retailer_now"))]
    if bad:
        fails.append(f"個人の当事者名がそのまま出ている {len(bad)}件。3.1")

    hbad = [r for r in rows for h in r.get("history", [])
            if not hidden(h.get("operator_kind"), h.get("operator"))
            or not hidden(h.get("retailer_kind"), h.get("retailer"))]
    if hbad:
        fails.append(f"履歴に個人の当事者名がそのまま残っている {len(hbad)}件。3.1")

    # 設置者が個人なら、住所は merge の時点で町丁目まで丸まっているはず。
    # 丸め忘れをここでも見る（5節「迂回検査」）
    ban = re.compile(r"[0-9０-９]+\s*[-‐−－ー―]\s*[0-9０-９]+|[0-9０-９]+番地?[0-9０-９]*号?")
    addr_bad = [r for r in rows
                if r.get("operator_kind") in ("individual", "undisclosed")
                and (ban.search(r.get("addr") or "") or ban.search(r.get("addr_key") or ""))]
    if addr_bad:
        fails.append(f"個人の設置者の記録に地番が残っている {len(addr_bad)}件。3.1")


def test_settisha_groups_by_banchi_not_town():
    """店のまとめ方が「町丁目」に落ちていないか。

    届出は同じ店に何度も出るので、まとめないと同じ店を何度も数える。
    ただし町丁目でまとめると、同じ町丁目の別の店が1つの店として混ざる。
    鍵を町丁目に落として作り直したら店が76減った。うち別の店に吸われたのが
    16件だった（2026-09-19）。
    退店履歴でも、町丁目の一致 55件のうち店名まで一致したのは
    9件だけだった（2026-09-19）。まとめる鍵は必ず番地まで見ること。
    """
    rows = _settisha_rows()
    if not rows:
        return

    sys.path.insert(0, os.path.join(HERE, "common"))
    import addr as addrlib

    bad = []
    for r in rows:
        try:
            n = addrlib.normalize(r.get("pref", ""), r.get("city", ""), r.get("addr", ""))
        except Exception:
            continue
        # 番地まで読めた住所なのに、町丁目の鍵でまとまっている
        if n.get("addr_key") and r.get("addr_key") == n.get("addr_key_town") \
                and n["addr_key"] != n["addr_key_town"]:
            bad.append(r.get("store"))
    if bad:
        fails.append(f"町丁目でまとめている店 {len(bad)}件。別の店が混ざる")

    # 同じ (店名, 番地) が2行に割れていないか。割れていると同じ店を二重に数える
    seen = Counter((r.get("store"), r.get("addr_key")) for r in rows)
    dup = [k for k, v in seen.items() if v > 1]
    if dup:
        fails.append(f"同じ店が複数行に分かれている {len(dup)}件")


def test_settisha_changes_match_history():
    """「表記が変わった回数」が、履歴と合っているか。

    合っていなければ、データが言っていないことを画面に書いている。
    履歴が日付の順に並んでいることも一緒に見る（並んでいなければ
    「いまの設置者」が最後の届出のものにならない）。
    """
    rows = _settisha_rows()
    if not rows:
        return

    order_bad, count_bad, now_bad = [], [], []
    for r in rows:
        h = r.get("history") or []
        dates = [x.get("date") or "" for x in h]
        if dates != sorted(dates):
            order_bad.append(r.get("store"))
        for field, shown in (("operator", "operator_changes"),
                             ("retailer", "retailer_changes")):
            names = [x.get(field) for x in h if x.get(field)]
            # 書き方の違いだけのもの（近鉄不動産(株) と 近鉄不動産株式会社）は
            # 数えない。ひと続きの並びとして数えるので、A→B→A→C は3回
            want, prev = 0, None
            for x in names:
                if prev is not None and prev != x and not privacy.same_corp(prev, x):
                    want += 1
                prev = x
            if r.get(shown) != want:
                count_bad.append((r.get("store"), field))
            now = names[-1] if names else ""
            if (r.get(field + "_now") or "") != now:
                now_bad.append((r.get("store"), field))
    if order_bad:
        fails.append(f"履歴が日付の順に並んでいない店 {len(order_bad)}件")
    if count_bad:
        fails.append(f"変わった回数が履歴と合わない {len(count_bad)}件")
    if now_bad:
        fails.append(f"「いまの当事者」が履歴の最後と違う {len(now_bad)}件")


def test_free_text_columns_do_not_hold_bare_numbers():
    """自由記入の欄に、数字だけの値が入っていないか。

    大阪府の一覧は見出しが2段で、「17. 備考欄」の下に「延床面積」
    「施設の用途地域」「その他」がぶら下がる。上の段しか読んでいなかったので、
    **延床面積を「備考」として拾い、用途地域は丸ごと落ちていた。**
    画面には「備考 10909」という、意味の分からない数だけが出ていた（2026-09-19）。

    **列がずれたことは、値の形に出る。** 自由記入の欄に数字しか入っていなければ、
    それは文章ではなく、どこかの列の数がそこに来ている。
    他の収集先の備考は「現店舗を閉鎖し、建て替えを行うため」のような文章で、
    数字だけのものは1件も無い。
    """
    path = os.path.join(HERE, "data", "all.json")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        recs = json.load(f)

    # 自由記入の欄。数だけが入る欄（area_m2 など）はここに入れない
    FREE = ("note", "content", "citizen_opinion", "city_opinion",
            "pref_opinion", "recommendation")
    bad = Counter()
    for r in recs:
        for k in FREE:
            v = str(r.get(k) or "").strip()
            # 「3」のような短い数は台数の記載などでありうる。4桁以上を見る
            if v.isdigit() and len(v) >= 4:
                bad[(r.get("source"), k)] += 1
    if bad:
        fails.append(f"自由記入の欄に数字だけの値がある {sum(bad.values())}件"
                     f"（{dict(list(bad.items())[:4])}）。列がずれている")


def test_floor_area_is_not_smaller_than_store_area():
    """延床面積が店舗面積より小さくなっていないか。

    延床面積は建物ぜんぶ、店舗面積は店の部分なので、**延床 ≧ 店舗** になる。
    逆転していたら、2つの列が入れ替わっているか、別の行の値を拾っている。
    見出しが2段の表では、上の段だけを読むとこれが起きる。

    同じ値になることはある（建物ぜんぶが店の場合）。そこは通す。
    """
    path = os.path.join(HERE, "data", "all.json")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        recs = json.load(f)

    both = [r for r in recs
            if isinstance(r.get("floor_area_m2"), (int, float))
            and isinstance(r.get("area_m2"), (int, float))]
    if not both:
        return
    bad = [r for r in both if r["floor_area_m2"] < r["area_m2"]]
    # 一次情報の側が逆転していることが、わずかにある（複数棟にまたがる店で、
    # 延床が1棟ぶんだけ書かれているなど）。**列が入れ替わっていれば、
    # わずかではなくほとんど全部が逆転する。** だから数ではなく割合で見る
    share = len(bad) / len(both)
    if share > 0.2:
        fails.append(f"延床面積が店舗面積より小さい記録が {share:.0%}。列が入れ替わっている")


def test_zoning_values_are_real_categories():
    """用途地域の欄に、用途地域でないものが入っていないか。

    都市計画法の用途地域は13種類と、市街化調整区域・市街化区域。
    それ以外の文字列が入っていたら、別の列を拾っている。
    複数の地域にまたがる店は「準工業地域、第一種住居地域」のように並ぶので、
    区切って1つずつ見る。
    """
    path = os.path.join(HERE, "data", "all.json")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        recs = json.load(f)

    sys.path.insert(0, os.path.join(HERE, "common"))
    import zoning as zoninglib

    got = unknown = 0
    names = Counter()
    for r in recs:
        if not r.get("zoning"):
            continue
        g, u = zoninglib.normalize(r["zoning"])
        got += len(g)
        unknown += len(u)
        for x in u:
            names[x] += 1
    if not (got + unknown):
        return
    # **列がずれると、ほとんど全部が読めなくなる。** 少し読めないのは
    # 出どころの言い方のばらつきで、そちらは common/zoning.py が吸収する。
    # 数ではなく割合で見る（9節「実測値を説明文に書かない」）
    share = unknown / (got + unknown)
    if share > 0.2:
        fails.append(f"用途地域の欄の {share:.0%} が用途地域として読めない"
                     f"（{list(names)[:4]}）。列がずれている")


def test_same_corp_sees_through_notation_only():
    """書き方が違うだけの社名を、同じ会社と見られるか。

    一覧によって ㈱／(株)／株式会社 が混ざり、全角と半角も混ざる。
    見分けられないと、**1ミリも変わっていないものを「変わった」と数える。**
    実測で、設置者が変わったとされる98件のうち17件がこれだった（2026-09-19）。

    **逆に、見えすぎてもいけない。** 商号変更・合併・持株会社化は名前が
    本当に変わるので、ここで同じと言ってはいけない。見分けるには法人番号が要る。

    社名は架空のものを使う。
    """
    same = [
        ("鯨屋不動産(株)", "鯨屋不動産株式会社"),
        ("㈱鯨屋不動産", "株式会社鯨屋不動産"),
        ("ＫＵＪＩＲＡリース(株)", "KUJIRAリース株式会社"),
        ("鯨屋建設(株)　ほか1者", "鯨屋建設株式会社　ほか１者"),
        ("鯨屋商事㈲", "鯨屋商事有限会社"),
    ]
    diff = [
        ("鯨屋電鉄株式会社", "鯨屋ホールディングス株式会社"),   # 持株会社化
        ("鯨屋信託銀行㈱", "海猫信託銀行㈱"),                   # 合併
        ("株式会社鯨屋", "株式会社海猫"),
        ("株式会社", "株式会社"),                               # 芯が無い。同じと言わない
    ]
    for a, b in same:
        if not privacy.same_corp(a, b):
            fails.append(f"書き方が違うだけの社名を別の会社と見ている（{a} / {b}）")
    for a, b in diff:
        if privacy.same_corp(a, b):
            fails.append(f"名前そのものが違う社名を同じ会社と見ている（{a} / {b}）")


def test_no_script_reads_the_clock_twice():
    """走らせるスクリプトが、時計を直に見ていないか。

    毎朝の巡回は 07:00 JST に始まり、終わるのは 09:10 JST ごろ。
    日付をまたぐ時刻に動くと、**同じ実行の中で日付が2つになる。**

        取ってきた日（recon が打つ）   2026-09-18
        commit の日（git が打つ）      2026-09-19

    サイトに出ていた取得日が、毎日1日早いほうだった（2026-09-19 に気づいた）。
    **決めるのは走り始めの1回。** 以降は common/runday.py だけが時計を見る。

    時間帯を日本時間に寄せるだけでは足りない。それは「たまたま日付を
    またがない」だけで、走る時刻が動けばまた起きる（3.5）。
    """
    targets = [f for f in glob.glob(os.path.join(HERE, "*.py"))
               + glob.glob(os.path.join(HERE, "common", "*.py"))
               if os.path.basename(f) not in ("runday.py", "test_privacy.py")]
    # date.today() / datetime.now() / time.time() を直に呼んでいる行
    clock = re.compile(r"\b(date\.today\(\)|datetime\.(now|today|utcnow)\(\)|time\.time\(\))")
    bad = []
    for f in targets:
        with open(f, encoding="utf-8") as fh:
            for i, line in enumerate(fh, 1):
                if line.lstrip().startswith("#"):
                    continue
                if clock.search(line):
                    bad.append(f"{os.path.basename(f)}:{i}")
    if bad:
        fails.append(f"時計を直に見ている箇所 {len(bad)}（{bad[:4]}）。"
                     f"common/runday.py の today() を通すこと")


def main():
    # 定義した test_ を名前で全部拾う（一覧に書き足し忘れて、走っていない検査があった）
    tests = [f for name, f in list(globals().items()) if name.startswith("test_") and callable(f)]
    print(f"検査 {len(tests)} 本")
    for t in tests:
        t()
    if fails:
        print(f"落ちた検査 {len(fails)} 件\n")
        for m in fails:
            print("  ✗ " + m)
        print("\nデータを取りに行く前に止めた。共通仕様3.1を読み直すこと。")
        return 1
    print("privacy の検査はすべて通った")
    return 0


if __name__ == "__main__":
    sys.exit(main())
