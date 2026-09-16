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
    eq([len(c) for c, _ in rows], [3, 3], "colspan の見出しが2列に広がり、行の長さが揃う")
    eq(rows[0][0], ["店舗", "店舗", "届出日"], "colspan は同じ文字を繰り返す")
    # 本文に rowspan：2行目の先頭に1行目の値が下りてくる
    t2 = ("<table><tr><th>市</th><th>店舗</th><th>届出日</th></tr>"
          "<tr><td rowspan=\"2\">大阪市</td><td>A店</td><td>令和6年5月1日</td></tr>"
          "<tr><td>B店</td><td>令和6年6月1日</td></tr></table>")
    rows = parse.rows_of(t2, "https://example.test/")
    eq([c for c, _ in rows][1:], [["大阪市", "A店", "令和6年5月1日"], ["大阪市", "B店", "令和6年6月1日"]],
       "rowspan の値が次の行の同じ列位置に入る")


def test_stale_party_marks_are_dropped():
    """5節：欄そのものが無い記録に、合流で運ばれた古い印（_kind/_display）を残さない。"""
    import merge
    rec = {"source": "kobe-city", "key": "demo-stale", "store": "テスト店",
           "operator_kind": "undisclosed", "operator_display": "個人", "address": "神戸市中央区1-1-1"}
    merge.apply_privacy([rec])
    eq("operator_kind" in rec, False, "欄が無いのに古い kind が残っている")
    eq("operator_display" in rec, False, "欄が無いのに古い display が残っている")


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
    eq("2丁目1番20号" in rec.get("operator_suspect_value", ""), False, "記録に残す値も町丁目までに丸める")
    disp = rec["operator_display"]
    merge.apply_privacy([rec]); merge.apply_privacy([rec])
    eq(rec["operator_display"], disp, "伏せたあとに何度通しても文言と印が消えない")
    eq(rec.get("operator_suspect"), "address", "印も残る")


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
    eq(len(same), 0, f"大阪市の取得日が一覧の日付そのものになっている {len(same)} 件（ファイル名の日付を取得日にしていないか）")


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
    eq(k.issue_no_of_label("目次"), None, "見出しでないものは None")
    eq(k.stem_of({"date": "2025-12-19", "no": "g2"}), "2025-12-19-g2", "号外のファイル名")
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


def main():
    for t in (test_is_corp, test_names, test_addr, test_small_numbers,
              test_all_json, test_generated_pages, test_public_urls,
              test_late_name_is_still_redacted, test_every_record_has_source,
              test_no_raw_small_counts_in_pages, test_no_empty_fetch_date_in_pages,
              test_fetch_etiquette, test_place_names, test_parse_keeps_unknown_columns,
              test_addr_normalize, test_jis_rows, test_index_json):
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
