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
            if not d or d == "個人":
                continue
            if privacy.is_corp(d) or privacy.is_placeholder(d):
                continue
            fails.append(f"{r.get('key','?')}: {f_}_display に伏せそこねた値: {d!r}")


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


def main():
    for t in (test_is_corp, test_names, test_addr, test_small_numbers,
              test_all_json, test_generated_pages, test_public_urls,
              test_late_name_is_still_redacted, test_every_record_has_source,
              test_no_raw_small_counts_in_pages, test_no_empty_fetch_date_in_pages,
              test_fetch_etiquette, test_place_names, test_parse_keeps_unknown_columns):
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
