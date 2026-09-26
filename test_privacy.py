#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""共通仕様 3.1 / 3.2 を守れているかの検査。

  https://github.com/VirgoB77/ogataten-nippo/blob/main/docs/kyotsu-shiyo.md

前半は common/privacy.py そのものの検査。
後半が本体で、公開する生成物を全部走査して、privacy.py を迂回した値が
1件でも残っていないかを見る（5節「privacy.py を迂回した出力が1件でもあれば落ちる検査を書く」）。

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


import contextlib as _contextlib


@_contextlib.contextmanager
def toosu_kado_mon(mod):
    """検査の中だけの**「通す偽の門」**。カードの門（common/kado.py）を素通りに差し替える。

    2026-09-25、取りに行く各段に共通指示書1のカードの門を入れた。
    門そのものの挙動（承認・robots・相手台帳・混雑）は tests/test_kado.py が
    確かめている。ここより下の検査は**門を試していない**——利用規約の関所・
    指紋の比べ方・条件付きGET・取得の完全性の判定など、**門を通ったあとの
    中身**を見ている。その検査が「門で止めた」に化けて中身を試せなくなるのを
    防ぐため、検査の中だけ `kado.hajimeru()` / `kado.genzai()` を、
    素通りする偽物に差し替える（呼び方が段によって違う——`main()` が
    `K = kado.hajimeru(...)` を局所変数で持つ段と、`kado.genzai()` を
    その都度呼ぶ段の両方がある。**本番のコードには「検査のときは通す」
    道を作らない**（共通指示書5）。

    `_genzai` は「セッションの中」だと分かる印（`common/kado.py` の同名の属性と同じ役目）。
    ここは**通した**あとの門なので、値を持たせておく——持たせないと、
    「最終URLが承認範囲内」（共通指示書2）を試す側が、セッションの外だと誤認する。
    """
    class _ToosuK:
        cards = {}
        _genzai = ("toosu", {}, ())

        def sesshon(self, cid, hozon_saki=None, **kw):
            return _contextlib.nullcontext()

        def card_mon(self, cid, hozon_saki=None, **kw):
            return []

        def install(self):
            return self

    fake = _ToosuK()
    moto_genzai, moto_hajimeru = mod.kado.genzai, mod.kado.hajimeru
    mod.kado.genzai = lambda: fake
    mod.kado.hajimeru = lambda *a, **kw: fake
    try:
        yield fake
    finally:
        mod.kado.genzai, mod.kado.hajimeru = moto_genzai, moto_hajimeru


# ---------------------------------------------------------------- is_corp
def subete_no_py(nozoku=("test_",)):
    """**この置き場の .py を全部拾う。1か所で拾う。**

    2026-09-20 の監査で出た。検査の中に**拾い方が4通り**あった。

        glob(HERE/*.py)                                  引数の関所
        glob(HERE/*.py) + glob(HERE/common/*.py)         3つの検査
        ＋ glob(HERE/scripts/*.py)                       読めるかの検査

    **`scripts/` はもう無い。** 逆に、`common/` を見ていない検査が1本あった。
    **新しい置き場に .py を1本足した日、どれが見てどれが見ないかは
    書いた人にも分からない。**

    だから**歩いて拾う。** 一覧も、階層の数も、決め打ちしない。
    """
    import os as _os
    de = []
    for ne, dirs, files in _os.walk(HERE):
        dirs[:] = [d for d in dirs
                   if not d.startswith(".") and d != "__pycache__"]
        for f in files:
            if f.endswith(".py") and not any(f.startswith(n) for n in nozoku):
                de.append(_os.path.join(ne, f))
    return sorted(de)


def soto_ni_deru():
    """**外に出て行く .py を、実物から拾う。** 名前で並べない。

    2026-09-19、開発系のやり方（`urlopen` を呼ぶか）を自分に当てたら、
    検査の中に**名前の一覧が2か所**あった。

        test_every_fetcher_stops_when_busy   ("recon.py", "files.py", …)
        decode の検査                        ("common/fetch.py", "koho_pdf.py", …)

    **同じ日に足した `chizu_recon.py` が、両方に入っていない。**
    429/503 を見ていなくても、文字コードを決め打ちしていても、**黙る。**
    """
    import re as _re
    DERU = _re.compile(r"from\s+common\.fetch\s+import|common\.fetch\b|urlopen\s*\(")
    # **`common/fetch.py` には、外に出ない道具も入っている。**
    # 文字コードを選ぶ `decode_html` は、**保存済みのバイトにも使う。**
    # それだけを借りている段は、**1回も外に出ない。**
    #
    # 2026-09-21、保存済みの1枚から識別子を抜くだけの段が、
    # **429/503 を見ていないと言われて落ちた。** 相手がいないのに。
    #
    # **名前では外さない。** その段が**つなぎに行く形を持っているか**で外す
    DENAI = ("decode_html", "ja_score", "bakete_inai")
    TSUNAGU = _re.compile(r"urlopen\s*\(|urllib\.request\.(?:Request|urlopen)|"
                          r"\b(?:check_robots|is_busy|Konde|UA|WAIT|TIMEOUT)\b")
    de = []
    for m in subete_no_py():
        src = open(m, encoding="utf-8").read()
        if not DERU.search(src):
            continue
        if not TSUNAGU.search(src):
            continue            # **道具だけ借りている。外には出ない**
        de.append(m)
    return de


def workflow_files():
    """workflow の一覧。**拡張子を1つに決め打ちしない。**

    2026-09-19、競売統計が見つけた。`*.yml` しか見ていない見張りは、
    **`.yaml` で書かれたものを1本も見ない**（向こうでは18本が黙っていた）。
    GitHub は両方を読む。**見張りだけが片方しか読まない。**

    「見張りを名前の一覧で作らない」（9節）の、拡張子版。
    """
    import glob
    michi = os.path.join(HERE, ".github", "workflows")
    return sorted(glob.glob(os.path.join(michi, "*.yml"))
                  + glob.glob(os.path.join(michi, "*.yaml")))


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
    # 「1件ずつ」のような**数えた件数でない言い回し**には当てない。
    # 誤報を出す見張りは、そのうち読まれなくなる（9節）。件数のあとに来るのは
    # 「。」「の」「（」などで、「ずつ」は来ない（2026-09-19）
    r"|class=\"lead\">[12]件(?!ずつ)"    # 市区町村ページ・種別ページの先頭行
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
    """robots の判定・混雑の判定・恒久失敗の扱い・目録の年ずれの復旧・空本文の見張り。ネットには出ない。

    2026-09-25、robots.txt を取って判定する中身は `common/kado.py` の門へ引っ越した
    （`common/fetch.py.check_robots` は `kado.robots_kekka()` に聞くだけの窓口）。
    そちらの判定そのもの（404は許可・429/503は混んでいる・401/403/5xxは確かめられ
    なかった・読めた規則の当てはめ）は tests/test_kado.py の robotsの応答／
    robots照合器 で確かめてある。ここで見るのは**門を通っていないときに、
    check_robots が許可／拒否を言い切らないか**——以前の「robots.txt が空なら許可」
    のような fail-open の再発を防ぐ、fail-closed の側の確認。
    """
    import urllib.error
    from datetime import date as _d
    from common import fetch, kado
    eq(kado.genzai(), None, "この検査の中では門（common/kado.py）を始めていない")
    ok, why = fetch.check_robots("https://x.example.invalid/kk32/a.pdf")
    eq(ok, None,
       "門を始めていないのに check_robots が許可／拒否を言い切っている（fail-open の再発）")
    eq(bool(why), True, "確かめられなかった理由を必ず返す（黙って None にしない）")
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


# 2026-09-19 に測った値。**増えたら鳴る。減っても鳴る**（減ったのに
# この数を直し忘れたら、次の悪化に気づけなくなる）。
# 直すには町丁目の一覧（data/ref/towns.json）が要る。まだ無い
# 2026-09-19 に 1369 → 2209 に増えた。**直した結果として増えた。**
# 丁目の無い住所で、地番が町丁目に入っていたのを空にしたため（845件）。
# 丁目のある行を巻き込んでいないことは、直す前後を全件比べて確かめた（0件）
# 2026-09-20 に 4,809件中2,209件 → 4,828件中2,226件。**理由を見てから直した。**
# 増えた19件のうち14件は、新しく拾った保存（2026-06-08）の兵庫県の縦覧で、
# **一覧のページに所在地の列が無い**（実物の見出しは
# 届出年月日・店舗名称・縦覧期間・概要の4つだけ）。読み方は壊れていない。
# 残り5件は堺市と兵庫県の新しい届出で、こちらは町丁目までつながっている
# 2026-09-21 に動いた。**増えたので、先に理由を見た**（検査が言うとおり）。
#   前 4,828件中 2,226件 → いま 4,825件中 2,228件
# **住所の読み方は壊れていない。** 鍵が前にもある 4,796件で、
# `pref` `city` `address` `ward` が変わったのは **0件**。
# 動いたのは**店名の寄せ方を直した**ぶん（`merge.py`・法人格を正本に通した）で、
# **29件の鍵が付け替わり、3件が重複としてまとまった。**
# **数えた日に数を直す。理由を見ないまま直さない。**
# 2026-09-22 に動いた。**減ったので、理由を見てから直した**（検査が言うとおり）。
#   前 4,361件中 1,764件 → いま 4,361件中 1,669件
# 西宮市の町丁目一覧435件（国交省2025年版）を data/ref/towns.json に入れた。
# **西宮市だけ。**他の市は一覧がまだ無いので、これまでどおり空のまま。
#   西宮市の空 105 → 10（②で47・①'で48 が決まった）
#   もとから決まっていた行の値が変わったのは **0件**
TOWN_GAP = 1669
TOWN_TOTAL = 4361     # **住所が読めた行だけ。** 原典に住所が無い行は下で別に数える
TOWN_NASHI = 464      # 原典に住所が書かれていなかった行（こちらでは減らせない）


# 2026-09-22 に測った値。**いま町丁目まで決まっている行の数。**
# 一覧を入れたら増える。**減ったら、決まっていたものが決まらなくなった**ので鳴る
# **2つの数を分ける。** 片方だけだと「一覧が効いた」と「決まらなくなった」が混ざる
TOWN_KIMATTA_NASHI = 2597   # 一覧を外したとき＝丁目から決まる行だけ。ここが減ったら壊れた
TOWN_KIMATTA_ARI = 2692     # いまの towns.json を当てたとき（2026-09-22。西宮市435件）


def _towns_wo_sashikomu(ichiran):
    """町丁目の一覧を差し込む。**ファイルには書かない。**戻すのは呼ぶ側。"""
    import addr as _a
    moto = _a._towns
    _a._towns = ichiran
    return moto


def _shirushi_no_naka(text):
    """`<!-- 数えた値を書かない：ここから（…） -->` で挟まれた区間を返す。

    **日本語の見出しで範囲を切らない**（2026-09-22）。
    見出しの文言で挟むと、言い回しを整えただけで落ちる。
    実際、範囲を `##` までにしたら385行・7小見出しに広がり、
    **日付つきの過去の実測まで鳴った。**

    目印は人が読んでも邪魔にならず、**何のための印かが読めばわかる**形にする。
    """
    HAJIME = re.compile(r"<!--\s*数えた値を書かない：ここから（([^）]*)）\s*-->")
    OWARI = "<!-- 数えた値を書かない：ここまで -->"
    out = []
    for m in HAJIME.finditer(text):
        e = text.find(OWARI, m.end())
        if e < 0:
            raise AssertionError(
                f"「数えた値を書かない：ここから（{m.group(1)}）」に、"
                "対になる「ここまで」が無い")
        out.append((m.group(1), text[m.end():e]))
    return out


def _ichiran_no_shi():
    """いま町丁目の一覧を持っている市の名前。**検査に名前を書かない。**

    `data/ref/towns.json` の鍵（市区町村コード）を、
    `data/ref/jis-codes.json`（総務省の全国地方公共団体コード）で名前に直す。
    市が増えても、この検査は直さなくてよい。
    """
    import json
    t = os.path.join(HERE, "data", "ref", "towns.json")
    c = os.path.join(HERE, "data", "ref", "jis-codes.json")
    if not (os.path.exists(t) and os.path.exists(c)):
        return []
    with open(t, encoding="utf-8") as f:
        code = set(json.load(f))
    with open(c, encoding="utf-8") as f:
        return [r.get("city", "") for r in json.load(f) if r.get("code") in code]


def test_数えた値を書かない印の中に件数が無いか():
    """**手で書いた数には、持ち主がいない**（2026-09-22 に4件見つけた）。

    現在の件数は、数えた段が生成物に書く。文書はそこを見る。

        addr_katachi.py  →  data/ref/addr-katachi.md
        town_gap.py      →  data/ref/town-gap.md
        build_site.py    →  index.json の not_counted

    その古い写しが文書に残っていた。**数字を新しくするのではなく、手書きをやめた。**
    ここでは印で挟んだ区間だけを見る。**過去の実測や事故の記録は禁じない**
    （日付つきで残すもの。機械で一律に止めると、履歴まで消える）。
    """
    for michi in (os.path.join(HERE, "docs", "kyotsu-shiyo.md"),
                  os.path.join(HERE, "docs", "nokori.md")):
        if not os.path.exists(michi):
            continue
        with open(michi, encoding="utf-8") as f:
            text = f.read()
        kukan = _shirushi_no_naka(text)
        if michi.endswith("kyotsu-shiyo.md") and len(kukan) < 3:
            raise AssertionError(
                f"正本の「数えた値を書かない」の印が {len(kukan)} 区間しか無い。"
                "**印を消すと、そこに件数を書き戻せる**")

        for na, s in kukan:
            # ① 件数・割合。**しきい値は別**（範囲の後ろ側・以上/以下/未満/超）
            warui = []
            for m in re.finditer(r"([0-9][0-9,]{1,})\s*(件|本|行|枚|欄)|([0-9]+\.[0-9])\s*%", s):
                mae = s[max(0, m.start() - 1):m.start()]
                ato = s[m.end():m.end() + 2]
                if mae in ("〜", "～", "-", "–"):
                    continue
                if ato[:2] in ("以上", "以下", "未満") or ato[:1] == "超":
                    continue
                warui.append(m.group(0).strip())
            if warui:
                raise AssertionError(
                    f"「{na}」の区間に、件数か割合が手で書かれている： "
                    + " / ".join(warui[:5])
                    + "。**現在値は、数えた段が書く生成物に置く**")

            # ② コードの一覧を写していないか（字下げ＋英小文字の名前）
            utsushi = re.findall(r"^    ([a-z_]{3,})\s{2,}\S", s, re.M)
            if utsushi:
                raise AssertionError(
                    f"「{na}」の区間に、コード側の一覧が写されている： "
                    + " / ".join(utsushi[:5])
                    + "。**写すと片方だけ古くなる。実物のある場所を指す**")

            # ③ 数を消したなら、どこを見ればよいかが書いてあるか
            if not re.search(r"data/ref/[A-Za-z0-9_.-]+|index\.json|KARA_DE_YOI|[a-z_]+\.py", s):
                raise AssertionError(
                    f"「{na}」の区間に、現在値の見に行き先が書かれていない。"
                    "**数字を消したなら、どこを見ればよいかを書く**")

            # ④ 市の名前を書かない（一覧が増えたら古くなる）。
            #    **名前を検査に書かない。**いま一覧を持っている市を
            #    data/ref/towns.json と data/ref/jis-codes.json から引く
            for shi in _ichiran_no_shi():
                if shi and shi in s:
                    raise AssertionError(
                        f"「{na}」の区間に市の名前「{shi}」が書かれている。"
                        "**どの市の一覧を持っているかは data/ref/towns.json が持つ**")


def test_文書が案内する参照先が実在するか():
    """**案内した先が消えても、誰も気づかない**（2026-09-22）。

    文書は「現在値は `data/ref/…` を見る」と書くようになった。
    だがその先が消えても、消えたことを見る検査が無かった
    （`addr-katachi.md` も `town-gap.md` も、隠して走らせたら通った）。

    **参照先が増えても、検査を書き足さなくてよい形**にする。
    文面から拾って、在るかどうかだけ見る。**件数は1つも持たない。**

    まだ作っていないものは、同じ行に `<!-- まだ無い -->` と書く。
    **予定と現在を混ぜない**（6節「「まだ無い」とも書かない」）。
    """
    import glob as _glob
    MICHI = re.compile(r"data/ref/[A-Za-z0-9_.-]+\.(?:md|json)")
    nai = []
    mita = 0
    docs = [os.path.join(HERE, "CLAUDE.md"), os.path.join(HERE, "README.md")]
    docs += sorted(_glob.glob(os.path.join(HERE, "docs", "**", "*.md"), recursive=True))
    for d in docs:
        if not os.path.exists(d):
            continue
        with open(d, encoding="utf-8") as f:
            for i, ln in enumerate(f, 1):
                if "まだ無い" in ln and "<!--" in ln:
                    continue                      # これから作るもの
                for m in MICHI.finditer(ln):
                    mita += 1
                    if not os.path.exists(os.path.join(HERE, m.group(0))):
                        nai.append(f"{os.path.relpath(d, HERE)}:{i} {m.group(0)}")
    if nai:
        raise AssertionError(
            "文書が案内している参照先が無い： " + " / ".join(nai[:5])
            + "。**案内した先が消えたら、案内も直す。"
            "まだ作っていないなら、その行に <!-- まだ無い --> と書く**")
    if mita == 0:
        raise AssertionError(
            "文書から data/ref への案内が1本も拾えなかった。"
            "**拾い方が壊れていると、この検査は黙って通る**")


def test_空でよい欄の理由に件数を書いていないか():
    """**理由は意味を書く場所で、件数を置く場所ではない**（2026-09-22）。

    `KARA_DE_YOI` の `city_code` の理由に「市区町村が決まらない37件」と
    件数が手で書かれていた。**2026-09-19 に書かれてから一度も更新されておらず、
    そのとき実数は 44 になっていた。**

    この数はコードの判定に使われていない（`37` はこの文字列の中にしか無かった）。
    検査も「理由が空でないか」しか見ていないので、**古くなっても誰も鳴らない。**

    数を新しくするのではなく、**ここで件数を持つのをやめた。**
    現在値は `index.json` の `not_counted` が持つ（`build_site.py` が毎回書く）。
    """
    import re as _re
    import build_site as bs

    # **しきい値と実数を分ける。** 最初に書いた見張りは
    # `count` の「1〜2件は伏せる」（3.2 の境目）にも当たった。
    # しきい値は境目として書く（`1〜2件` `3件以下`）、実数はそのまま書く（`37件`）。
    # だから「範囲の一部」と「以上・以下・未満・超が続くもの」は数えない
    warui = []
    for k, riyuu in bs.KARA_DE_YOI.items():
        for m in _re.finditer(r"([0-9][0-9,]*)\s*(件|本|行|枚|欄)", riyuu):
            mae = riyuu[max(0, m.start() - 1):m.start()]
            ato = riyuu[m.end():m.end() + 2]
            if mae in ("〜", "～", "-", "–"):
                continue                       # 範囲の後ろ側（1〜2件）
            if ato[:2] in ("以上", "以下", "未満") or ato[:1] == "超":
                continue                       # 境目（3件以下）
            warui.append(f"{k}: {m.group(0)}")
    if warui:
        raise AssertionError(
            "KARA_DE_YOI の理由に件数が書かれている： " + " / ".join(warui[:5])
            + "。**理由は意味を書く場所。現在件数は index.json の not_counted が持つ**")

    # **見に行き先が書いてあるか。**数を消したなら、どこを見るかは要る
    if "not_counted" not in bs.KARA_DE_YOI.get("city_code", ""):
        raise AssertionError(
            "KARA_DE_YOI の city_code の理由に `not_counted` への案内が無い。"
            "**件数を消したなら、どこを見ればよいかを書く**")


def test_町丁目の一覧が読める形で在るか():
    """西宮市の一覧を入れた日（2026-09-22）に足した。

    **出典を `towns.json` に混ぜない。** 混ぜると、説明の鍵（`_source` など）が
    **市区町村コードとして数えられる。** 姉妹サイトの `town_list.json` は
    `{"_note":…, "towns": {…}}` の形で、これをそのまま置くと
    `load_towns().get(code)` が毎回 `None` になり、**エラーも出さずに②が効かない。**
    ③に落ちるだけなので検査も通ってしまう（2026-09-22 に見つけた形）。
    """
    import json
    import addr
    path = os.path.join(HERE, "data", "ref", "towns.json")
    if not os.path.exists(path):
        return                      # **まだ無い日もある。**無いこと自体は違反ではない
    with open(path, encoding="utf-8") as f:
        ichiran = json.load(f)

    eq(isinstance(ichiran, dict), True, "towns.json は {コード: [町名]} の形")
    for code, machi in ichiran.items():
        if not (code.isdigit() and len(code) == 5):
            raise AssertionError(
                f"towns.json の鍵が市区町村コードでない: {code!r}。"
                "**出典や説明を混ぜない**（data/ref/towns.meta.json に置く）")
        eq(isinstance(machi, list), True, f"{code} の中身は一覧")
        if len(machi) != len(set(machi)):
            raise AssertionError(f"{code} の町名に重複が在る: {len(machi)} → {len(set(machi))}")
        for m in machi:
            if addr._clean(m) != m:
                raise AssertionError(
                    f"{code} の「{m}」が下ごしらえ済みでない。"
                    "**当てる相手と同じ形でないと当たらない**（common/addr.py の _clean）")

    # 出典が別ファイルに在るか。**在るか**だけを見る（中身の正しさは見ていない）
    meta = os.path.join(HERE, "data", "ref", "towns.meta.json")
    if not os.path.exists(meta):
        raise AssertionError("towns.json は在るが towns.meta.json が無い。**出どころが追えない**")
    with open(meta, encoding="utf-8") as f:
        m = json.load(f)
    for k in ("fetched_on", "source", "edition", "cities"):
        if k not in m:
            raise AssertionError(f"towns.meta.json に「{k}」が無い")
    for code in ichiran:
        if code not in m.get("cities", {}):
            raise AssertionError(f"towns.json の {code} が towns.meta.json に無い")

    # **一覧が無い市では、従来どおり空になる。**
    moto = _towns_wo_sashikomu(ichiran)
    try:
        d = addr.normalize("大阪府", "枚方市", "岡東町12-1")
        eq(d["town"], "", "一覧が無い市では、従来どおり空のまま")
    finally:
        _towns_wo_sashikomu(moto)


def test_町丁目の照合が短い町名へ化けない():
    """**②が外れると、別の町丁目になる**（正本4節）。

    2026-09-22、西宮市の105件で測って分かったこと。

      ・「丁目なし・番地あり」の51件は、一覧を**一度も見ていなかった**
      ・②の最長一致には「当たった直後が数字か」の条件が**コードに無かった**
        （西宮市では偶然0件だったが、コードが守ったのではない）

    A〜E をここで見る。**実在の町名を使う。**地番も人も出てこない。
    """
    import addr
    moto = _towns_wo_sashikomu({})
    try:
        # A 数字の手前と町名が丸ごと同じ → ①で決まる
        _towns_wo_sashikomu({"28204": ["甲子園町"]})
        d = addr.normalize("兵庫県", "西宮市", "甲子園町1番2号")
        eq(d["town"], "甲子園町", "A ①：数字の手前と完全一致なら決まる")

        # B 短い町名だけが前方一致 → 決めない
        _towns_wo_sashikomu({"28204": ["甲子園"]})
        d = addr.normalize("兵庫県", "西宮市", "甲子園口北町5番6号")
        eq(d["town"], "", "B ①：短い町名が頭に一致しただけでは決めない")

        # C 1行に町が2つ → ①で誤って決めない
        #   「139番、」の番は後ろが数字でないので印にならず、
        #   数字の手前が「今津曙町139番、今津水波町」になる。丸ごと同じではない
        _towns_wo_sashikomu({"28204": ["今津曙町", "今津水波町"]})
        d = addr.normalize("兵庫県", "西宮市", "今津曙町139番、今津水波町2番3号")
        eq(d["town"], "", "C ①：1行に町が2つあるとき、片方を選ばない")

        # D ②で町名の直後が数字 → 従来どおり決まる
        _towns_wo_sashikomu({"28204": ["甲子園町"]})
        d = addr.normalize("兵庫県", "西宮市", "甲子園町1-2")
        eq(d["town"], "甲子園町", "D ②：直後が数字なら決まる")

        # E ②で町名の直後が漢字 → 決めない
        _towns_wo_sashikomu({"28204": ["甲子園"]})
        d = addr.normalize("兵庫県", "西宮市", "甲子園口北町1-2")
        eq(d["town"], "", "E ②：直後が漢字なら決めない")

        # **より短い候補へ下がらない**ことも見る。
        # 「甲子園口北町」が無く「甲子園口」と「甲子園」が在っても、決めない
        _towns_wo_sashikomu({"28204": ["甲子園", "甲子園口"]})
        d = addr.normalize("兵庫県", "西宮市", "甲子園口北町1-2")
        eq(d["town"], "", "E' ②：境目が合わないとき、短い候補へ下がらない")

        # 末尾で終わる形も採る（数字が1つも無い町名だけの住所）
        _towns_wo_sashikomu({"28204": ["甲子園町"]})
        d = addr.normalize("兵庫県", "西宮市", "甲子園町")
        eq(d["town"], "甲子園町", "②：末尾で終わるときも採る")
    finally:
        _towns_wo_sashikomu(moto)


# ①'（丁目が無く①で決まらない行を、数字の手前の丸ごと一致で決める）で決まる行の数。
# 2026-09-26 に数えた（西宮市だけ。一覧が西宮市ぶんしか無い）。条件を締めても 48 のまま。
# **数えた日に数を直す。理由を見ないまま直さない。** 減ったら、締めた条件で落ちた行を見る
ICHI_DASH_DE_KIMARU = 48


def test_丁目なしの町名は_紛らわしい候補が一覧に在れば決めない():
    """①' の条件（2026-09-26・統括判断。正本4節）。**1つでも欠ければ決めない。**

      ・丁目が無い／①では決まらない
      ・数字の手前が、その市の町名の一覧の1件と丸ごと同じ（前方一致は使わない）
      ・**その町名で始まる別の町名が、一覧に無い**

      F 「X」と「X N丁目」が在る → X＋数字は決めない（3 が丁目の略記か地番か分からない）
      G 「X」と「X南町」「X町」が在る → X＋番地は決めない（実在の組）
      H 前方一致だけ → 決めない
      I 紛らわしい候補が無い → これまでどおり決まる
      J 実データ：①' で決まる行の数が ICHI_DASH_DE_KIMARU のまま

    **紛らわしさの確認を外すと、F と G が鳴る。**
    """
    import addr
    moto = _towns_wo_sashikomu({})
    try:
        _towns_wo_sashikomu({"28204": ["山口町下山口", "山口町下山口1丁目", "山口町下山口2丁目"]})
        d = addr.normalize("兵庫県", "西宮市", "山口町下山口3番5号")
        eq(d["town"], "", "F ①'：「X」と「X N丁目」が在るとき、X＋数字は決めない")

        _towns_wo_sashikomu({"28204": ["鷲林寺", "鷲林寺南町", "鷲林寺町"]})
        d = addr.normalize("兵庫県", "西宮市", "鷲林寺123番地")
        eq(d["town"], "", "G ①'：X で始まる別の町が在るとき、X＋番地は決めない")

        _towns_wo_sashikomu({"28204": ["今津"]})
        d = addr.normalize("兵庫県", "西宮市", "今津曙町139番地")
        eq(d["town"], "", "H ①'：前方一致だけでは決めない")

        _towns_wo_sashikomu({"28204": ["甲子園町", "上ケ原二番町"]})
        d = addr.normalize("兵庫県", "西宮市", "甲子園町847番地の1")
        eq(d["town"], "甲子園町", "I ①'：紛らわしい候補が無ければ、これまでどおり決まる")

        # J 実データ。①' を外したときとの差が、①' で決まった行
        _towns_wo_sashikomu(None)
        with open(os.path.join(HERE, "data", "all.json"), encoding="utf-8") as f:
            recs = [r for r in json.load(f) if r.get("address")]
        ari = [addr.normalize(r.get("pref") or "", r.get("city") or "", r["address"])["town"] for r in recs]
        hontai = addr.machi_maru_goto
        addr.machi_maru_goto = lambda mae, towns: ""
        try:
            nashi = [addr.normalize(r.get("pref") or "", r.get("city") or "", r["address"])["town"] for r in recs]
        finally:
            addr.machi_maru_goto = hontai
        kimatta = sum(1 for a, b in zip(ari, nashi) if a and not b)
        eq(kimatta, ICHI_DASH_DE_KIMARU, "J ①'：実データで ①' で決まる行の数（数えた日に直す。理由を見てから）")
    finally:
        _towns_wo_sashikomu(moto)


def test_町丁目が決まっている行を一覧が書き換えない():
    """F **いま決まっているものを、あとから来た一覧が動かさない。**

    9節「繋がらなかったことは残るが、まとまってしまったことは残らない」。
    決まっていた町丁目が別の値に変わるのは、いちばん気づけない壊れ方。
    """
    import json
    import addr
    path = os.path.join(HERE, "data", "all.json")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        recs = json.load(f)

    def hakaru():
        out = {}
        for i, r in enumerate(recs):
            if not (r.get("address") or "").strip():
                continue
            try:
                d = addr.normalize(r.get("pref", ""), r.get("city", ""), r.get("address", ""))
            except ValueError:
                raise
            except Exception:
                continue
            if d.get("addr_key_town"):
                out[i] = d["addr_key_town"]
        return out

    moto = _towns_wo_sashikomu({})
    try:
        mae = hakaru()
        if len(mae) != TOWN_KIMATTA_NASHI:
            raise AssertionError(
                f"一覧を外したときに決まる行が動いた： {TOWN_KIMATTA_NASHI} → {len(mae)}。"
                "**ここは一覧と関係なく、丁目から決まる行。減ったら読み方が壊れた**")

        # いまの towns.json を当てたときの数。**増える方向にしか動かないはず**
        honban = os.path.join(HERE, "data", "ref", "towns.json")
        if os.path.exists(honban):
            with open(honban, encoding="utf-8") as f:
                _towns_wo_sashikomu(json.load(f))
            ima = hakaru()
            if len(ima) != TOWN_KIMATTA_ARI:
                raise AssertionError(
                    f"いまの一覧で決まる行が動いた： {TOWN_KIMATTA_ARI} → {len(ima)}。"
                    "**増えたなら一覧が増えた（この数を直す）。減ったなら先に理由を見る**")
            kawatta_honban = [i for i, v in mae.items() if ima.get(i) != v]
            if kawatta_honban:
                raise AssertionError(
                    f"いまの一覧で、決まっていた町丁目が {len(kawatta_honban)}件 変わった。"
                    "**一覧は、決まっていないものだけを決める**")
        # 一覧を差し込む。**いま決まっている行の値が1つでも変わったら鳴る**
        _towns_wo_sashikomu({"28204": ["甲子園町", "今津曙町", "浜町", "本町", "甲子園"]})
        ato = hakaru()
        kawatta = [i for i, v in mae.items() if ato.get(i) != v]
        if kawatta:
            raise AssertionError(
                f"一覧を入れたら、決まっていた町丁目が {len(kawatta)}件 変わった。"
                "**一覧は、決まっていないものだけを決める**")
    finally:
        _towns_wo_sashikomu(moto)


def test_町丁目までつながらない数が動いたら気づく():
    """4節③「空にして**記録する**」の、記録のほう。

    1,764件が空だった（2026-09-21 に数え直した。
    それまでは原典に住所が無い 464件を混ぜて 2,228件と書いていた）。**空にするのは正しいが、
    空になったことをどこにも書いていなかった**（2026-09-19）。
    一覧が入れば減る。様式が変われば増える。どちらも気づけるようにする。
    """
    import json
    import town_gap
    path = os.path.join(HERE, "data", "all.json")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        recs = json.load(f)
    total, empty, _by_city, _unread, nashi = town_gap.measure(recs)
    # **原典が書かなかった行を、読めた行に混ぜない**（2026-09-21 に混ざっていた）
    if nashi != TOWN_NASHI:
        raise AssertionError(
            f"原典に住所が無い行が動いた： {TOWN_NASHI} → {nashi}。"
            "**こちらでは減らせない行なので、読めた行に混ぜない**")
    if (total, empty) != (TOWN_TOTAL, TOWN_GAP):
        raise AssertionError(
            f"町丁目までつながらない数が動いた： {TOWN_TOTAL}件中{TOWN_GAP}件 → "
            f"{total}件中{empty}件。減ったなら towns.json が効いた（この数を直す）。"
            "増えたなら様式が変わったか、住所の読み方が壊れた（先に理由を見る）")

    # 記録のファイルが、いまの数と食い違っていないか。
    # **作った一覧を巡回に入れないと、古いまま検査を通る**（9節）
    rep = os.path.join(HERE, "data", "ref", "town-gap.md")
    if os.path.exists(rep):
        with open(rep, encoding="utf-8") as f:
            text = f.read()
        if f"{empty:,}" not in text:
            raise AssertionError(
                f"data/ref/town-gap.md が古い（いまは {empty:,} 件）。"
                "town_gap.py を走らせ直すこと")


def test_正本に同じ行が2度続いていないか():
    """直すときに1行を複製して、片方だけ直す形。

    2026-09-19 に2か所あった（404 の URL の話と、コードブロックの話）。
    どちらも「その行を強調しようとして貼り直した」あと。
    見た目では気づけないので、機械で見る。
    """
    path = os.path.join(HERE, "docs", "kyotsu-shiyo.md")
    lines = open(path, encoding="utf-8").read().splitlines()
    dups = []
    for i in range(1, len(lines)):
        t = lines[i].strip()
        # 表の行・箇条書き・コードブロックの中は、同じ行が並んでよい
        if t and lines[i] == lines[i - 1] and t[0] not in "|-" and not t.startswith("```"):
            dups.append(f"{i + 1}行目: {t[:60]}")
    if dups:
        raise AssertionError("正本に同じ行が2度続いている：\n  " + "\n  ".join(dups))


def test_文字コードは例外の有無で選ばない():
    """cp932 はほとんどのバイト列を受け取るので、EUC-JP がそこで「成功」する。

        "大阪府".encode("euc-jp").decode("cp932")  →  "ﾂ郤衙ﾜ"   例外は出ない

    2026-09-19、開発系が自分の to_text() で見つけ、こちらの decode_html にも
    同じ穴があった（総当たりの順で cp932 が euc-jp より先だった）。
    **例外の有無ではなく、中身の見た目で選ぶ。**

    これが実害になっていた実物が `ref_jis.py`。総務省のページを utf-8 で
    決め打ちして読み、meta の label が化け、**その化けた文字列に
    「政令」「廃置」「変更」で点を付けていた。**
    """
    from common.fetch import decode_html, ja_score

    # ① 宣言が無く、cp932 でも「読めてしまう」EUC-JP
    for word in ("大阪府の市区町村コード一覧", "兵庫県神戸市の統計"):
        got, enc = decode_html(word.encode("euc-jp"), "text/html")
        eq(got, word, f"宣言の無い EUC-JP を読む（{word[:4]}…）")
        eq(enc, "euc-jp", "どれで読んだかを返す")

    # ② 宣言があれば信じる
    eq(decode_html("Excelファイル".encode("cp932"),
                   "text/html; charset=Shift_JIS")[0], "Excelファイル",
       "宣言された Shift_JIS")

    # ③ 点そのもの。化けたほうが必ず低い
    if not ja_score("大阪府の市区町村コード") > ja_score("ﾂ郤衙ﾜﾃﾓﾅﾄｻﾔﾈｪ"):
        raise AssertionError("化けた文字列のほうが日本語らしいと判定された")

    # ③-2 2つの点は**測っているものが違う**。取り違えると、英数字だけの
    #     ページを「化けている」と判定して落とす（開発系の指摘・2026-09-19）
    from common.fetch import bakete_inai
    eisuu = "GET /index.html HTTP/1.1 200 OK"
    if ja_score(eisuu) > 0:
        raise AssertionError("ja_score は日本語の字を数えるので、英数字だけなら 0 以下")
    if bakete_inai(eisuu) < 0.99:
        raise AssertionError("bakete_inai は化けを数えるので、英数字だけでも 1.0 に近い")
    if bakete_inai("ﾂ郤衙ﾜﾃﾓﾅﾄｻﾔﾈｪ") >= bakete_inai(eisuu):
        raise AssertionError("化けた文字列のほうが化けていないと判定された")

    # ④ 決め打ちが戻っていないか。**取りに行くもの全部**を文字として見る。
    #    ref_*.py だけ見ていたので、robots.txt と月ページを見落としていた
    #    （2026-09-19、4サイトのうち3つが同じ場所で同じものを見つけた）。
    #    ただし**正しいものを壊れていると言わない。** 外から来た文字列でない
    #    ものは決め打ちでよいので、理由つきの許可リストで外す
    import glob
    ok_riyuu = (
        ("r.stdout", "外部コマンドの出力。utf-8 と決まっている"),
        ("json.loads", "JSON の API。utf-8 と決まっている"),
        ("化けたまま", "decode_html 自身の最後の逃げ道。もう手が無い"),
        ("LookupError", "宣言された名前が引けなかったときの逃げ道"),
        # common/kado.py の robots.txt 読み。RFC 9309 で robots.txt は
        # UTF-8（ASCII 互換）と決まっている。**読めなければ推測せず、
        # 「確かめられなかった」で fail-closed に倒す**（決め打ちではない）
        ("UnicodeDecodeError", "robots.txt は規格で UTF-8。読めなければ確かめられなかったに倒す"),
    )
    # **名前で並べない**（2026-09-19）。外に出るものを実物から拾う
    targets = soto_ni_deru()
    bad = []
    for path in targets:
        if not os.path.exists(path):
            continue
        text = open(path, encoding="utf-8").read()
        for m in re.finditer(r'\.decode\(\s*["\']utf-8["\']', text):
            near = text[max(0, m.start() - 160):m.start() + 160]
            if any(w in near for w, _ in ok_riyuu):
                continue
            line = text[:m.start()].count("\n") + 1
            bad.append(f"{os.path.basename(path)}:{line}")
    if bad:
        raise AssertionError(
            "取りに行くところで文字コードを決め打ちしている（decode_html を使う）："
            + " / ".join(bad))


def test_取ってきた生データを文字にしてから保存していないか():
    """`data/raw/` に置換文字だらけのファイルが無いか。

    2026-09-19、`data/raw/hyogo-pref-juran/` に5枚あった。
    相手が gzip で返した回に、`wayback.py` が**文字にしてから保存**していた。
    先頭が `1f 8b 08`（gzip）ではなく `1f ef bf bd` になっていて、
    `0x8b` が U+FFFD に潰れている。**元のバイトはもう戻らない。**

    `recon.py` は最初から `"wb"` でバイトのまま書いていた
    （「生のまま残す。これがアーカイブの最初の1枚になる」）。
    **同じ判断が2か所にあって、片方だけ正しかった。**
    """
    import glob
    root = os.path.join(HERE, "data", "raw")
    if not os.path.isdir(root):
        return
    bad = []
    for fp in sorted(glob.glob(os.path.join(root, "**", "*.html"), recursive=True)):
        raw = open(fp, "rb").read()
        n = raw.count(b"\xef\xbf\xbd")
        if raw and n * 40 > len(raw):          # 40バイトに1個より多い
            bad.append(f"{os.path.relpath(fp, HERE)}（置換文字 {n} 個 / {len(raw)} バイト）")
        # **バイトのまま保存するようにしたら、こちらは置換文字が出なくなる。**
        # **守りを直すと、その守りを見ていた検査の効き目も変わる**（2026-09-19）
    if bad:
        raise AssertionError(
            "生データが文字にしてから保存されている（バイトのまま書くこと）：\n  "
            + "\n  ".join(bad[:5])
            + (f"\n  ほか {len(bad) - 5} 件" if len(bad) > 5 else ""))


def test_生データの名前が中身と合っているか():
    """拡張子と中身の先頭が合っているか。

    2026-09-19、`data/raw/tokyo-ref/` に `%PDF` で始まる `.html` が **40枚**あった。
    バイトは無事なので壊れてはいない。**名前が嘘をついている**だけ。
    だが `*.html` を読む側は、黙って読み違える
    （9節「名前が変わったことと、中身が変わったことは違う」）。

    **捕まえないもの**：中身が正しいか。HTML と名乗る HTML が
    壊れていないかは、ここでは見ていない。
    """
    import glob
    import recon
    root = os.path.join(HERE, "data", "raw")
    if not os.path.isdir(root):
        return
    bad = []
    for fp in sorted(glob.glob(os.path.join(root, "**", "*.*"), recursive=True)):
        if os.path.isdir(fp):
            continue
        raw = open(fp, "rb").read(8)
        want = recon.ext_of(raw)
        have = os.path.splitext(fp)[1].lower()
        # .html は「それ以外」の受け皿なので、中身が判る形のときだけ責める
        if want != ".html" and have != want:
            bad.append(f"{os.path.relpath(fp, HERE)} は {want} の中身")
    if bad:
        raise AssertionError(
            "名前と中身が合っていない：\n  " + "\n  ".join(bad[:5])
            + (f"\n  ほか {len(bad) - 5} 件" if len(bad) > 5 else ""))


def test_住まいの語は語の切れ目まで見る():
    """文字列を含むかだけで見ると、**逆のものを拾う。**

    2026-09-19、足したその日に実データで2件誤って拾った。
    どちらも別の語の一部だった。
    """
    from common.privacy import residential_reason as rr

    # 実データにあった誤検知（どちらも住まいではない）
    eq(rr("（仮称）三井アウトレットパークマリンピア神戸建替計画"), "",
       "「神戸建替」の『戸建』を拾わない")
    eq(rr("ライフコーポレーション"), "",
       "「コーポレーション」の『コーポ』を拾わない（むしろ法人の語）")
    eq(rr("長屋町1-2-3 倉庫"), "", "「長屋町」は地名")

    # 本物は拾う（実データにあったもの）
    for text in ("緑地東グランドマンション（阪急オアシス服部緑地店）",
                 "浪速住宅ビル", "ハンリョウ八尾ハイツ",
                 "ＡＳＴＭ芦屋浜高層住宅プロジェクト商業施設",
                 "一戸建て 木造"):
        if rr(text) != "居住用途の建物":
            raise AssertionError(f"住まいの語を拾えていない：{text!r} → {rr(text)!r}")


def test_既定値で黙って埋めていないか():
    """注記はそう書いてあるのに、コードは既定値で動きつづける形。

    競売統計が自分の `site.py` で見つけた（2026-09-19）——
    「名前の正は site.json の1か所だけ」と注記にあるのに、
    **欄を抜いても既定値から補って通った。** `bot_name` は
    **相手のサーバーに届く名乗りそのもの**で、欄が消えても動くので誰も気づかない。

    こちらを洗ったら3つ出た。

      出典の名前とURL  控えが無いと「兵庫県公報 検索用目録」で埋めて**公開していた**
      freq            知らない綴りを、いちばん頻繁な側（毎日）に倒していた
      last_saved      `.html` だけ見ていた。PDF の日は「持っていない」になる

    **捕まえないもの**：安全な既定値かどうか。
    `kinds.get("operator", "individual")` のように**きつい側**に倒すものは正しい。
    """
    import glob
    import re as _re
    # 相手のサーバーに出る回数と、画面に出る出典。**この2つは既定値で決めない**
    import recon
    src = {"id": "ためし", "freq": "weekly"}          # 表に無い綴り
    try:
        recon.FREQ_DAYS[src["freq"]]
    except KeyError:
        pass
    else:
        raise AssertionError("ためしの綴りが表にある。別の綴りで当て直すこと")
    # 知らない freq で止まるか（止まらないと毎日取りに行く）
    ok = False
    try:
        if src["freq"] not in recon.FREQ_DAYS:
            ok = True
    except Exception:
        pass
    if not ok:
        raise AssertionError("知らない freq を見分けられていない")

    # 保存した日を、拡張子で絞っていないか
    srcfile = open(os.path.join(HERE, "recon.py"), encoding="utf-8").read()
    body = srcfile[srcfile.index("def last_saved"):]
    body = body[:body.index("\ndef ")]
    if '????-??-??.html' in body:
        raise AssertionError(
            "last_saved が .html だけ見ている。"
            "名前は中身から決めるので、PDF の日を見落として毎日取りに行く")


def test_探される語が_description_に入っているか():
    """役所の語だけで書くと人に見つからない。**だが言い換えて主張にしない。**

    2026-09-19、Search Console の実測。検索されているのは
    「◯◯ 開店」「◯◯ 閉店」で、**「新設」「廃止」では1件も当たっていない。**

        箕面 コストコ ／ 出屋敷 コスモス ／ エバーグリーン 狭山 閉店
        イズミヤ西神戸 閉店 ／ カナエ今川店 開店

    **それでも「◯月◯日に開店予定」とは書かない。** 2つ外れる。

    ① 届出が出しているのは「大規模小売店舗として新設する日」であって、
       開店日ではない。**新設してから開ける日は別に決まる**
       （2026-09-19、[運営者]の指摘。僕が一度「に開店予定」と書き、
       その日のうちに直した。「事実の主張は外れる」と正本に書いた当日）。

    ② **「予定」そのものが外れる。** 4,809件を数えたら、届出日より前の日が
       入っていた：変更1,760・承継143・廃止94・新設2・中規模2、**計2,001件。**
       過ぎた日を「予定日」と呼んでいた。

    だから書くのは「**届出に書かれた新設日は**◯月◯日」。主語が届出なので
    外れようがない。探される語は「（開店日とは別に決まります）」の側に入れる。
    ページには「開店」「閉店」が入り、しかも外れない。

    この検査は3つを見張る。
    ① 探される語が添え字に入っていること
    ② **呼び名に「予定」「開店」「閉店」が入っていないこと**（表を直接見る）
    ③ **「に開店予定」が戻ってきていないこと**（説明の # 行は数えない）

    **捕まえないもの**：実際に検索順位が上がるか。それは後日 Search Console で見る。
    """
    import importlib
    bs = importlib.import_module("build_site")
    hyo = bs.KIND_HIZUKE

    # ① 探される語は添え字の側に入れる。
    # **表に無い種類は、ここでは KeyError にしない。** 表の取りこぼしは
    # test_日付の呼び名が種類を取りこぼしていないか が実データ付きで鳴らす。
    # ここで落ちると、あちらの良い言い分けが読まれないまま終わる
    for kind, kotoba in (("新設", "開店"), ("廃止", "閉店")):
        if kotoba not in hyo.get(kind, ("", ""))[1]:
            raise AssertionError(
                f"{kind} の添え字に「{kotoba}」が入っていない。"
                "役所の語だけでは、人が探している語に当たらない")

    # ② **呼び名のほうには入れない。** 呼び名は届出が呼んでいる名前だけ
    for kind, (yobina, soeru) in hyo.items():
        for warui in ("予定", "開店", "閉店"):
            if warui in yobina:
                raise AssertionError(
                    f"{kind} の呼び名「{yobina}」に「{warui}」が入っている。"
                    "呼び名は届出が呼んでいる名前だけにする。"
                    "「予定」は2,001件で外れ、「開店」は届出が言っていない")
        # 添え字で「別に決まります」と断らずに開店・閉店を書くのも主張になる
        if ("開店" in soeru or "閉店" in soeru) and "別に決まります" not in soeru:
            raise AssertionError(
                f"{kind} の添え字「{soeru}」が、開店・閉店を断らずに書いている")

    # **変更・承継に開店・閉店を付けない。** その日は開店日でも閉店日でもない
    for kind in ("変更", "承継", "中規模"):
        if hyo.get(kind, ("", ""))[1]:
            raise AssertionError(
                f"{kind} に添え字「{hyo[kind][1]}」が付いている。"
                "その日は開店日でも閉店日でもない")

    # ③ **言い換えて主張にしない。**
    #
    # ここは一度、見張り方を間違えた（2026-09-19）。ソースの字面で
    # 「に開店予定」を禁じたら、**「『◯月◯日に開店予定』とは書きません」と
    # 説明しているページ自身が鳴った。**
    # 正本9節の「見張りが探す言葉は、文中に出てこない目印にする」の裏返しで、
    # **禁じたい言葉そのものは、説明にも出てくる。**
    #
    # なので見るのは2つに分けた。
    #   ・出来上がった個票（s/*.html）——読む人に届くのはここだけ
    #   ・ソースでは、**日付を差し込んでいる行だけ**（f-string の { がある行）
    src = open(os.path.join(HERE, "build_site.py"), encoding="utf-8").read()
    for warui in ("に開店予定", "に閉店予定"):
        i = src.find(warui)
        while i >= 0:
            atama = src.rfind("\n", 0, i) + 1
            gyou = src[atama:src.find("\n", i)]
            if not gyou.lstrip().startswith("#") and "{" in gyou:
                raise AssertionError(
                    f"{src[:i].count(chr(10)) + 1}行目が、日付を差し込みながら"
                    f"「{warui}」と書いている。届出が出しているのは「新設する日」で、"
                    "開店日は別に決まる。事実の主張になる")
            i = src.find(warui, i + 1)

    # **出来上がった個票を読む。** 読む人に届くのはここだけ
    import glob
    for michi in glob.glob(os.path.join(HERE, "s", "*.html")):
        with open(michi, encoding="utf-8") as f:
            h = f.read(3000)
        for warui in ("に開店予定", "に閉店予定"):
            if warui in h:
                raise AssertionError(
                    f"{os.path.basename(michi)} に「{warui}」と出ている。"
                    "届出が言っていない")


def test_新設と開店の違いを説明する1枚があるか():
    """**役所の語では見つからない。だが言い換えて主張にしない。** その代わりの1枚。

    2026-09-19、[運営者]の案——

    > 新設と廃止で閉店と開店とは異なります。の記載で１位目指せないかにゃ？

    「◯◯ 開店」で1位は取れない（町の情報サイトもニュースも書く）。
    だが「**新設 開店 違い**」なら取れる。**役所が自分で2つの欄を
    分けて持っている**ことを、数えて示せるのはこちらだけだから。

    この検査が見張るのは3つ。
    ① 1枚が在ること
    ② **新設・廃止からだけつなぐこと。** 変更・承継の日は開店日ではないので、
       つなぐと「関係がある」と言ったことになる
    ③ **文章に数を書き写していないこと。** ページの合計が、いま data から
       数え直した値と合うこと

    **捕まえないもの**：実際に1位になるか。それは後日 Search Console で見る。
    """
    import glob, json
    michi = os.path.join(HERE, "shinsetsu-to-kaiten.html")
    if not os.path.exists(michi):
        return   # まだ組み立てていない
    honbun = open(michi, encoding="utf-8").read()

    # ② つなぐのは新設・廃止だけ
    tsunagu, tsunaganai = set(), set()
    for f in glob.glob(os.path.join(HERE, "s", "*.html")):
        with open(f, encoding="utf-8") as fh:
            h = fh.read(3000)
        m = re.search(r"の(新設|廃止|変更|承継|中規模|意見・勧告)届出", h)
        if not m:
            continue
        (tsunagu if "shinsetsu-to-kaiten" in h else tsunaganai).add(m.group(1))
    yokei = tsunagu - {"新設", "廃止"}
    if yokei:
        raise AssertionError(
            f"{sorted(yokei)} からも説明の1枚につないでいる。"
            "その日は開店日でも閉店日でもないので、つなぐと関係があると言ったことになる")
    for kind in ("新設", "廃止"):
        if kind in tsunaganai and kind not in tsunagu:
            raise AssertionError(f"{kind} の個票が説明の1枚につながっていない")

    # ③ **数を書き写していない。** いま数え直した値と合うか
    zairyo = os.path.join(HERE, "data", "all.json")
    if not os.path.exists(zairyo):
        return
    recs = json.load(open(zairyo, encoding="utf-8"))
    kazoeta = sum(1 for r in recs
                  if r.get("kind") == "新設" and r.get("planned_on") and r.get("opened_on")
                  and r["opened_on"] >= r["notified_on"])
    if kazoeta and f"<b>{kazoeta:,}</b>" not in honbun and f"<b>{kazoeta}</b>" not in honbun:
        raise AssertionError(
            f"ページの合計が、いま数え直した {kazoeta} 件と合わない。"
            "文章に数を書き写していないか")


def test_住所の書かれ方は細かいほうから見るか():
    """**ゆるい印を先に見ると、細かい印が全部そこに落ちる。**

    `…番…号`（住居表示）は `…番` も満たす。`…番` を先に見ると、
    住居表示 843件がまるごと「…番 まで」に入って、**消える。**
    合計は変わらないので、**合計の検査では捕まらない**（正本9節）。

    2026-09-19。地図に点を置けるかを数えるために書いた
    `addr_katachi.py` の、順番そのものを留める。

    **捕まえないもの**：印があれば本当に座標が当たるか。
    それは実際に引き当ててから測る。
    """
    import importlib
    ak = importlib.import_module("addr_katachi")

    # **見本は実物から取る**（data/all.json の実際の書かれ方から。作文しない）
    for text, machigai in (
            ("中央区森ノ宮中央2丁目1番70号", "住居表示（…番…号）"),
            ("西区鳳東町七丁733番地", "地番（…番地…）"),
            ("岸和田市土生町二丁目32番39", "…番 まで"),
            ("門真市江端町", "町名まで"),
            # **印が1つも無くても、町名より下に数字があることがある。**
            # 開発系が近畿財務局の売却結果で見つけた（2026-09-19）。
            # 向こうで199件中145件（72.9%）、こちらで1,406件中975件（69.3%）。
            # **2サイトが独立に同じ割合を出した**ので、印を1つ足した
            ("北区長曽根町3456－7 ほか", "略記（印が無いが数字はある）"),
            # **括弧の中と「外◯筆」は場所の細かさではない。**
            # 開発系が「食い違うとしたらここ」と教えてくれた形。
            # 向こうの199件では1件も違わなかったが、**こちらでは5件出た**
            ("川西市火打一丁目（中央北地区特定土地区画整理事業6街区20―3画地ほか）", "町名まで"),
            ("美方郡香美町香住区山手外1筆", "町名まで"),
            ("南区晴美台4丁 1-2の一部", "略記（印が無いが数字はある）"),
            # **丁目の数字は町名の一部。** 落としてから数字を探す
            ("豊中市庄内西町5丁目", "町名まで"),
            ("", "住所が空"),
    ):
        deta = ak.katachi(text)
        if deta != machigai:
            raise AssertionError(
                f"「{text}」を {deta} と読んだ。{machigai} のはず。"
                "細かい印から先に見ているか")

    # **数えた合計が、元の件数と合うか。** 取りこぼしは合計では見えないが、
    # 増えたり減ったりは見える
    recs = [{"address": a} for a in
            ("A1番1号", "B1番地", "C1番", "D町", "", None)]
    zentai, _ = ak.measure(recs)
    if sum(zentai.values()) != len(recs):
        raise AssertionError(f"数えた合計 {sum(zentai.values())} が {len(recs)} と合わない")


def test_not_counted_が4つとも出ているか():
    """升に入らなかった行を、黙って落とさない（6節）。

    2026-09-19、競売統計の blessing から4サイトに広げた。
    **そのとき、うちだけ `not_counted` を1つも出していないことに気づいた。**

    しかも落としてすらいなかった。`city_code` が空のまま升ができていて、
    **`city_code: ""` の升が16枚、公開されていた**（中身は「兵庫県」。
    県が市区町村を書かずに公表した分）。横断ハブは `city_code` で引くので、
    **空の鍵に全部まとまるか、黙って落ちる。**

    見張るのは3つ。
    ① `not_counted` が在って、**4つとも在る**こと（欠けているキーは0ではない）
    ② **`city_code` が空の升が1枚も無い**こと
    ③ `unresolved` が、いま records から数え直した値と合うこと

    **捕まえないもの**：升の合計と足して合うか。**升の数は伏せてある**ので
    出来上がりからは足せない（3.2）。足し算は build_site の中で見ていて、
    合わなければ ValueError で止まる。
    """
    import json
    michi = os.path.join(HERE, "index.json")
    if not os.path.exists(michi):
        return
    with open(michi, encoding="utf-8") as f:
        d = json.load(f)

    # ① 4つとも在る
    nc = d.get("not_counted")
    if nc is None:
        raise AssertionError(
            "index.json に not_counted が無い。升に入らなかった行を黙って落としている")
    for key in ("unresolved", "unobserved", "undecided", "gone"):
        if key not in nc:
            raise AssertionError(
                f"not_counted に {key} が無い。**欠けているキーは0ではない。**"
                "横断で読む側は「0」と「このサイトは数えていない」を見分けられない")

    # ② city_code が空の升を作らない
    kara = [m for m in d["counts_by_city"] if not m.get("city_code")]
    if kara:
        raise AssertionError(
            f"city_code が空の升が {len(kara)}枚ある（例 {kara[0].get('city')}）。"
            "横断ハブは city_code で引く。空の鍵にまとまるか、黙って落ちる")

    # ③ いま数え直した値と合う
    kazoeta = sum(1 for r in d["records"] if not r.get("city_code"))
    if nc["unresolved"] != kazoeta:
        raise AssertionError(
            f"not_counted.unresolved が {nc['unresolved']} だが、"
            f"いま数えたら {kazoeta} 件。数え方が合っていない")


def test_外に出るものが知らない引数で止まるか():
    """**打ち間違いが、本番の収集になってはいけない。**

    2026-09-19、開発系の事故報告——

    > `python3 recon.py --help` と打ちました。**`--help` は受け取らないので、
    > そのまま毎日の収集が走り出しました。**

    `sys.argv[1]` をそのまま対象の名前にする書き方だと、知らない語が
    「当たらない名前」になり、当たらなければ全部走る形なら**全部走る。**

    9節の「既定値は倒す向きが問題」。そこで出るのは役所への接続なので、
    **既定は止まる側**に倒す。

    **名前の一覧では探さない**（9節）。`common.fetch` を使っているか
    `urlopen` を呼んでいるかで、外に出るものを構造で拾う。
    そのうえで**実際に走らせて**、知らない引数で終了コードが0にならないことを見る。

    **捕まえないもの**：受け取る引数を正しく処理するか。ここが見るのは
    「知らない引数で外に出ないこと」だけ。
    """
    import subprocess
    warui, mita = [], 0
    # **拾い方は subete_no_py に1本化した**（2026-09-20 の監査）。
    # ここで見るのは、そのうち**自分で走れるもの**だけ
    for michi in soto_ni_deru():
        na = os.path.relpath(michi, HERE)
        if "__main__" not in open(michi, encoding="utf-8").read():
            continue
        mita += 1
        r = subprocess.run(
            ["python3", na, "--zzz-shiranai-hikisu"],
            cwd=HERE, capture_output=True, text=True, timeout=60)
        if r.returncode == 0:
            warui.append(f"{na}（終了コード0。**そのまま走った**）")
    if mita == 0:
        raise AssertionError(
            "外に出るスクリプトが1つも見つからない。拾い方が壊れている")
    if warui:
        raise AssertionError(
            "知らない引数を渡しても止まらないものがある：\n  " + "\n  ".join(warui)
            + "\n  打ち間違いが本番の収集になる（common/hikisu.py を通すこと）")


def test_目録の問い合わせと件数の読み():
    """**「返ってきた」は「見つかった」ではない。**

    2026-09-19、1回目の実行。3件とも `200` で返り、記録はこう書いた。

        | 目録が返ってきた | 3 |

    **中身は空だった。** 3件とも**きっちり 210 バイト**＝0件。
    問い合わせに都道府県を入れていたのが原因（目録のデータセット名は
    「大阪市都島区（大阪法務局）登記所備付地図データ」で、都道府県は入っていない）。

    見張るのは2つ。
    ① 都道府県だけを落とすこと。**市区町村の名前は削らない**
    ② **0 と「読めなかった」を混ぜないこと**
       0 は向こうが「無い」と言った。None はこちらが読めなかった（6節）

    **捕まえないもの**：その語で本当に当たるか。それは走らせて数える。
    """
    import importlib
    cr = importlib.import_module("chizu_recon")

    # ① **見本は実物から取る**（index.json に実際に入っている市区町村名）
    for moto, hoshii in (
            ("大阪府大阪市都島区", "大阪市都島区"),
            ("兵庫県姫路市", "姫路市"),
            ("大阪府南河内郡美原町", "南河内郡美原町"),
            ("兵庫県丹波篠山市", "丹波篠山市"),
    ):
        deta = cr.shichoson(moto)
        if deta != hoshii:
            raise AssertionError(f"「{moto}」→「{deta}」。「{hoshii}」のはず")

    # **落として空になるなら、落とさない。** 空の語で問い合わせない
    if cr.shichoson("兵庫県") != "兵庫県":
        raise AssertionError("都道府県だけの名前を空にしている。空の語で目録を引くことになる")

    # 問い合わせの語に都道府県が残っていないか
    url = cr.ask("大阪府大阪市都島区")
    import urllib.parse
    q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["q"][0]
    if "大阪府" in q:
        raise AssertionError(f"問い合わせに都道府県が残っている：{q}")

    # ② 0 と「読めなかった」を混ぜない
    if cr.mitsukatta(b'{"result":{"count":0}}') != 0:
        raise AssertionError("0件を0として読めていない")
    if cr.mitsukatta(b'{"result":{"count":2}}') != 2:
        raise AssertionError("件数を読めていない")
    if cr.mitsukatta(b'zzz not json') is not None:
        raise AssertionError(
            "読めなかったものを None にしていない。"
            "0（向こうが無いと言った）と混ざる")


def test_空でよい欄には理由があるか():
    """**空でよい欄には理由を書く。理由が書けないなら、それは穴**（競売統計）。

    2026-09-19。競売統計が「向きが逆だと捕まらない」をそのまま実行した——
    **出す欄を1つずつ空にして走らせた。** 向こうは3つ黙った。

    **こちらで同じことをしたら、25欄のうち17欄が黙った。**

        上     site / site_name / generated_at
        升     city / kind / period / count
        個票   title / date / pref / city / addr / addr_key / …

    `city_code` を見る検査は在った。だが**「ある値が入っているか」しか見ていない。**
    「**空のものが出ていないか**」は誰も見ていなかった。**同じ欄に向いていて、向きが逆。**

    この検査は `build_site.KARA_DE_YOI` を読む。**そこに理由が書いてある欄だけが
    空になってよい。** 書いていない欄が空なら鳴る。
    欄を足した日に「空でよいか」を決めさせる形（「見ないものを並べる」と同じ向き）。

    **捕まえないもの**：値が正しいか。ここが見るのは「空でないか」だけ。
    """
    import importlib
    import json
    michi = os.path.join(HERE, "index.json")
    if not os.path.exists(michi):
        return
    bs = importlib.import_module("build_site")
    yoi = bs.KARA_DE_YOI
    with open(michi, encoding="utf-8") as f:
        d = json.load(f)

    def kara(v):
        return v in (None, "", [], {})

    warui = []
    for k, v in d.items():
        if k in ("records", "counts_by_city"):
            continue
        if kara(v) and k not in yoi:
            warui.append(f"上の {k}")
    for nm, rows in (("升", d["counts_by_city"]), ("個票", d["records"])):
        if not rows:
            continue
        for k in rows[0]:
            n = sum(1 for r in rows if kara(r.get(k)))
            if n and k not in yoi:
                warui.append(f"{nm}の {k}（{n:,}行が空）")
    if warui:
        raise AssertionError(
            "空なのに、空でよい理由が書かれていない欄がある：\n  " + "\n  ".join(warui)
            + "\n  build_site.KARA_DE_YOI に理由を書くか、空にしないこと")

    # **理由のほうも空にしない。** 「空でよい」と書いただけでは理由にならない
    for k, riyu in yoi.items():
        if not (riyu or "").strip():
            raise AssertionError(f"KARA_DE_YOI の {k} に理由が書かれていない")


def test_消えるまでの日数を仮定で書いていないか():
    """**仮定を書いたら、当たるかを測る。**

    2026-09-19。案出しから「今週消える縦覧情報」の案が来た。作れる。
    だが統括は「縦覧は4か月」という仮定を持っていた。**測ったら外れた。**

        ±14日以内で当たった   25
        **外れた**            89

    しかも実績は**収集先ごとにまったく違う**（中央値 0日〜144日）。
    ひとつの平均にまとめてはいけない。

    見張るのは3つ。
    ① 消えない置き場（`cumulative`）を混ぜないこと。混ぜると「ほとんど消えない」になる
    ② 仮定が当たるかを**測っていること**（`katei_wa_ataru` が在る）
    ③ 記録に「**こちらが見てから**」と書いてあること。「載ってから」は分からない

    **捕まえないもの**：中央値が正しいか。数字は毎朝動く。
    """
    import importlib
    import json
    michi = os.path.join(HERE, "data", "all.json")
    if not os.path.exists(michi):
        return
    ki = importlib.import_module("kieru")
    recs = json.load(open(michi, encoding="utf-8"))

    # ① 消えない置き場を混ぜない
    nise = [{"mode": "cumulative", "listed": False, "source": "x",
             "first_seen": "2026-01-01", "last_seen": "2026-06-01"}]
    if ki.measure(nise)[0]:
        raise AssertionError(
            "cumulative（消えない置き場）を数えている。"
            "混ぜると「ほとんど消えない」という嘘の数字になる")

    # ② 仮定が当たるかを測っている。**当たっていなくてよい。測っていることが要る**
    #
    # 2026-09-25、比べる時点を last_seen から kakunin_saigo（完全観測の日のうち、
    # 見えた最後の日）に直した（共通指示書4）。手元の data/all.json が、まだこの印を
    # 1件も持っていない（parse.py がこの直しのあとにまだ書き直していない）ときは、
    # ここでは測れない——ファイルが無いときと同じに扱う（安全側）。
    if not any(r.get("kakunin_saigo") for r in recs):
        return
    ok, ng, _ = ki.katei_wa_ataru(recs)
    if ok + ng == 0:
        raise AssertionError(
            "「縦覧は4か月」の仮定を1件も突き合わせていない。"
            "仮定を書いたら、当たるかを測る")

    # ③ 記録の言い方。**主語をこちらにする**
    kiroku = os.path.join(HERE, "data", "ref", "kieru.md")
    if not os.path.exists(kiroku):
        return
    honbun = open(kiroku, encoding="utf-8").read()
    if "こちらが最後に見た日" not in honbun:
        raise AssertionError(
            "記録に「こちらが最後に見た日」と書かれていない。"
            "持っているのは相手が消した日ではない（3.5）")

    # **中央値は出さない**（2026-09-19、[運営者]「情報としてしょぼい」）。
    # こちらの観測の話であって、読む人に関係がない
    if "中央値" in honbun and "出さない" not in honbun:
        raise AssertionError("記録に中央値が出ている。こちらの観測の話で、読む人に関係がない")

    # **区間で書く。** 「消えた日」を点で言わない
    if "点ではなく" not in honbun:
        raise AssertionError(
            "「消えた日」を点として書いている。"
            "持っているのは最後に在るのを見た日で、消えたのはその後のどこか（3.5）")


def test_消えたことの書き方():
    """**「消えた」も主張。主語をこちらにする。**

    2026-09-19、[運営者]の——

    > ネットから消えた日の件は、**SEO対策で語句を選ばないといけない**にゃね

    そのとおりで、しかも語句を選ぶ前に**外れない形**にする必要があった。
    それまでこう書いていた。

        ❌ 自治体のページには載らなくなりました
           → **自治体のページの話。** こちらが見に行けなかっただけかもしれない
             （URL が変わった・取得に失敗した・robots が変わった）
        ✅ ◯月◯日を最後に、自治体のページでは**見つかっていません**

    そして**消えた日は点ではない**ので、そこも書く。

    見張るのは3つ。
    ① 「載らなくなりました」のような、相手を主語にした断定が無いこと
    ② 消えたものは**説明文（description）にも入る**こと
       —— 検索から着いた人が「役所のページに無い」をそこで知る
    ③ 「まだ在る」側も主語がこちらであること

    **捕まえないもの**：実際に検索で上がるか。後日 Search Console で見る。
    """
    src = open(os.path.join(HERE, "build_site.py"), encoding="utf-8").read()

    # ① 相手を主語にした断定
    for warui in ("載らなくなりました", "削除されました", "消滅しました"):
        i = src.find(warui)
        while i >= 0:
            atama = src.rfind("\n", 0, i) + 1
            if not src[atama:i].lstrip().startswith("#"):
                raise AssertionError(
                    f"{src[:i].count(chr(10)) + 1}行目の「{warui}」は相手を主語にした断定。"
                    "こちらが見に行けなかっただけかもしれない（3.5）")
            i = src.find(warui, i + 1)

    # ②③ 出来上がった個票で見る
    import glob
    import json
    zairyo = os.path.join(HERE, "data", "all.json")
    if not os.path.exists(zairyo):
        return
    recs = json.load(open(zairyo, encoding="utf-8"))
    # **listed は3つの値**（2026-09-24、merge.listed_wo_kimeru）。「見つかっていません」と書くのは
    # 取得がそろった観測で見えなかったもの（false）だけ。未判定（null）には書かない
    kieta = [r for r in recs if r.get("mode") == "snapshot"
             and r.get("listed") is False and r.get("last_seen")]
    aru = [r for r in recs if r.get("mode") == "snapshot" and r.get("listed") is True]
    for rows, kotoba, nani in (
            (kieta[:30], "見つかっていません", "消えたもの"),
            (aru[:30], "こちらが最後に見た", "まだ在るもの")):
        for r in rows:
            michi = os.path.join(HERE, "s", f"{r['key']}.html")
            if not os.path.exists(michi):
                continue
            h = open(michi, encoding="utf-8").read()
            if kotoba not in h:
                raise AssertionError(
                    f"{nani}の個票に「{kotoba}」が入っていない（{os.path.basename(michi)}）")

    # ② 説明文にも入る
    for r in kieta[:30]:
        michi = os.path.join(HERE, "s", f"{r['key']}.html")
        if not os.path.exists(michi):
            continue
        h = open(michi, encoding="utf-8").read()
        m = re.search(r'name="description" content="([^"]*)"', h)
        if m and "見つかっていません" not in m.group(1):
            raise AssertionError(
                f"消えたものの説明文に入っていない（{os.path.basename(michi)}）。"
                "検索から着いた人が、役所のページに無いことをそこで知る")


def test_辿れる側の一覧を手で書いていないか():
    """**印を足す所と、辿れる側に数える所が別だと、片方を忘れる。**

    2026-09-19、開発系の報告——

    > `KOMAKAI` から印を1つ落としたら**鳴らなかった**。①定数を読む検査も、
    > ②実データで数える検査も通る。変わるのは「番まで辿れる見込み」の1行だけ。

    **統括でも試したら同じだった。** 81.9% が 61.6% になっても、
    **検査77本すべて通った。**

    直し方は見張りを足すことではなく、**2か所を1か所にすること。**
    `KOMAKAI` は `KATACHI` の「どこまで当たるか」から作る。

    そのうえで、**紙に書いた割合を、いま数え直した割合と突き合わせる。**
    導き方そのものが壊れたときに鳴る。

    **捕まえないもの**：印があれば本当に座標が当たるか。まだ引き当てていない。
    """
    import importlib
    import json
    ak = importlib.import_module("addr_katachi")

    # ① **手で書いていない。** 表から作られている
    # **語ではなく真偽で見る**（2026-09-19、開発系の指摘）。
    # 「置けない」という語で当てていたら、「点を置けません」と
    # 書き換えただけで黙る。**名前の一覧をやめて、語の一致にしただけだった**
    hyo = {name for name, _d, tadoreru, _m in ak.KATACHI if tadoreru}
    if any("置けない" in (m or "") for _n, _d, _t, m in ak.KATACHI):
        raise AssertionError(
            "KATACHI の「どこまで当たるか」に判定用の語が混ざっている。"
            "画面に出す文（OKENAI）は真偽から作ること")

    # **本数を留める**（開発系のやり方、2026-09-19）。
    # 真偽から導くと、導く側と確かめる側が同じものを見ることになり、
    # **真偽を1つ裏返しても鳴らない**（実際に試して鳴らなかった）。
    # 構造にできない所は本数で見る——壊し方の表と同じ扱い。
    #
    # 印を足したら、ここも直す。**直すときに「辿れる側か」を1回決めさせる**のが狙い
    TADORERU, OKENAI_KAZU = 4, 2
    if (len(ak.KOMAKAI), len(ak.KATACHI) - len(ak.KOMAKAI)) != (TADORERU, OKENAI_KAZU):
        raise AssertionError(
            f"辿れる印が {len(ak.KOMAKAI)}・置けない印が "
            f"{len(ak.KATACHI) - len(ak.KOMAKAI)} になっている"
            f"（{TADORERU}・{OKENAI_KAZU} のはず）。"
            "印を足したか、真偽を裏返したか。**どちらも1回決め直すこと**")
    if set(ak.KOMAKAI) != hyo:
        raise AssertionError(
            f"KOMAKAI {sorted(ak.KOMAKAI)} が、表から作った {sorted(hyo)} と違う。"
            "2か所あると、印を足した日に片方を忘れる")

    # ② **紙の割合と、いま数え直した割合が合うか**
    zairyo = os.path.join(HERE, "data", "all.json")
    kami = os.path.join(HERE, "data", "ref", "addr-katachi.md")
    if not (os.path.exists(zairyo) and os.path.exists(kami)):
        return
    recs = json.load(open(zairyo, encoding="utf-8"))
    zentai, _rei = ak.measure(recs)
    okeru = sum(zentai.get(k, 0) for k in ak.KOMAKAI)
    honbun = open(kami, encoding="utf-8").read()
    if f"{okeru:,}件" not in honbun:
        raise AssertionError(
            f"紙の「番まで辿れる見込み」が、いま数えた {okeru:,}件 と合わない。"
            "印を足したのに、辿れる側に数えていないか")


def test_括弧の中だけに数字がある住所():
    """**括弧の中と「外◯筆」は、場所の細かさではない。**

    開発系が測って教えてくれた（2026-09-19）。向こうの実データ199件では
    **2つの書き方で1件も違わなかった**が——

    > 0件なのは開発系の話で、4サイトの話ではないにゃ

    **そのとおりだった。こちらでは5件出た。**

        川西市火打一丁目（中央北地区特定土地区画整理事業◯街区◯◯―◯画地ほか）

    括弧の中は区画整理の仮換地表示で、**地番ではない。**
    印は4サイト共通なので、統括が直して4本とも同じ日に変える。

    直したあとは**0件が正しい姿**。0でなくなったら、括弧の中の
    書き方が増えたということなので、そこで見直す。
    """
    import importlib
    import json
    ak = importlib.import_module("addr_katachi")

    # **見本は実物から取る**（開発系が送ってきた形と、こちらの実データ）
    for text, hoshii in (
            ("美方郡香美町香住区山手外1筆", True),
            ("京都市北区上賀茂薮田町（12街区）", True),
            ("北区長曽根町3456－7 ほか", False),
            ("門真市江端町", False),
    ):
        if ak.kakko_dake(text) != hoshii:
            raise AssertionError(f"「{text}」の判定が違う（{ak.kakko_dake(text)}）")

    zairyo = os.path.join(HERE, "data", "all.json")
    if not os.path.exists(zairyo):
        return
    nokori = ak.kuichigai(json.load(open(zairyo, encoding="utf-8")))
    if nokori:
        raise AssertionError(
            f"略記と読んだもので、数字が括弧か「外◯筆」にしかないものが {len(nokori)}件ある"
            f"（例 {nokori[0].get('address')}）。"
            "括弧の中は場所の細かさではない。**正本に上げること**")


def test_移り変わりと複数を見分けているか():
    """**「名前が移り変わった」と「同じ日に複数いる」は別のこと。**

    2026-09-19、フロアマップの案が出たので、うちのデータで
    どこまで見えるかを測った。そこで**1回まちがえた。**

    どちらも「その建物に出てくる名前が2つ以上か」で数えていたので、
    **2つの行が同じ数（103）を出していた。** 名前だけ違う同じ数。

    競売統計の「市区町村92は升92だった」とまったく同じ形。
    そして見分け方も向こうと同じ——**わざと逆のものを渡して、値が変わるか。**

        同じ日に2者    → 「複数いる」は1、「移り変わった」は0
        日が違って2者  → 「複数いる」は0、「移り変わった」は1

    **同じ値が出る材料では、この検査は何も言っていない。**

    **捕まえないもの**：社名変更か入れ替えか。届出に書かれていない。
    """
    import importlib
    ki = importlib.import_module("kouri")

    # ① 同じ日に2者。**複数いるが、移り変わってはいない**
    onaji = [{"store": "A館", "retailer": "甲社", "notified_on": "2026-01-01"},
             {"store": "A館", "retailer": "乙社", "notified_on": "2026-01-01"}]
    _t, utsuri, fukusu = ki.measure(onaji)
    if utsuri or not fukusu:
        raise AssertionError(
            f"同じ日に2者を、移り変わり {len(utsuri)}・複数 {len(fukusu)} と読んだ。"
            "移り変わり0・複数1 のはず")

    # ② 日が違って2者。**移り変わったが、同じ日に複数はいない**
    chigau = [{"store": "B館", "retailer": "甲社", "notified_on": "2020-01-01"},
              {"store": "B館", "retailer": "乙社", "notified_on": "2026-01-01"}]
    _t, utsuri, fukusu = ki.measure(chigau)
    if not utsuri or fukusu:
        raise AssertionError(
            f"日が違う2者を、移り変わり {len(utsuri)}・複数 {len(fukusu)} と読んだ。"
            "移り変わり1・複数0 のはず")

    # ③ **会社の種類は落とさない。** 落とすと社名変更が見えなくなる
    if ki.norm("㈱イオン") == ki.norm("イオンリテール㈱"):
        raise AssertionError("会社の種類まで落としている。社名変更が見えなくなる")
    if ki.norm("上新電機 ㈱") != ki.norm("上新電機㈱"):
        raise AssertionError("空白を落としていない。表記ゆれが別の会社に見える")


def test_遅延証明書のページをURLで当てていないか():
    """**在りかを知らないものは、辿って見つける。作文しない。**

    2026-09-19、[運営者]の案。5つのルール全部に○が付いた唯一の題材で、
    **個人が1人も出てこない**（3.1 の問題がゼロ）。

    だが**遅延証明書のページの在りかは知らない。** そこで
    `https://…/train/delay/` のような URL を書くと、**在りかを作文した**ことになる。
    地図データで同じところを一度通っている（目録を引いて、向こうが書いた URL を使った）。

    見張るのは3つ。
    ① 一覧に**トップページだけ**が入っていること（深い URL を書いていない）
    ② 探す語が「遅延」ではなく「**遅延証明**」であること
       —— 「遅延情報」は**いまの運行**の話で、欲しいのは**過去の記録**
    ③ 「全部見た」と書いていないこと（この一覧は大阪・兵庫の全社ではない）

    **捕まえないもの**：見つけたページが本当に遅延証明書か。
    実物を人が1回見てから読み取りを書く。
    """
    import importlib
    import urllib.parse
    cr = importlib.import_module("chien_recon")

    # ① トップページだけ。**深い URL を書かない**
    for na, u in cr.KAISHA:
        p = urllib.parse.urlparse(u)
        if p.path not in ("", "/"):
            raise AssertionError(
                f"{na} に深い URL が書かれている（{u}）。"
                "遅延証明書の在りかは知らない。**トップから辿ること**")

    # ② 「遅延」ではなく「遅延証明」で探す
    if cr.SAGASU.search("遅延情報"):
        raise AssertionError(
            "「遅延情報」に当たっている。それは**いまの運行**の話で、"
            "欲しいのは**過去の記録**（遅延証明書）")
    if not cr.SAGASU.search("遅延証明書"):
        raise AssertionError("「遅延証明書」に当たらない")

    # ③ 記録に「全部」と書かない
    michi = os.path.join(HERE, "data", "ref", "chien-recon.md")
    if os.path.exists(michi):
        honbun = open(michi, encoding="utf-8").read()
        if "全社ではない" not in honbun:
            raise AssertionError(
                "記録に「この一覧は全社ではない」が書かれていない。"
                "分母を添えずに件数を出さない（3.2）")

    # **リンクを拾う所を、実物の形で確かめる**（見本は実物から取る）
    mihon = (b'<html><body>'
             b'<a href="/train/delay_info/">\xe9\x81\x85\xe5\xbb\xb6\xe6\x83\x85\xe5\xa0\xb1</a>'
             b'<a href="/train/delay_cert/">\xe9\x81\x85\xe5\xbb\xb6\xe8\xa8\xbc\xe6\x98\x8e\xe6\x9b\xb8</a>'
             b'</body></html>')
    deta = cr.sagasu("https://example.invalid/", mihon, "text/html; charset=utf-8")
    saki = [u for u, _t in deta]
    if "https://example.invalid/train/delay_cert/" not in saki:
        raise AssertionError(f"遅延証明書のリンクを拾えていない（{saki}）")
    if any("delay_info" in u for u in saki):
        raise AssertionError(f"遅延情報まで拾っている（{saki}）")

    # ④ **1社の不調で、残りを見ないようにしない。**
    #
    # ここは一度 `break` にしていた。自治体を回る `recon.py` は
    # **同じ相手**を続けて見るので中止が正しいが、**ここは1社ごとに相手が違う。**
    # 混んでいるのはその1社だけで、**押し込まないのはその相手に対してだけ。**
    src = open(os.path.join(HERE, "chien_recon.py"), encoding="utf-8").read()
    for shirushi in ("except Konde:", "if ok is None:"):
        i = src.index(shirushi)
        ato = src[i:i + 500]
        # その処理の中で、次の `except`/`if` が来る前に break していないか
        kugiri = min((ato.index(x) for x in ("\n        except", "\n        try:")
                      if x in ato[1:]), default=len(ato))
        if re.search(r"^\s+break\s*$", ato[:kugiri], re.M):
            raise AssertionError(
                f"{shirushi} で break している。**1社の不調で残りを見なくなる。**"
                "相手が1社ごとに違うので、飛ばすのはその社だけ")


def test_全部同じ理由で失敗したら自分を疑うか():
    """**全部が同じ理由で失敗したら、相手ではなく自分を疑う。**

    2026-09-19、統括がこれをやった。**外に出られない環境で走らせて、
    その結果を記録として commit した。**

        | こちらが出られなかった | 10 |

    数え方は正しい。「こちらが出られなかった」は**こちらの事実**だから。
    だが**全件がそれなら、相手について何も言っていない。**
    記録には**どこから走ったかが書いていない**ので、
    main で読んだ人は「鉄道会社に繋がらない」と読む。

    今日の「相手が答えた／こちらが出られなかった」を分けたのは正しかったが、
    **分けただけでは足りなかった。** 全件がこちら側なら、そう書く。

    **捕まえないもの**：なぜ出られないか。回線か、proxy か、相手か。
    **分からないので書かない。**
    """
    src = open(os.path.join(HERE, "chien_recon.py"), encoding="utf-8").read()
    if "1社にも接続できていない" not in src:
        raise AssertionError(
            "全件が「こちらが出られなかった」のときに、記録で断っていない。"
            "そのままだと、相手について何も言っていない数が読まれる")

    michi = os.path.join(HERE, "data", "ref", "chien-recon.md")
    if not os.path.exists(michi):
        return
    honbun = open(michi, encoding="utf-8").read()
    import re as _re
    m = _re.search(r"\| \*\*こちらが出られなかった\*\* \| ([\d,]+) \|", honbun)
    k = _re.search(r"\| この一覧に載せた会社 \| ([\d,]+) \|", honbun)
    if not (m and k):
        return
    derarenai = int(m.group(1).replace(",", ""))
    if derarenai and derarenai == int(k.group(1).replace(",", "")):
        if "1社にも接続できていない" not in honbun:
            raise AssertionError(
                "記録で全件が「出られなかった」なのに、断りが書かれていない")


def test_記録から行き先を読めるか():
    """**2段目は、1段目の記録から読む。統括の記憶からは読まない。**

    そして**見本は実物から取る。** 下の文字列は、2026-09-19 に
    `chien_recon.py` が実際に書いた `chien-recon.md` から切り取ったもの。
    **思いついた形で試さない。**

    ここで一度踏んだ形を、そのまま見本にしてある。

    ① 上にある**件数の表**（`| | 会社数 |`）から一致が始まる
    ② **区切り線**（`|---|---|---|`）から一致が始まる
    ③ リンクの文字に**改行**が入っていて、行をまたぐ

    ①②は `re.S`（改行もまたぐ）を付けたせいで、**JR西日本の行を
    まるごと食べていた。** ③は書く側が改行を残したせい。
    **読む側を器用にせず、書く側を直した**（`chien_recon.moji`）。

    **捕まえないもの**：その行き先が本当に遅延証明書か。実物を見てから決める。
    """
    import importlib
    cg = importlib.import_module("chien_get")
    cr = importlib.import_module("chien_recon")
    import tempfile

    # **実物から切り取った見本**（件数の表・区切り線・改行入りの行を含む）
    mihon = (
        "# 遅延証明書のページを探した記録\n\n"
        "| | 会社数 |\n|---|---:|\n"
        "| **リンクが見つかった** | 9 |\n"
        "| トップに無かった | 1 |\n\n"
        "## 見つかったリンク\n\n"
        "| 会社 | リンクの文字 | 行き先 |\n|---|---|---|\n"
        "| JR西日本 | 遅延証明書新しいウィンドウで開きます | "
        "http://delay.trafficinfo.westjr.co.jp/ |\n"
        "| 阪急電鉄 | 運行状況\n          \n            遅延証明書\n"
        "           | https://www.hankyu.co.jp/railinfo/index.html |\n"
        "| 阪神電気鉄道 | 遅延証明書 | https://www.hanshin.co.jp/system/delay/ |\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".md", encoding="utf-8",
                                     delete=False) as f:
        f.write(mihon)
        kari = f.name
    try:
        deta = cg.yomu(kari)
    finally:
        os.unlink(kari)

    saki = {na: u for na, u in deta}
    # ① 件数の表から拾わない
    if any(na.startswith("**") or na == "" for na in saki):
        raise AssertionError(f"件数の表から拾っている（{sorted(saki)}）")
    # ② JR西日本が食べられていない。**http のまま**
    if saki.get("JR西日本") != "http://delay.trafficinfo.westjr.co.jp/":
        raise AssertionError(
            f"JR西日本が読めていない（{saki.get('JR西日本')}）。"
            "区切り線や件数の表から一致が始まっていないか。"
            "**http を https に書き換えてもいけない**")
    if "阪神電気鉄道" not in saki:
        raise AssertionError("改行入りの行のあとが読めていない")

    # ③ **書く側が改行を残さない**
    if "\n" in cr.moji("運行状況\n   \n  遅延証明書\n  "):
        raise AssertionError(
            "リンクの文字に改行が残っている。記録の表が1行に収まらない")

    # **同じページを2回取りに行かない**（クエリ違いは同じとみなす）
    with tempfile.NamedTemporaryFile("w", suffix=".md", encoding="utf-8",
                                     delete=False) as f:
        f.write("| 会社 | 文字 | 行き先 |\n|---|---|---|\n"
                "| 甲社 | あ | https://example.invalid/a/ |\n"
                "| 甲社 | い | https://example.invalid/a?x=1 |\n")
        kari = f.name
    try:
        if len(cg.yomu(kari)) != 1:
            raise AssertionError("クエリだけ違う同じページを2回取りに行く形になっている")
    finally:
        os.unlink(kari)


def test_下見は数えるだけか():
    """**下見は「何が在るか」を数えるだけ。読み取らない。**

    2026-09-19、遅延証明書の2段目。10社ぶん取れたが、
    **中身をまだ1文字も見ていない。** そして
    「**何日分残っているか**」が、このサイトでいちばん効く数字。

    実物を見ないと決められないので、**形だけ数える。**

    ① 日付を**組み立てない。** 見つけた文字列をそのまま並べる
    ② 「YYYY年M月D日」と「M月D日」を**別に数える**
       —— 同じものを2回数えているのではなく、**書き方が違う**
    ③ 見つからなかったら「無い」と書く。**0件にしない**

    **捕まえないもの**：その日付が遅延の日付か。ページの更新日かもしれない。
    **人が実物を1回見るまで、決めない。**
    """
    import importlib
    cg = importlib.import_module("chien_get")

    # **見本は実物の形から**（遅延証明書の表によくある形）
    h = ("<html><body><table>"
         "<tr><td>2026年9月19日</td><td>10分</td></tr>"
         "<tr><td>2026年9月18日</td><td>5分</td></tr>"
         "</table></body></html>").encode("utf-8")
    m = cg.shitami(h)

    if m["hyo"] != 1:
        raise AssertionError(f"表の数が {m['hyo']}。1 のはず")
    if m["fun"] != 2:
        raise AssertionError(f"「◯分」の数が {m['fun']}。2 のはず")
    if m["hiduke"].get("YYYY年M月D日") != 2:
        raise AssertionError(f"日付を数えられていない（{m['hiduke']}）")
    # ② 書き方ごとに別で数える
    if "M月D日" not in m["hiduke"]:
        raise AssertionError(
            "「M月D日」を別に数えていない。**書き方が違うものを1つにまとめない**")
    # ① **組み立てない。** 見つけた文字列がそのまま出る
    for x in m["rei"]:
        if x not in ("2026年9月19日", "2026年9月18日", "9月19日", "9月18日"):
            raise AssertionError(f"見つけていない文字列が出ている（{x}）。組み立てている")

    # ③ 日付が無いページは「無い」。**0 と書かない**
    kara = cg.shitami(b"<html><body>\xe4\xbb\x8a\xe6\x97\xa5</body></html>")
    if kara["hiduke"]:
        raise AssertionError(f"日付が無いのに何か数えている（{kara['hiduke']}）")

    # **記録の側でも「無い」と書く**
    src = open(os.path.join(HERE, "chien_get.py"), encoding="utf-8").read()
    if "**無い**" not in src:
        raise AssertionError("日付が見つからないとき、記録に「無い」と書いていない")


def test_保健所を目録から探しているか():
    """**URL を作文しない。既に在る目録を引く。**

    2026-09-19、案出しの調査——兵庫県の保健所の営業許可は
    **毎月20日頃に上書き**（ファイル名固定）。
    **いま始めないと過去は取り返せない**ので、探す段だけ先に作った。

    見張るのは3つ。
    ① 目録の URL が**既に `sources.json` に在るもの**であること
       —— 新しい URL を書いたら、それは在りかを作文したことになる
    ② 探す語が「許可」ではなく「**営業許可**」であること
       —— 「許可」だけだと建築確認まで拾う
    ③ 記録に**対象区域の但し書き**が書いてあること
       —— 兵庫県の一覧は神戸市・姫路市・尼崎市・明石市・西宮市を除く。
          読まずに「兵庫県全部」と名乗ると、人口の多いところが抜ける

    **捕まえないもの**：見つけたものが本当に営業許可の一覧か。実物を見てから決める。
    """
    import importlib
    import json
    hr = importlib.import_module("hokenjo_recon")

    # ① 目録は既に収集先に在るもの
    michi = os.path.join(HERE, "sources.json")
    if os.path.exists(michi):
        with open(michi, encoding="utf-8") as f:
            url_ra = {s.get("url", "") for s in json.load(f)["sources"]}
        if not any(u.startswith(hr.MOKUROKU) for u in url_ra):
            raise AssertionError(
                f"目録 {hr.MOKUROKU} が sources.json に無い。"
                "**在りかを作文している**")

    # ② 「許可」だけで探さない
    if "許可" in hr.KOTOBA:
        raise AssertionError("「許可」だけで探している。建築確認まで拾う")
    if "営業許可" not in hr.KOTOBA:
        raise AssertionError("「営業許可」で探していない")

    # 拾う所を**実物の形**で確かめる。
    #
    # **問い合わせの語は、こちらが URL に入れたもの。** 目録は探した語を
    # query に持つので、**ページ上のすべてのリンク**に語が入る。
    # 2026-09-20 の初回がこれで、「当たった3」の中身は
    # 並べ替えリンクと「本文へスキップします。」だった——
    # **1つも一覧ではなかった**（9節「返ってきたは見つかったではない」）。
    base = ("https://web.pref.hyogo.lg.jp/opendata/index.php"
            "?keyword=%E5%96%B6%E6%A5%AD%E8%A8%B1%E5%8F%AF")
    h = ("<html><body>"
         "<a href='?p=1_1&asc=summary&keyword=%E5%96%B6%E6%A5%AD%E8%A8%B1%E5%8F%AF'>"
         "並べ替え</a>"
         "<a href='#tmp_honbun'>本文へスキップします。</a>"
         "<a href='/opendata/d/123'>飲食店営業許可一覧</a>"
         "<a href='/files/x.xlsx'>営業許可（エクセル）</a>"
         "<a href='/other'>建築確認</a>"
         "</body></html>").encode("utf-8")
    de = hr.hirou(base, h, "text/html; charset=utf-8", "営業許可")
    for t, u, _f in de:
        if "keyword=" in u or "tmp_honbun" in u:
            raise AssertionError(
                f"**こちらが URL に入れた語で当てている**（{t!r} → {u}）。"
                "目録のページは全リンクに語が入る")
    if len(de) != 2:
        raise AssertionError(f"拾えた数が {len(de)}。2 のはず（{de}）")
    if not any(f for _t, _u, f in de):
        raise AssertionError("ファイルとページを見分けていない")
    if any("建築確認" in t for t, _u, _f in de):
        raise AssertionError("関係ないものまで拾っている")

    # ③ 対象区域の但し書き
    src = open(os.path.join(HERE, "hokenjo_recon.py"), encoding="utf-8").read()
    for kotoba in ("対象区域", "神戸市"):
        if kotoba not in src:
            raise AssertionError(
                f"記録に「{kotoba}」の但し書きが無い。"
                "兵庫県の一覧は兵庫県全部ではない")


def test_知らない種類が入口から消えないか():
    """**一覧で回すと、一覧に無いものは作られるのに、どこからも行けない。**

    2026-09-20、開発ちゃんが自分の所で見つけた形——
    **報告の組み立てが系統名の一覧で回っていて、一覧に無い系統は
    収集も保存もされるのに紙にだけ出ない。**

    統括にも同じものが在った。種類ごとのページは実データから作るのに、
    入口のリンクだけ `for k in KIND_ORDER` で並べていた。
    **知らない種類は、ページが作られてどこからも行けない。**

    **今日は正しく動いている**（いまある種類は全部一覧に在る）。
    **足した日に黙る。** 監査の r1-26 と同じ族で、
    「見張りを名前の一覧で作らない」の**画面版**。

    一覧は**順番のため**に残してよい。**落とさなければいい。**

    **捕まえないもの**：並び順が読みやすいか。ここは落ちないことだけ。
    """
    from collections import Counter
    import build_site

    # ① 知らない種類が後ろに付く（落ちない）
    k = Counter({"新設": 3, "廃止": 2, "まだ無い種類": 1})
    de = build_site.kind_narabi(k)
    if "まだ無い種類" not in de:
        raise AssertionError(f"知らない種類が落ちている（{de}）")
    if de[:2] != ["新設", "廃止"]:
        raise AssertionError(f"知っている種類の順が崩れた（{de}）")

    # ② 0件は出さない（空の入口を作らない）
    if "廃止" in build_site.kind_narabi(Counter({"新設": 1, "廃止": 0})):
        raise AssertionError("0件の種類まで入口に出している")

    # ③ 出来上がりの側。**作った種類のページに、全部リンクが在るか**
    import glob as _glob
    michi = os.path.join(HERE, "index.html")
    if not os.path.exists(michi):
        return
    honbun = open(michi, encoding="utf-8").read()
    nai = [os.path.basename(f)[:-5]
           for f in _glob.glob(os.path.join(HERE, "k", "*.html"))
           if f'k/{os.path.basename(f)}' not in honbun]
    if nai:
        raise AssertionError(
            f"種類のページを作ったのに、トップから行けない: {nai}")


def test_外に出る前に検査を走らせているか():
    """**伏せ忘れがあるまま取りに行くと、その日のぶんが汚れる。**

    正本4節「テスト」（ワークフローの最初のステップで走らせる）。
    落ちたらそこで止まり、**1バイトも取りに行かない。**

    2026-09-20 の監査（r1-43）で、地図の手順書に無いのが見つかった。
    直したついでに**全部の手順書を数えたら、ほかに2本無かった**
    （遅延証明書と保健所。どちらも監査より**あとに書いたもの**）。

    **一覧で持たない。** 外に出る `.py` を走らせる手順書を構造で拾って、
    そこに `check.sh` の段があるかを見る。**手順書が増えても勝手に見る。**

    「見張りを名前の一覧で作らない」（9節）の、**手順書版**。
    指摘を1本ずつ直すと、**次に書いた1本がまた抜ける。**

    **捕まえないもの**：検査の中身。そちらは検査そのものが見る。
    """
    import re as _re
    soto = {os.path.basename(m) for m in soto_ni_deru()}
    nai = []
    for michi in workflow_files():
        honbun = open(michi, encoding="utf-8").read()
        hashiru = {f"{n}.py" for n in
                   _re.findall(r"python3\s+([A-Za-z0-9_./-]+)\.py", honbun)}
        if not (hashiru & soto):
            continue                      # 外に出ない手順書は数えない
        if "check.sh" not in honbun:
            nai.append(f"{os.path.basename(michi)}（{sorted(hashiru & soto)}）")
    if nai:
        raise AssertionError(
            "外に出るのに、先に検査を走らせていない手順書：\n  "
            + "\n  ".join(nai)
            + "\n  伏せ忘れがあるまま取りに行くと、その日のぶんが汚れる（4節）")


def test_毎回読み込まれる1枚が短いままか():
    """**解こうとしている問題を、自分で作らない。**

    `CLAUDE.md` は毎回自動で読み込まれる。だから**長くすると、それ自体が
    「文脈が重い」という、この1枚が解こうとしている問題になる。**

    2026-09-20 に作ったときの長さは 61 行。**ここが膨らむのは、
    「大事だから書いておこう」を1回ずつ足したとき。** 1回ずつは正しい。

    足したくなったら、**正本（`docs/kyotsu-shiyo.md`）か
    `docs/hikitsugi.md` に書く。** ここに置くのは
    **読み飛ばされても届かないと困る線**だけ。

    **捕まえないもの**：中身が正しいか。そちらは正本との突き合わせで見る。
    """
    michi = os.path.join(HERE, "CLAUDE.md")
    if not os.path.exists(michi):
        return
    gyou = open(michi, encoding="utf-8").read().splitlines()
    if len(gyou) > 90:
        raise AssertionError(
            f"CLAUDE.md が {len(gyou)} 行。**毎回読み込まれる1枚が長い。**"
            " 足したいものは正本か引き継ぎ書へ（ここは読み飛ばされても"
            "届かないと困る線だけ）")


def test_取りに行く段が条件で消えていないか():
    """**条件で消えた段は、消えたことを誰にも言わない。**

    2026-09-20、自分で踏んだ。遅延証明書を毎日ためる段を入れたとき、
    金庫（private の置き場）がある回だけ走る条件を付けた。

        if: ${{ env.HAS_VAULT == 'true' && ... }}

    **このリポジトリは金庫の形ではない**（生データを自分で追跡している
    旧来の形）。つまり**1度も走らない段**を入れて、「毎日たまります」と
    報告していた。緑のまま、何も起きない。

    金庫の有無は**しまい方**の話で、**取りに行くかどうかの話ではない。**
    取得は取り返せない（今日ぶんしか出さない相手がいる）。
    **しまい先が変わるだけで、取りに行くのは毎回。**

    見張り方は、**外に出る .py を走らせる段**を構造で拾って、
    そこに金庫の条件が付いていないかを見る（名前の一覧は持たない）。

    **捕まえないもの**：しまい方が正しいか。そちらは
    「公開側に生データが混ざったら止まる」段が見る。
    """
    import re as _re
    soto = {os.path.basename(m) for m in soto_ni_deru()}
    warui = []
    for michi in workflow_files():
        honbun = open(michi, encoding="utf-8").read()
        if "schedule:" not in honbun:
            continue                      # 手で押す回は、押した人が見ている
        # 段ごとに切って、走らせる .py と if: を組にする
        for dan in _re.split(r"\n      - name: ", honbun)[1:]:
            hashiru = {f"{n}.py" for n in
                       _re.findall(r"python3\s+([A-Za-z0-9_./-]+)\.py", dan)}
            if not (hashiru & soto):
                continue
            joken = _re.search(r"^        if:(.*)$", dan, _re.M)
            if joken and "HAS_VAULT" in joken.group(1):
                warui.append(f"{os.path.basename(michi)}: "
                             f"{sorted(hashiru & soto)} が金庫の条件で消える")
    if warui:
        raise AssertionError(
            "取りに行く段に、金庫の有無の条件が付いている：\n  "
            + "\n  ".join(warui)
            + "\n  金庫はしまい方の話。**取りに行くのは毎回**（取得は取り返せない）")


def test_当事者の語が正本とそろっているか():
    """**手で写した一覧は、写した日からずれ始める。**

    2026-09-20 の監査（r1-40）。`is_party_column()` が見る語が、
    正本の一覧より**6語少なかった**。

        落札者  落札者名  契約相手方  契約の相手方  買受人  譲受人

    **落ちている側の間違い**なので、何も壊れない。
    落とした列は privacy を通らないまま、**そのまま公開される。**

    正本にはこう書いてある——**当事者の語は落とすと地番が出る側**なので、
    足すのは安全側。だから**一覧は手で持ったままでよい**（勝手に増やすと、
    関係のない列まで伏せてしまう）。**ずれたらここが鳴る。**

    **捕まえないもの**：正本の一覧が足りているか。新しい列名に出会った
    サイトが足す。そのとき**この検査がコード側の足し忘れを止める。**
    """
    import re as _re
    from common import privacy

    michi = os.path.join(HERE, "docs", "kyotsu-shiyo.md")
    if not os.path.exists(michi):
        return
    honbun = open(michi, encoding="utf-8").read()
    m = _re.search(r"### 当事者を指す列名.*?```\n(.*?)```", honbun, _re.S)
    if not m:
        raise AssertionError("正本に「当事者を指す列名」の囲みが無い")
    seihon = set(m.group(1).split())
    if len(seihon) < 5:
        raise AssertionError(f"正本の語が少なすぎる（{sorted(seihon)}）。読み方が壊れている")

    morashi = sorted(w for w in seihon if not privacy._PARTY_WORD.search(w))
    if morashi:
        raise AssertionError(
            f"正本にあるのに privacy が見ていない当事者の語: {morashi}。"
            "**その列は伏せずに公開される**")


def test_作ったページが公開の許可リストから漏れていないか():
    """**直したのに公開されないのが、いちばん気づかない。**

    2026-09-20 の監査（r1-42）。毎朝の巡回が「公開してよいもの」を
    **手で並べた一覧**で入れていて、そこから4本が漏れていた。

        taiten.html  settisha.html  shinsetsu-to-kaiten.html  style.css

    落ちているのは**出力のほう**なので、何も壊れない。
    ページは毎朝ちゃんと作り直されて、**そのまま捨てられていた。**
    その日に直した文言が、いつまでも site に出ない。

    許可リスト自体は**手で並べたままでよい**——生データを入れないための
    守りなので、勝手に増える形にはしない。**漏れをここが鳴らす。**
    「見張りを名前の一覧で作らない」を、**一覧の側ではなく見張りの側**で守る。

    **捕まえないもの**：許可リストに入っているものが本当に公開してよいか。
    そちらは workflow の中の見張り（生データ・symlink が混ざったら止まる）が見る。
    """
    import re as _re
    michi = [m for m in workflow_files() if "shutten-recon" in os.path.basename(m)]
    if not michi:
        return
    honbun = open(michi[0], encoding="utf-8").read()
    kyoka = set()
    # 金庫の形では、許可リストは `git add` 直書きではなく
    # `for p in <一覧…>; do … git add -A -- "$p"; done`（許可リストの見張り・
    # 2026-09-25）。**折り返し（末尾の \\）をまたいで**一覧全体を拾う
    for m in _re.finditer(r"for\s+\S+\s+in\s+(.*?);\s*do", honbun, _re.S):
        kyoka |= set(m.group(1).replace("\\", " ").split())
    # `git add` の行に並ぶ語を全部集める。**行の続き（末尾の \\）も拾う**——
    # 一覧が長くなると折り返すので、1行しか見ないと後ろ半分が「無い」ことになる
    tsuzuki = False
    for gyou in honbun.splitlines():
        if not (tsuzuki or "git add " in gyou):
            continue
        kyoka |= set(gyou.replace("git add", " ").replace("\\", " ").split())
        tsuzuki = gyou.rstrip().endswith("\\")

    import glob as _glob
    tsukuru = [os.path.basename(f)
               for f in _glob.glob(os.path.join(HERE, "*.html"))
               + _glob.glob(os.path.join(HERE, "*.css"))]
    morashi = sorted(f for f in tsukuru if f not in kyoka)
    if morashi:
        raise AssertionError(
            f"作っているのに公開の許可リストに無いページ: {morashi}。"
            "**毎朝作り直して、そのまま捨てている**")


def test_全国の会社をドメインで作文していないか():
    """**200社のドメインを思い出して並べたら、それは作文。**

    2026-09-20、[運営者]の「遅延証明はかるいから全国にひろげてほしい」。
    10社なら目で確かめられるが、全国で同じことをすると、
    **当たっているかを誰も確かめられないドメインが並ぶ。**
    外れていれば**関係のない誰かのサーバーを叩く**（3.4）。

    なので役所の一覧から引く。見張るのは5つ。

    ① `chien_zenkoku.py` に、種いがいの行き先が直に書かれていないこと
    ② 同じ役所かどうかを**組織のところ**で見ること
       —— 事業者の一覧は**地方運輸局**（`wwwtb.mlit.go.jp`）にある。
          ホストまるごとで見ると、種（`www.mlit.go.jp`）と別物になり、
          **いちばん欲しいページを最初に落とす**
    ③ `.lg.jp` を落とさないこと —— **市営地下鉄は自治体のドメイン**
    ④ HTML でない別紙を「事業者0本」と数えないこと
       —— 役所の一覧は PDF のことがある。リンクの式は必ず0を返す
    ⑤ 次の段が、**どの一覧を使ったか**を言うこと（ルール⑥）

    **捕まえないもの**：拾ったホストが本当に鉄道事業者か。
    そこは探しに行って、無ければ無いと記録する。
    """
    import importlib
    import re as _re
    cz = importlib.import_module("chien_zenkoku")
    cr = importlib.import_module("chien_recon")

    # ① 種いがいの行き先を直に書いていない
    src = open(os.path.join(HERE, "chien_zenkoku.py"), encoding="utf-8").read()
    kaki = set()
    for i, gyou in enumerate(src.splitlines(), 1):
        if gyou.lstrip().startswith("#"):
            continue
        for u in _re.findall(r"https?://[^\s\"'<>)]+", gyou):
            if not cz.TANE.startswith(u) and u != cz.TANE:
                kaki.add(f"{i}: {u}")
    if kaki:
        raise AssertionError(
            f"種いがいの行き先が直に書いてある: {sorted(kaki)[:4]}。"
            "**一覧を作文している**")

    # ② 地方運輸局を「同じ役所」と見る（ここで1回踏んだ）
    if not cz.onaji_yakusho("https://wwwtb.mlit.go.jp/kanto/tetudou/x.htm"):
        raise AssertionError(
            "地方運輸局を別の役所と見ている。**事業者の一覧はそこにある**")
    if cz.onaji_yakusho("https://www.soumu.go.jp/"):
        raise AssertionError("よその省まで同じ役所と見ている")

    # ③ 市営地下鉄（.lg.jp）を落とさない。よそ（交流サイト）は落とす
    h = ("<a href='https://www.example-tetsudo.co.jp/'>架空鉄道</a>"
         "<a href='https://www.example-tetsudo.co.jp/rosen/'>路線図</a>"
         "<a href='https://www.city.example.lg.jp/chikatetsu/'>架空市交通局</a>"
         "<a href='https://twitter.com/example'>X</a>"
         "<a href='https://www.mlit.go.jp/tetudo/'>戻る</a>").encode("utf-8")
    de = cz.jigyousha("https://wwwtb.mlit.go.jp/x.htm", h, "text/html")
    hosts = {x[1] for x in de}
    if "www.city.example.lg.jp" not in hosts:
        raise AssertionError("市営地下鉄（.lg.jp）を落としている")
    if "twitter.com" in hosts or "www.mlit.go.jp" in hosts:
        raise AssertionError(f"事業者でないものを拾っている（{sorted(hosts)}）")
    if len(de) != 2:
        raise AssertionError(f"同じホストを重ねていない（{sorted(hosts)}）")
    if not all(u.count("/") == 3 for _t, _h, u in de):
        raise AssertionError(f"行き先をトップに丸めていない（{de}）")

    # ④ HTML でない別紙を 0本 と混ぜない
    for kotoba in ("HTML でなかった", "読んでいない"):
        if kotoba not in src:
            raise AssertionError(
                f"記録に「{kotoba}」が無い。PDF の別紙が「事業者0本」に化ける")

    # ⑤ どの一覧を使ったかを言う
    kai, doko = cr.kaisha()
    if not kai or not doko:
        raise AssertionError("会社の一覧か、その出どころが空")
    if "全国" not in doko and "手で並べた" not in doko:
        raise AssertionError(f"一覧の出どころを名乗っていない（{doko!r}）")


def test_升が本当に数えているか():
    """**升を全部「1-2」にしても、升を1枚も作らなくても、誰も鳴らなかった。**

    2026-09-20 の監査（r1-20・r1-22）。`build_site.py` の中には
    足し算の確かめがあるが、**見ているのは伏せる前の数**なので、

    * `masked()` が壊れて全部 `None` になっても
    * 升に入る条件が外れて `counts_by_city` が空になっても

    どちらも**そのまま出る。** 前者は「全部 1〜2件のサイト」に、
    後者は「数えていないサイト」に見える。

    ここは**出来上がった `index.json` だけを見て**確かめる。
    作り手の数え方を写すと、同じ間違いを2回書くことになる（9節）。

    **区間で挟む。** 伏せた升は1件か2件のどちらかなので、

        実数の合計 ＋ 1×伏せた升 ≦ 升に入った個票 ≦ 実数の合計 ＋ 2×伏せた升

    全部 `None` になると左端が上がりきって**入らなくなる。**
    凍らせた数を持たないので、**毎日増えても鳴らない。**

    **捕まえないもの**：どの升にどの届出が入るか。ここは総数の話。
    """
    import json
    michi = os.path.join(HERE, "index.json")
    if not os.path.exists(michi):
        return
    with open(michi, encoding="utf-8") as f:
        d = json.load(f)
    masu = d.get("counts_by_city") or []
    kohyo = len(d.get("records") or [])
    hairanai = sum((d.get("not_counted") or {}).values())

    if kohyo and not masu:
        raise AssertionError(f"個票が {kohyo:,} 件あるのに升が1枚も無い")

    # ① 入らなかったものが大半なら、升の条件が外れている。
    #    **凍らせた数にしない**（毎日増えるので、動いたこと自体は当たり前）
    if kohyo and hairanai > kohyo * 0.05:
        raise AssertionError(
            f"升に入らなかったものが {hairanai:,}／{kohyo:,} 件。"
            "5%を超えた。**升の条件が外れている**")

    # ② 伏せた升と実数の升。**片方が全部になったら鳴る**
    jissu = [m["count"] for m in masu if m.get("count") is not None]
    fuseta = len(masu) - len(jissu)
    if not jissu:
        raise AssertionError(
            f"升 {len(masu):,} 枚が**全部伏せ字**。masked() が壊れている疑い")

    # ③ 区間で挟む
    haitta = kohyo - hairanai
    shita, ue = sum(jissu) + fuseta, sum(jissu) + fuseta * 2
    if not (shita <= haitta <= ue):
        raise AssertionError(
            f"升の中身が個票と合わない。升に入ったはずの {haitta:,} 件が、"
            f"升から見た {shita:,}〜{ue:,} 件の外にある")

    # ④ 伏せた値と、人に見せる文字列が食い違わない（6節の2本立て）
    for m in masu:
        if (m.get("count") is None) != (m.get("count_label") == "1-2"):
            raise AssertionError(
                f"升の count と count_label が食い違っている: {m}")


def test_pyの拾い方が1か所か():
    """**拾い方が4通りあると、どれが見ているか誰にも分からない。**

    2026-09-20 の監査（r1-01/02/03/06/08/09）。検査の中に、
    見に行く .py の並べ方が**4通り**あった。

        glob(HERE/*.py)                           引数の関所
        glob(HERE/*.py) + glob(common/*.py)       3本
        ＋ glob(scripts/*.py)                     読めるかの検査

    **`scripts/` はもう無い**（消した日に、この行だけ残った）。
    逆に、引数の関所は **`common/` を1本も見ていなかった。**

    「見張りを名前の一覧で作らない」（9節）の、**置き場の一覧**版。
    一覧で持つと、**足した日ではなく、足したことを忘れた日に黙る。**

    見張るのは2つ。
    ① `subete_no_py()` が、**git が知っている .py を1本残らず含む**こと
       —— git は別の数え方なので、歩き方が置き場を飛ばせば食い違う
    ② 検査の中に、**もう一度 .py を並べ直している所が無い**こと

    **捕まえないもの**：拾った .py を正しく見ているか。ここは拾うところだけ。
    """
    import subprocess
    hirotta = {os.path.relpath(m, HERE) for m in subete_no_py(nozoku=())}

    # ① git が知っているものと突き合わせる（**別の数え方**で確かめる）
    r = subprocess.run(["git", "ls-files", "*.py"],
                       cwd=HERE, capture_output=True, text=True)
    if r.returncode == 0 and r.stdout.strip():
        git_no = {x for x in r.stdout.split("\n") if x.strip()}
        morashi = sorted(git_no - hirotta)
        if morashi:
            raise AssertionError(
                f"git が知っている .py を拾えていない: {morashi[:5]}。"
                "**歩き方が置き場を飛ばしている**")

    # ② 並べ直している所が無いか。**この検査の説明文は数えない**
    #    （説明に書いた `glob(...)` の形に自分で引っかかる。2026-09-19 に3回踏んだ）
    # **探す語を、そのままの形で1行に書かない。** この行が自分に当たる
    # （2026-09-19、衝突マーカーの見張りで3回踏んだ）
    hari = "glob.glob" + "("
    hoshi = '"*' + '.py"'
    nokori = []
    for i, gyou in enumerate(
            open(os.path.join(HERE, "test_privacy.py"), encoding="utf-8"), 1):
        if gyou.lstrip().startswith("#"):
            continue
        if hari in gyou and hoshi in gyou:
            nokori.append(i)
    if nokori:
        raise AssertionError(
            f"検査の中で .py を並べ直している行がある（{nokori}）。"
            "**subete_no_py() を通すこと**")


def test_伏せたと名乗るのは本当に伏せたときだけか():
    """**丸めるものが無いのに「丸めた」と書かない。**

    2026-09-20 に見つけた。「所在地を町丁目まで丸めた」と名乗る 823 件のうち
    **436 件は、取ってきた一覧に所在地の欄がそもそも無かった。**
    神戸市の一覧も兵庫県の縦覧も、ページに所在地の列が無い
    （`data/raw/` の実物で確かめた。見出しは 届出年月日・店舗名称・縦覧期間・概要）。

    ルール⑥「名乗りは事実の主張になる」。
    **「こちらが伏せた」と「向こうが載せていない」は、読者にとって別のこと。**
    前者は「あるが見せない」、後者は「探しても無い」。
    前者だと思った人は、原本に当たれば地番が載っていると考える。

    **捕まえないもの**：所在地が無い理由が、向こうが書いていないからか、
    こちらが読めなかったからか。そこは分けられない。だから名乗りも
    「**取ってきた一覧に入っていなかった**」——こちらが受け取った物の話にする。
    """
    import json
    import merge

    # ① 作った印が、実物どおりに付くか（**架空の名前だけを使う**）
    recs = [
        {"key": "a1", "source": "test", "kind": "新設", "store": "架空ストア一号店",
         "address": "兵庫県架空市架空町一丁目2番3", "operator": "架空 太郎"},
        {"key": "a2", "source": "test", "kind": "変更", "store": "架空ストア二号店",
         "address": "", "operator": ""},
    ]
    marumeta, nakatta = merge.apply_privacy(recs)
    if (marumeta, nakatta) != (2, 1):
        raise AssertionError(f"数え方が変わった（丸めた {marumeta} / 無かった {nakatta}）")
    if not recs[0].get("address_redacted") or recs[0].get("address_nakatta"):
        raise AssertionError("地番があったのに「伏せた」と名乗っていない")
    if recs[1].get("address_redacted"):
        raise AssertionError(
            "**所在地が空なのに「伏せた」と名乗っている。** 丸めるものが無い")
    if not recs[1].get("address_nakatta"):
        raise AssertionError("元から無かったことを書き留めていない")

    # ② 出来上がりの側。**1件でも残っていたら鳴る**
    michi = os.path.join(HERE, "data", "all.json")
    if not os.path.exists(michi):
        return
    with open(michi, encoding="utf-8") as f:
        zenbu = json.load(f)
    uso = [r for r in zenbu
           if r.get("address_redacted") and not (r.get("address") or "").strip()]
    if uso:
        raise AssertionError(
            f"所在地が空なのに「伏せた」と名乗る記録が {len(uso):,} 件ある"
            f"（例 {uso[0].get('source')}）。merge.py を走らせ直すこと")

    # ③ 個票の文言。**両方が同じ言い方だと、読者に見分けられない**
    src = open(os.path.join(HERE, "build_site.py"), encoding="utf-8").read()
    if "address_nakatta" not in src:
        raise AssertionError("個票が、元から無かった場合を書き分けていない")


def test_作業手順書が別の仕事の記録を巻き込まないか():
    """**写して作った手順書は、写し元の名前を連れてくる。**

    2026-09-20、保健所の手順書を遅延証明書のものから写して作った。
    最後の「記録を残す」でこう書いてあった。

        git add data/ref/hokenjo-recon.md data/ref/chien-get.md

    **保健所を走らせただけの回が、遅延証明書の記録を
    「保健所の記録」という題名で入れてしまう。**
    入る中身は正しいのに、**いつ・何をして変わったのかが履歴から消える。**

    見張り方は、**名前の一覧を持たない**こと（9節）。
    手順書が走らせた `◯◯_....py` の頭と、`git add` に並ぶ
    `data/ref/◯◯-....md` の頭を突き合わせる。**手順書が増えても勝手に見る。**

    **捕まえないもの**：その記録の中身が正しいか。ここは名前だけの話。

    **門（common/kado.py）の控えは、どの取得の回でも門自身が書く**（今日もう見たか・機械札）。
    その回の仕事の記録なので、どの手順書が入れてもよい。名前は一覧で持たず、
    門が書く置き場の定義（`kado.KYOU`・`kado.FUDA_PATH`）から引く。
    """
    from common import kado as _kado
    mon_no_hikae = {os.path.splitext(os.path.basename(p))[0]
                    for p in (_kado.KYOU, _kado.FUDA_PATH)}
    warui = []
    for michi in workflow_files():
        with open(michi, encoding="utf-8", errors="ignore") as f:
            honbun = f.read()
        # この手順書が走らせる .py の頭（chien_recon.py → chien）
        hashiru = {m.split("_")[0]
                   for m in re.findall(r"python3\s+([A-Za-z0-9_]+)\.py", honbun)}
        if not hashiru:
            continue
        for gyou in honbun.splitlines():
            if "git add " not in gyou:
                continue
            for michi2 in re.findall(r"data/ref/([A-Za-z0-9_-]+)\.[a-z]+", gyou):
                if michi2 in mon_no_hikae:
                    continue
                if michi2.split("-")[0] not in hashiru:
                    warui.append(
                        f"{os.path.basename(michi)} が data/ref/{michi2} を入れる"
                        f"（走らせるのは {sorted(hashiru)} だけ）")
    if warui:
        raise AssertionError(
            "手順書が、自分が走らせていない仕事の記録を巻き込んでいる: "
            + "; ".join(warui))


def test_姓を地方公共団体と読んでいないか():
    """**「◯村」で終わるだけでは、地方公共団体ではない。**

    2026-09-19 の監査（r1-39）で出た。`PUBLIC_RE` がこう書いてあった。

        |(都|道|府|県|市|区|町|村)$

    **日本でいちばん多い姓が8つとも法人扱いになり、氏名と地番がそのまま出た。**
    3.1 のいちばん重いところ。

    直し方は**実在の名前と突き合わせる**こと（総務省の団体コードの一覧）。
    **一覧が手に入らないときは「地方公共団体ではない」とみなす。**
    そちらに倒すと伏せる側に寄る——**その既定値で外に出るのは氏名と地番**
    なので、止まる側に倒す（9節）。

    ここに並べているのは**姓だけ**で、実在の人を指していない。

    **捕まえないもの**：一覧に無い自治体があるか。合併や新設で増える。
    増えたら `ref_jis.py` が取り直す。
    """
    from common import privacy

    # ① 姓を法人扱いにしない
    warui = [n for n in ("中村", "木村", "田村", "西村", "大村",
                         "北村", "野村", "今村", "川村", "松村")
             if privacy.is_corp(n)]
    if warui:
        raise AssertionError(
            f"姓を法人扱いしている：{' '.join(warui)}。"
            "**氏名と地番がそのまま出る**（3.1）")

    # ② 本物の自治体は法人のまま
    for n in ("兵庫県", "神戸市", "三木市", "宝塚市", "大阪市北区",
              "兵庫県知事", "神戸市長"):
        if not privacy.is_corp(n):
            raise AssertionError(f"{n} を個人扱いしている")

    # ③ **一覧が無いときは、伏せる側に倒れる**
    kara = privacy.jichitai_mei("/zzz/nai.json")
    if kara:
        raise AssertionError("一覧が無いのに何か返している")

    # ④ 法人はそのまま
    for n in ("株式会社イオン", "イオンリテール㈱", "上新電機株式会社"):
        if not privacy.is_corp(n):
            raise AssertionError(f"{n} を個人扱いしている")


def test_中規模を大店立地法と書いていないか():
    """**「中規模」は大店立地法ではなく、八尾市・堺市の条例。**

    2026-09-19。個票の description が 4,809件ぜんぶ
    「大規模小売店舗立地法の◯◯届出」で始まっていて、**中規模137件で外れていた。**

    面白いのは、**出典の注には最初から正しく書いてあった**こと
    （「八尾市・堺市の『中規模』は、法ではなく市の条例に基づく届出です」）。
    文書と実装は別の場所なので、**別々にずれる**（正本9節）。

    **捕まえないもの**：条例の名前が市ごとに正しいか。そこまでは書かない。
    """
    src = open(os.path.join(HERE, "build_site.py"), encoding="utf-8").read()
    if "市の条例" not in src:
        raise AssertionError("中規模の届出を、条例ではなく法にもとづくものとして書いている")

    # **実際に作った説明文で見る。** ソースの字面だけだと、
    # 分岐を書いたのに使っていない、を見逃す（正本9節「別の行で組み立てた書き先」）
    import glob
    atta = False
    for michi in glob.glob(os.path.join(HERE, "s", "*.html"))[:20000]:
        with open(michi, encoding="utf-8") as f:
            honbun = f.read(1200)
        if "の中規模届出" not in honbun:
            continue
        atta = True
        if "大規模小売店舗立地法の中規模届出" in honbun:
            raise AssertionError(
                f"{os.path.basename(michi)} が中規模を大店立地法と書いている")
    if not atta:
        return   # まだ組み立てていない（CI の順番による）


def test_日付の呼び名が種類を取りこぼしていないか():
    """**知らない種類が来たら、黙って「予定日」と書かずに止まる。**

    build_site の KIND_HIZUKE に無い種類に日付が付いていたら ValueError。
    ゆるい既定値にすると、外（4,809ページ）に「予定日」と出てしまう。
    **その既定値で動いたとき外に何かが出るなら、止まる側に倒す**（正本9節）。

    実データで見る。「意見・勧告」は 4,809件で日付を持たないので表に無くてよい。
    **持ちはじめた日に、ここが鳴る。**

    **捕まえないもの**：呼び名が日本語として正しいか。それは人が読む。
    """
    import importlib, json
    michi = os.path.join(HERE, "data", "all.json")
    if not os.path.exists(michi):
        return
    bs = importlib.import_module("build_site")
    recs = json.load(open(michi, encoding="utf-8"))

    motsu = {}
    for r in recs:
        if r.get("event_on") or r.get("planned_on"):
            motsu[r.get("kind")] = motsu.get(r.get("kind"), 0) + 1
    morashi = {k: n for k, n in motsu.items() if k not in bs.KIND_HIZUKE}
    if morashi:
        raise AssertionError(
            f"日付を持つのに KIND_HIZUKE に無い種類がある: {morashi}。"
            "このままだと個票に「予定日」と出る")


def test_過ぎた日を予定と呼んでいないか():
    """**「予定」は事実の主張で、2,001件で外れていた。**

    2026-09-19 に数えた。届出日より前の日が入っているもの：
    変更1,760・承継143・廃止94・新設2・中規模2。
    それまで個票には「予定日」、新設には「開店予定日」と書いていた。

    **数は動く**（毎朝増える）ので、この検査は数を固定しない。
    固定するのは「**過ぎた日が現に有る**」という形のほうで、
    それが1件でも有る限り「予定」とは書けない、という理由を残す。

    **捕まえないもの**：なぜ届出より前の日が入るのか。
    変更届は事後に出せるものがあるため、と読んでいるが確かめていない。
    """
    import importlib, json
    michi = os.path.join(HERE, "data", "all.json")
    if not os.path.exists(michi):
        return
    bs = importlib.import_module("build_site")
    recs = json.load(open(michi, encoding="utf-8"))

    sugita = 0
    for r in recs:
        ev = r.get("event_on") or r.get("planned_on")
        if ev and ev < r["notified_on"]:
            sugita += 1
    if sugita == 0:
        # 0件になったら「予定」と呼んでよくなるが、**勝手に戻さない。**
        # 数え方が壊れたほうを先に疑う（正本9節「鳴らなかったら、まず壊し方を疑う」）
        raise AssertionError(
            "届出日より前の日が1件も無い。2026-09-19 には2,001件あった。"
            "数え方が壊れていないか先に見る")
    for kind, (yobina, _) in bs.KIND_HIZUKE.items():
        if "予定" in yobina:
            raise AssertionError(
                f"過ぎた日が{sugita}件あるのに、{kind} を「{yobina}」と呼んでいる")


def test_split_city():
    """4節。**開発系が実データ456件で確かめた形を、そのまま固定する。**

    値は要約ではなく、向こうが実際に踏んだ住所（2026-09-19 に受け取った）。
    """
    from common import addr
    codes = addr.load_codes()
    if not codes:
        return

    # ① 住所そのものから切れる。**呼ぶ側の市は被せない**
    for text, want_pref, want_city in (
            ("岡山県備前市三石字山鼻731番11", "岡山県", "備前市"),
            ("兵庫県洲本市由良町由良字小佐毘濱2452番1", "兵庫県", "洲本市"),
            ("大阪府泉南郡岬町多奈川小島467番", "大阪府", "岬町")):
        got = addr.split_city(text, "大阪府", "大阪市", codes)
        eq((got["pref"], got["city"], got["city_source"]),
           (want_pref, want_city, "住所"), f"住所から切れる（{want_city}）")

    # ② 郡を落とした形でも当てる（コード表に郡は入っていない）
    got = addr.split_city("赤穂郡上郡町大持字段68番1", "兵庫県", "", codes)
    eq((got["city"], got["city_source"]), ("上郡町", "住所"), "郡を落として当てる")

    # ③ 台帳で補う。**補ったと記録する**
    got = addr.split_city("福島区海老江八丁目44番6", "大阪府", "大阪市", codes)
    eq((got["city"], got["city_precision"], got["city_source"]),
       ("大阪市福島区", "区", "台帳"), "区だけ書いてある")
    got = addr.split_city("矢田五丁目", "大阪府", "大阪市", codes)
    eq((got["city"], got["city_precision"], got["city_source"]),
       ("大阪市", "市", "台帳"), "市も区も書いていない")

    # ④ 決まらないものは空。**読み替えない**（篠山市→丹波篠山市 に直さない）
    got = addr.split_city("篠山市山内町64番３", "兵庫県", "", codes)
    eq((got["city"], got["city_source"]), ("", ""), "コード表に無い市は空のまま")

    # ⑤ **ヒントは狭めるためにだけ使う。**
    #    外して全国から探すと、大阪市の「北区梅田一丁目」が東京都北区になる。
    #    開発系の実データでは、台帳で補った121件のうち23件がこの形だった
    hazard = addr.split_city("北区梅田一丁目", "", "", codes)
    eq((hazard["pref"], hazard["city"]), ("東京都", "北区"),
       "ヒントを外すと他県に当たる（この形があるので広げてはいけない）")
    safe = addr.split_city("北区梅田一丁目", "大阪府", "大阪市", codes)
    eq((safe["pref"], safe["city"], safe["city_source"]),
       ("大阪府", "大阪市北区", "台帳"), "ヒントがあれば狭まる")

    # ⑥ 同じ名前の町が2つの府県にある。**管轄で絞る側の仕事**。
    #    split_city 自身は渡された府県で答える。勝手に選ばない
    for pref in ("大阪府", "兵庫県"):
        got = addr.split_city("太子町鵤123番", pref, "", codes)
        eq((got["pref"], got["city"]), (pref, "太子町"),
           f"太子町は渡された府県で答える（{pref}）")


def test_正本に書いた署名が実装にあるか():
    """5節の code block に書いた `def` が、`common/privacy.py` に実在するか。

    2026-09-19、開発系が突き合わせて見つけた。**2件ずれていた。**

        residential_reason(*texts)    文書に署名あり／**実装に無い**
        redact_name(name, names=())   文書は names あり／実装は (name)

    どちらも**文書を直して、コードを直していない**形。
    `common/MANIFEST.txt` は置き場どうしを比べる紙なので、
    **文書とコードのずれは映らない。** 4つの置き場が同じようにずれていたら
    全部通る。見る向きが違うので、別の検査が要る。
    """
    import ast
    import re as _re
    from common import privacy

    doc = open(os.path.join(HERE, "docs", "kyotsu-shiyo.md"), encoding="utf-8").read()
    sec = doc[doc.index("\n## 5."):doc.index("\n## 6.")]
    want = {}
    for m in _re.finditer(r"^def (\w+)\(([^)]*)\)", sec, _re.M):
        want[m.group(1)] = m.group(2)
    if len(want) < 5:
        raise AssertionError(f"5節から署名を{len(want)}個しか拾えていない。拾い方が壊れている")

    tree = ast.parse(open(privacy.__file__, encoding="utf-8").read())
    have = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}

    bad = []
    for name, params in sorted(want.items()):
        fn = have.get(name)
        if fn is None:
            bad.append(f"{name}(): 文書にあるが **実装に無い**")
            continue
        # 型の注記と既定値を落として、引数の名前だけを比べる
        doc_args = [a.split(":")[0].split("=")[0].strip().lstrip("*")
                    for a in params.split(",") if a.strip()]
        code_args = ([a.arg for a in fn.args.args]
                     + ([fn.args.vararg.arg] if fn.args.vararg else []))
        if doc_args != code_args:
            bad.append(f"{name}(): 文書 {doc_args} / 実装 {code_args}")
    if bad:
        raise AssertionError("正本の文書と実装がずれている：\n  " + "\n  ".join(bad))


def test_呼ばれていない守りの関数にそう書いてあるか():
    """5節は「人の判断ではなくコードで守る層」。

    **署名だけあって呼ばれていない関数は、守っているように見えて
    何も守っていない。** 次に読む人が「ここを通っているから安全」と
    思い込む（9節・2026-09-19）。だから**呼ばれていないと書く。**

    **捕まえないもの**：書いてある理由が正しいか。
    「呼んでいない」と書いてあるだけで通る。
    """
    import ast
    import glob
    from common import privacy

    tree = ast.parse(open(privacy.__file__, encoding="utf-8").read())
    funcs = {n.name: n for n in tree.body
             if isinstance(n, ast.FunctionDef) and not n.name.startswith("_")}
    called = set()
    for fp in subete_no_py():
        base = os.path.basename(fp)
        if base == "privacy.py":
            continue
        for node in ast.walk(ast.parse(open(fp, encoding="utf-8").read())):
            if isinstance(node, ast.Call):
                name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
                if name in funcs:
                    called.add(name)

    # **呼ばれている関数の中から呼ばれているものも、呼ばれている。**
    #
    # 2026-09-19 の監査で足りないところが出た。ここは
    # **「本番のファイルから直に呼ばれているか」しか見ていなかった。**
    # `is_corp` が `is_public` を呼び、`is_public` が `jichitai_mei` を呼ぶ形だと、
    # 中の2つが「呼ばれていない」と出る。**実際は本番で毎回通る。**
    #
    # privacy.py の中の呼び合いを辿って、届くものを足す。
    naka = {}
    for name, node in funcs.items():
        naka[name] = {getattr(c.func, "attr", None) or getattr(c.func, "id", None)
                      for c in ast.walk(node) if isinstance(c, ast.Call)}
    while True:
        fueta = {y for x in called for y in naka.get(x, ()) if y in funcs} - called
        if not fueta:
            break
        called |= fueta

    bad = []
    for name, node in sorted(funcs.items()):
        if name in called:
            continue
        doc = ast.get_docstring(node) or ""
        # **目印を1つに決める。** ふつうの言い回しで見ると、
        # 説明の中の同じ言葉で通ってしまう（実際に通った。2026-09-19）
        if "【本番から呼ばれていない】" not in doc:
            bad.append(name)
    if bad:
        raise AssertionError(
            "本番から呼ばれていないのに、呼ばれていないと書いていない関数："
            + " / ".join(bad)
            + "（守っているように見えて何も守っていない。docstring に書くこと）")


def test_common_の指紋が中身と合っているか():
    """`common/` を直したら、指紋の一覧も同じコミットで直す。

    2026-09-19、開発系が突き合わせたら `common/addr.py` が
    369行 と 197行で**別物**だった。しかも向こうが読んだのはさらに古い
    169行の版で、**ずれが二重になっていた。**
    正本11節の手順3「各サイトの common/ を更新する」は、人が覚える形
    だったので守られていなかった。機械が言うようにする。
    """
    import subprocess
    r = subprocess.run([sys.executable, os.path.join(HERE, "common_manifest.py"),
                        "--check"], capture_output=True, text=True, cwd=HERE)
    if r.returncode != 0:
        raise AssertionError(
            (r.stderr.strip() or r.stdout.strip()) +
            "（common/ を直したら、同じコミットで一覧も作り直す）")


def aite_no_host(name):
    """その .py が出て行く先のホストを、**実物から**集める。

    2026-09-20。「1日に2回行かない」を、**workflow の本数ではなく
    相手の数**で見張るために作った。

    2通り拾う。**片方だけだと漏れる。**

    * ソースに直に書いてある `https://…` のホスト（遅延証明書の10社など）
    * `sources.json` を読むと書いてあれば、そこに並ぶホスト全部（毎朝の巡回）

    **多めに拾う。** 記録に「トップに無かった会社」として書いてある相手も
    数に入る。**行かない相手を「行く」と数えるほうが、逆より安全**だから
    （3.4・既定は止まる側）。多すぎて止まったら、そのとき人が見る。

    **捕まえないもの**：辿った先で別のホストに飛ぶ場合。
    そこは行ってみないと分からない（robots はホストごとに見直している）。
    """
    import json as _json
    import re as _re
    import urllib.parse as _up
    michi = os.path.join(HERE, name)
    if not os.path.exists(michi):
        return set()
    honbun = open(michi, encoding="utf-8").read()

    # **本人に聞くのが先。** `ikisaki()` を持っている .py は、そこが行き先の正本。
    # 目で拾うと、記録の「トップに無かった会社」まで行き先に数えてしまう
    # （2026-09-20、神戸市営地下鉄でこれが起きた）
    if _re.search(r"^def ikisaki\(", honbun, _re.M):
        import importlib
        mod = importlib.import_module(
            os.path.splitext(os.path.basename(name))[0])
        return {h for h in (_up.urlsplit(u).netloc for u in mod.ikisaki()) if h}

    de = {_up.urlsplit(u).netloc
          for u in _re.findall(r'https?://[^\s"\'<>)]+', honbun)}
    de.discard("")
    if "sources.json" in honbun:
        michi2 = os.path.join(HERE, "sources.json")
        if os.path.exists(michi2):
            with open(michi2, encoding="utf-8") as f:
                for ss in _json.load(f)["sources"]:
                    if ss.get("url"):
                        de.add(_up.urlsplit(ss["url"]).netloc)
    # **行き先を記録から読むものがある**（遅延証明書の2段目）。
    # ソースに1つも URL が書いていないので、**そのままだと相手が0に見える。**
    # 「0件」は、その道を1回も通っていないときにも出る（9節）
    for kiroku in _re.findall(r'"([a-z0-9-]+\.md)"', honbun):
        michi3 = os.path.join(HERE, "data", "ref", kiroku)
        if os.path.exists(michi3):
            for u in _re.findall(r"https?://[^\s|<>)\]]+",
                                 open(michi3, encoding="utf-8").read()):
                de.add(_up.urlsplit(u).netloc)
    # 出どころでないもの（説明文に書いたリンク）を落とす
    return {h for h in de if not h.endswith("github.com")
            and not h.endswith("githubusercontent.com")
            and h != "creativecommons.org"}


def test_1日に2回以上取りに行かないか():
    """about ページに書いた「毎朝1回」を、機械で見張る。

    **書いたら約束になる。** 競売統計が 2026-09-19 に踏む手前で止めた——
    金庫と公開用の cron が**両方 `30 22 * * *`** で、消していなければ
    その晩に裁判所と自治体へ**2回**行っていた。ページには「1日1回」と
    書いてある（3.4／8節）。

    **捕まえないもの**：手で押した回。`workflow_dispatch` は数えない。
    人が押す回数は、この検査では守れない。
    """
    import glob
    import re as _re

    # **名前の一覧で数えない。**
    #
    # 2026-09-19、ここは一度外れた。`\b(recon|...)\.py\b` という名前の
    # 一覧で見ていたので、**`chizu_recon.py` を1文字も見ていなかった。**
    # `_` は語の文字なので `\brecon` が当たらない。
    # 新しい取得スクリプトを足しても、この見張りは黙ったままになる。
    #
    # なので**構造で見る。** workflow が走らせている `.py` を拾い、
    # **その中身が外に出て行くか**を読む（`common.fetch` を使うか、
    # `urlopen` を呼ぶか）。名前は関係ない。
    HASHIRU = _re.compile(r"python3?\s+([A-Za-z0-9_./-]+\.py)")
    DERU = _re.compile(r"from\s+common\.fetch\s+import|common\.fetch\b|urlopen\s*\(")

    def deru_ka(name):
        """その .py が外に出て行くか。**無いファイルは、無いと言う。**"""
        michi = os.path.join(HERE, name)
        if not os.path.exists(michi):
            return None
        return bool(DERU.search(open(michi, encoding="utf-8").read()))

    daily, nai, mita = [], [], 0
    for path in sorted(workflow_files()):
        text = open(path, encoding="utf-8").read()
        deru = False
        for name in set(HASHIRU.findall(text)):
            mita += 1
            d = deru_ka(name)
            if d is None:
                nai.append(f"{os.path.basename(path)} → {name}")
            elif d:
                deru = True
        if not deru:
            continue                      # 取りに行かない workflow は数えない
        for m in _re.finditer(r'cron:\s*"([^"]+)"', text):
            fields = m.group(1).split()
            if len(fields) == 5 and fields[2:] == ["*", "*", "*"]:
                aite = set()
                for name in set(HASHIRU.findall(text)):
                    aite |= aite_no_host(name)
                daily.append((f"{os.path.basename(path)}（{m.group(1)}）", aite))

    # **走らせている .py が無いのは、名前を変えたのに直し忘れた形。**
    # workflow はその場で落ちるが、落ちるのは押した日。ここなら今日わかる
    if nai:
        raise AssertionError("workflow が、無い .py を走らせようとしている：\n  "
                             + "\n  ".join(nai))
    if mita == 0:
        raise AssertionError(
            "workflow から走らせている .py が1つも見つからない。"
            "数え方（python3 ◯◯.py の探し方）が壊れている")
    # **数えるのは workflow ではなく、相手。**
    #
    # 2026-09-20 に直した。ここは「毎日走る workflow は1本まで」と数えていた。
    # about に書いてあるのは
    #
    #     自治体が公表している「届出」を**毎朝1回**とりに行き
    #
    # で、**主語は自治体。** 鉄道会社に毎日行くことは、この約束を破らない。
    # 逆に、**同じ相手に1日2回**行けば、workflow が1本でも約束を破る。
    #
    # 見張るのは「相手のサーバーに1日何回出るか」（3.4）。
    # 実際に、遅延証明書の 神戸市営地下鉄 と 自治体の 神戸市 は
    # **同じホスト**（www.city.kobe.lg.jp）。数え方を変えて初めて見えた。
    kasanari = []
    for i, (na1, aite1) in enumerate(daily):
        for na2, aite2 in daily[i + 1:]:
            onaji = sorted(aite1 & aite2)
            if onaji:
                kasanari.append(f"{na1} と {na2}: {', '.join(onaji[:4])}")
    if kasanari:
        raise AssertionError(
            "同じ相手に1日2回 行く形になっている（3.4）：\n  "
            + "\n  ".join(kasanari)
            + "\n  相手のサーバーに出る回数なので、片方に寄せること")
    if not daily:
        raise AssertionError(
            "毎日 取りに行く workflow が1つも見つからない。数え方が壊れているか、"
            "巡回が止まっている（どちらも見たい）")


# 門と逆向きに読める言い回し。**この検査の中では分けて書く**（そのまま書くと、この検査自身が鳴る）
GYAKU_KOTOBA = ("迷ったら" + "先に取る", "早い者" + "勝ち", "取得を" + "止めない",
                "押し" + "放題", "読めば" + "動く", "人が読むまで" + "1バイトも",
                # 「利用条件が禁じていても、事実だから載せられる」と読める形（2026-09-26・3.3 を直した）
                "それでも" + "載せられる")
# 歩かない置き場。**金庫（_raw）・人が置いた原本（inbox）・予約台帳（_yoyaku）は private の中身。**
# 読むと、公開の Actions の記録に private 側のパスや語が出る。どの深さでも外す
GYAKU_NOZOKU = frozenset({".git", "__pycache__", "data", "s", "_raw", "inbox", "_yoyaku"})
# **当時の記録**として残す行の印。行にこの印があれば数えない（歴史の記録を消させない）
GYAKU_TOUJI = ("当時の記録", "当時の記述")


def gyaku_no_iimawashi(ne):
    """ne の下を歩いて、門と逆向きに読める言い回しを探す。(見たファイル数, [場所「語」]) を返す。"""
    import re as _re
    pat = _re.compile("|".join(_re.escape(k) for k in GYAKU_KOTOBA))
    mita, warui = 0, []
    for d0, dirs, files in os.walk(ne):
        dirs[:] = [d for d in dirs if d not in GYAKU_NOZOKU
                   and (not d.startswith(".") or d == ".github")]
        for f in files:
            if not f.endswith((".md", ".py", ".yml")):
                continue
            p = os.path.join(d0, f)
            mita += 1
            for i, gyou in enumerate(open(p, encoding="utf-8", errors="replace"), 1):
                m = pat.search(gyou)
                if m and not any(t in gyou for t in GYAKU_TOUJI):
                    warui.append(f"{os.path.relpath(p, ne)}:{i}「{m.group(0)}」")
    return mita, warui


def test_取りに行く前の門と逆向きの言い回しが_文書とコードに残っていないか():
    """門の運用と逆に読める言い回しが、文書・コード・手順書に戻っていないかを見る（2026-09-26）。

    正本と周辺文書の全行監査で、下の言い回し（`GYAKU_KOTOBA`）が、いまの運用
    （取りに行く前の門。カードと運営者承認がそろった相手だけ・迷ったら止まる側）と
    逆向きに読めると分かった。
    **読まれる文書が逆を言うと、決まりより先にそちらが効く。**

    見る所は、この置き場の .md（CLAUDE.md・README.md・docs/）・.py（検査も含む）・
    手順書（.github/workflows/）。**拾い方は歩いて拾う**（名前の一覧で決め打ちしない）。
    **金庫（_raw）・inbox・予約台帳（_yoyaku）は見ない**（private の中身。公開の記録に出さない）。
    **当時の記録として残す行は、その行に「当時の記録」と書けば数えない**（歴史を書き換えさせない）。

    **捕まえないもの**：同じ意味を別の言葉で書いた文。そこは読む人が見る。
    """
    mita, warui = gyaku_no_iimawashi(HERE)
    if mita < 20:
        raise AssertionError(f"見たファイルが{mita}本しかない。拾い方が壊れている")
    if warui:
        raise AssertionError("取りに行く前の門と逆向きに読める言い回しが残っている：\n  "
                             + "\n  ".join(warui))


def test_逆向きの言い回しの見張りが_privateを読まず_当時の記録は残せるか():
    """上の見張りの守備範囲を、一時フォルダで確かめる（2026-09-26）。

    ① 公開側の文書に言い回しがあれば、拾う
    ② 金庫（_raw）・inbox・予約台帳（_yoyaku）の中にあっても、**読まない**（どの深さでも）
    ③ 「当時の記録」と書いた行は、数えない
    **外す置き場を消すと ② が、印を消すと ③ が、拾い方を壊すと ① が鳴る。**
    """
    import shutil as _sh
    import tempfile as _tf
    ne = _tf.mkdtemp()
    try:
        go = GYAKU_KOTOBA[0]
        oku = {
            os.path.join("docs", "ima.md"): f"いまの文。{go}。\n",
            os.path.join("docs", "mukashi.md"): f"2026-09-19 の文。{go}。（当時の記録）\n",
            os.path.join("_raw", "kinko.md"): f"金庫の中。{go}。\n",
            os.path.join("inbox", "genpon.md"): f"原本。{go}。\n",
            os.path.join("_yoyaku", "yoyaku.md"): f"予約台帳。{go}。\n",
            os.path.join("sub", "_raw", "fukai.md"): f"深い金庫。{go}。\n",
        }
        for rel, t in oku.items():
            os.makedirs(os.path.join(ne, os.path.dirname(rel)), exist_ok=True)
            with open(os.path.join(ne, rel), "w", encoding="utf-8") as f:
                f.write(t)
        mita, warui = gyaku_no_iimawashi(ne)
        mieta = sorted(w.split(":")[0].replace(os.sep, "/") for w in warui)
        if mieta != ["docs/ima.md"]:
            raise AssertionError("逆向きの言い回しの見張りの守備範囲がずれている：拾ったのは "
                                 + (", ".join(mieta) or "0件")
                                 + "（拾うのは docs/ima.md だけのはず。_raw・inbox・_yoyaku は読まない・"
                                 "当時の記録は数えない）")
    finally:
        _sh.rmtree(ne, ignore_errors=True)


def test_取り込みを止めているのに_取りに行っていると読める文を出さないか():
    """公開ページが「毎朝とりに行っている」と読める文を出していないかを見る（2026-09-26）。

    毎朝の巡回（shutten-recon.yml）の定時は 2026-09-25 に止めた。止めたあとも、
    フッター・about・トップが「毎朝1回とりに行き」「毎朝7時ごろ（最終 作った日）」と
    書いていた。**名乗りは事実の主張になる。** 止めているあいだは、止めていると書く。

    見ること（作った実物で見る。ソースの文字では見ない）：
      ① 巡回の workflow に動いている cron が無いなら、build_site.TORIKOMI_TEISHI は True
      ② フッター・about・トップ・新設と開店のページに、「毎朝」「毎日」が無い
      ③ 止めているなら、フッター・about・トップに、止めているという1文が出ている
      ④ トップの「いちばん新しい取り込み」は、作った日ではなくデータの取得日

    **捕まえないもの**：定時はあるが、門で止まって取れない回。
    そのときの書き方は、再開を決めるときに決める。
    """
    import re as _re
    import build_site as bs

    wf = os.path.join(HERE, ".github", "workflows", "shutten-recon.yml")
    ugoku = bool(_re.search(r"^\s*-\s*cron:", open(wf, encoding="utf-8").read(), _re.M))
    if not ugoku and not bs.TORIKOMI_TEISHI:
        raise AssertionError("巡回の定時が止まっているのに、build_site.TORIKOMI_TEISHI が False"
                             "（取りに行っていると書く）")
    with open(bs.ALL, encoding="utf-8") as f:
        recs = json.load(f)
    with open(bs.SOURCES, encoding="utf-8") as f:
        src_meta = {x["id"]: x for x in json.load(f)["sources"]}
    saishin = bs.saishin_torikomi(recs)
    if saishin != max(r.get("fetched_on") or "" for r in recs):
        raise AssertionError("いちばん新しい取り込みの日が、データの取得日になっていない")
    tsukutta = "2099-01-01"                 # 作った日。**これが画面に出たら、名乗りの間違い**
    mono = {
        "フッター": bs.page("ためし", "<p>ためし</p>", ""),
        "about": bs.about_page(src_meta, tsukutta, saishin),
        "トップ": bs.index_page(recs, tsukutta, saishin),
        "新設と開店": bs.shinsetsu_to_kaiten_page(recs, tsukutta),
    }
    warui = [f"{na}：「{m.group(0)}」" for na, t in mono.items()
             for m in _re.finditer(r".{0,12}(毎朝|毎日).{0,12}", _re.sub(r"<[^>]+>", "", t))]
    if warui:
        raise AssertionError("取りに行っていると読める文が残っている：\n  " + "\n  ".join(warui))
    if bs.TORIKOMI_TEISHI:
        # about とトップは、本文で見る（フッターにも同じ1文があるので、全体で見ると本文から消えても通る）
        nai = [na for na in ("フッター", "about", "トップ")
               if bs.torikomi_bun() not in (mono[na] if na == "フッター" else mono[na].split("<footer>")[0])]
        if nai:
            raise AssertionError("止めていると書いていない：" + "・".join(nai))
    if f"いちばん新しい取り込みは {saishin}" not in mono["トップ"] or tsukutta in mono["トップ"].split("<script")[0]:
        raise AssertionError("トップの日付が、データの取得日ではない（作った日を出している）")
    # sitemap も名乗り。止めているあいだに「毎日変わる」と言わない
    sm = "\n".join(bs.sitemap_gyou("https://example.invalid/", ["about.html"]))
    if bs.TORIKOMI_TEISHI and "changefreq" in sm:
        raise AssertionError("取り込みを止めているのに、sitemap が changefreq を名乗っている")


def _build_site_wo_utsushi_de(recs, run_date):
    """build_site.py を、外への通信を塞いだまま、一時の写しの中で最後まで走らせる。

    写すのは置き場の全部から、.git と、作り直す出力（s・a・k）と、読み取りの控え（data/parsed）を
    除いたもの。**名前の一覧で写さない**（build_site が新しく読むファイルを足した日に黙る）。
    data/all.json だけ、渡された recs に差し替える。**公開用の木には1バイトも書かない。**
    返すのは (終了コード, 出力, 写しの根)。写しは呼んだ側が消す
    """
    import shutil
    import subprocess
    import tempfile
    ne = tempfile.mkdtemp(prefix="bs-offline-")
    utsushi = os.path.join(ne, "r")
    shutil.copytree(HERE, utsushi, ignore=lambda d, names: [
        n for n in names if (d == HERE and n in (".git", "s", "a", "k")) or n == "__pycache__"
        or (os.path.basename(d) == "data" and n == "parsed")])
    with open(os.path.join(utsushi, "data", "all.json"), "w", encoding="utf-8") as f:
        json.dump(recs, f, ensure_ascii=False)
    tozasu = os.path.join(ne, "tozasu.py")
    with open(tozasu, "w", encoding="utf-8") as f:
        f.write("""import os, runpy, socket, sys, urllib.request
yobareta = []
def _tozasu(*a, **k):
    yobareta.append(1)
    raise RuntimeError("外への通信は塞いである")
socket.socket.connect = _tozasu
socket.socket.connect_ex = _tozasu
socket.create_connection = _tozasu  # kado-soto: 検査。外への通信を塞ぐ差し替えで、外へは出ない
socket.getaddrinfo = _tozasu
class _T(urllib.request.BaseHandler):
    def default_open(self, req):
        _tozasu()
urllib.request.install_opener(urllib.request.build_opener(_T()))  # kado-soto: 検査。urllib を塞ぐ差し替えで、外へは出ない
root = sys.argv[1]
os.chdir(root)
sys.path.insert(0, root)
sys.argv = ["build_site.py"]
try:
    runpy.run_path(os.path.join(root, "build_site.py"), run_name="__main__")
finally:
    print("OUTWARD", len(yobareta))
    if yobareta:
        sys.exit(3)
""")
    env = dict(os.environ, RUN_DATE=run_date, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    env.pop("SITE_URL", None)
    r = subprocess.run([sys.executable, tozasu, utsushi], capture_output=True, env=env, timeout=600)
    out = (r.stdout + r.stderr).decode("utf-8", "replace")
    return r.returncode, out, ne


def test_build_site_が外へ出ずに最後まで走るか():
    """build_site.py の main() を、外への通信を塞いで、一時の写しの中で最後まで走らせる。

    2026-09-26、PR #58 の直し（fd019f8）で main() の `host` を消し、
    **robots.txt を書く最後の行で NameError になっていた。** ページを作る関数ごとの検査は
    全部通っていた——**main を最後まで走らせる検査が無かった。**

    確かめること：
      ① 終了コード 0（最後まで走った）
      ② 外へ出ようとした回数 0（socket の接続・名前引きと urllib を塞いで数える）
      ③ robots.txt・sitemap.xml・index.json が書かれていて、robots.txt が sitemap を指している
      ④ 作った日（RUN_DATE）を、sitemap の更新日として名乗っていない（2026-09-26・統括判断）
    """
    import shutil
    with open(os.path.join(HERE, "data", "all.json"), encoding="utf-8") as f:
        recs = json.load(f)
    # 小さく走らせる。見えなくなった扱いの行も必ず混ぜる（注記とトップの12件の道を通す）
    kieta = [r for r in recs if r.get("mode") == "snapshot" and r.get("listed") is False][:15]
    nokori = [r for r in recs if r not in kieta][:25]
    tsukutta = "2099-01-01"
    code, out, ne = _build_site_wo_utsushi_de(nokori + kieta, tsukutta)
    try:
        if code != 0:
            raise AssertionError("build_site.py が最後まで走らなかった（終了コード %d）：\n%s" % (code, out[-1500:]))
        if "OUTWARD 0" not in out:
            raise AssertionError("build_site.py が外へ出ようとした：\n" + out[-800:])
        r = os.path.join(ne, "r")
        for fn in ("robots.txt", "sitemap.xml", "index.json"):
            if not os.path.exists(os.path.join(r, fn)):
                raise AssertionError(fn + " が書かれていない")
        robots = open(os.path.join(r, "robots.txt"), encoding="utf-8").read()
        if not re.search(r"^Sitemap: https?://\S+/sitemap\.xml$", robots, re.M):
            raise AssertionError("robots.txt が sitemap を指していない：" + robots)
        sm = open(os.path.join(r, "sitemap.xml"), encoding="utf-8").read()
        if tsukutta in sm:
            raise AssertionError("作った日（%s）を、sitemap の更新日として名乗っている" % tsukutta)
    finally:
        shutil.rmtree(ne, ignore_errors=True)


def test_見えなくなった届出に_空の日付や見えなくなった日と読める日付を出さないか():
    """取得がそろった観測の日（kakunin_saigo・kieta_kakunin）が無い記録で、注記を確かめる。

    2026-09-26、9/24 の data/all.json で作り直したら、見えなくなった扱いの 457 ページが
    「最後に確認できたのは  です。 の観測では…」と**日付が空のまま**出た。
    その2つの欄が入る前の判定で、見えなくなった扱いになった記録だった。

      ① 空の日付を出さない
      ② last_seen（こちらが最後に見た日）を、見えなくなった日のように書かない。
         「取得がそろった観測」を名乗らない（その記録では確かめられない）
      ③ 2つの欄がそろっている記録は、これまでどおりの注記
      ④ トップの12件は、空の kieta_kakunin を先頭の鍵にしない。最後に確認できた日の新しい順
    """
    import build_site as bs
    with open(bs.ALL, encoding="utf-8") as f:
        recs = json.load(f)
    with open(bs.SOURCES, encoding="utf-8") as f:
        src_meta = {x["id"]: x for x in json.load(f)["sources"]}
    moto = next(r for r in recs if r.get("mode") == "snapshot")

    def tsukuru(**k):
        r = dict(moto)
        for na in ("kakunin_saigo", "kieta_kakunin", "last_seen"):
            r.pop(na, None)
        r.update(mode="snapshot", listed=False, **k)
        return r

    def chuki(r):
        t = bs.detail_page(r, {}, src_meta)
        # 検索に出る説明文（description）も同じ線で見る
        for m in re.finditer(r'<meta (?:name|property)="(?:og:)?description" content="([^"]*)"', t):
            if re.search(r"(?:^|\s)を最後に|を最後に確認し、\s*の観測|\s\s", m.group(1)):
                raise AssertionError("説明文に空の日付が出ている：" + m.group(1))
            if r.get("last_seen") and not r.get("kieta_kakunin") and "を最後に確認し、そのあとの観測" not in m.group(1):
                raise AssertionError("説明文が、最後に確認できた日の言い方になっていない：" + m.group(1))
        m = re.search(r'<p class="note">([^<]*(?:<b>.*?</b>)?[^<]*このサイトには残しています。)</p>', t, re.S)
        if not m:
            raise AssertionError("見えなくなった扱いの注記が見つからない")
        return re.sub(r"<[^>]+>", "", m.group(1))

    for r in (tsukuru(last_seen="2026-08-05"), tsukuru()):
        s = chuki(r)
        if re.search(r"のは\s*です|。\s*の観測|\s\s", s):
            raise AssertionError("空の日付が出ている：" + s)
        if "必要なページをすべて取れた日）では" in s or "取得がそろった" in s:
            raise AssertionError("確かめられない「取得がそろった観測」を名乗っている：" + s)
        if r.get("last_seen") and "最後に確認できたのは 2026-08-05 です" not in s:
            raise AssertionError("last_seen を、最後に確認できた日として書いていない：" + s)
        if re.search(r"2026-08-05\s*(に|から|を最後に)?\s*(見えなく|消え)", s):
            raise AssertionError("last_seen を、見えなくなった日のように書いている：" + s)
    s = chuki(tsukuru(last_seen="2026-09-20", kakunin_saigo="2026-09-10", kieta_kakunin="2026-09-12"))
    if "最後に確認できたのは 2026-09-10 です" not in s or "2026-09-12 の観測" not in s:
        raise AssertionError("2つの欄がそろった記録の注記が変わっている：" + s)

    # ④ トップの12件の並び
    mise = [
        tsukuru(last_seen="2026-03-01", store="ならびためしB"),
        tsukuru(last_seen="2026-09-20", store="ならびためしA"),
        tsukuru(last_seen="2026-09-20", kakunin_saigo="2026-09-10", kieta_kakunin="2026-09-12", store="ならびためしC"),
    ]
    for i, r in enumerate(mise):
        r["key"] = "narabi-%d" % i
    t = bs.index_page(mise, "2099-01-01", "")
    t = t[t.find("確認できなくなった届出"):]
    ichi = [t.find(na) for na in ("ならびためしA", "ならびためしC", "ならびためしB")]
    if -1 in ichi or ichi != sorted(ichi):
        raise AssertionError("トップの「確認できなくなった届出」が、最後に確認できた日の新しい順になっていない：" + str(ichi))


def test_workflow_の中のシェルが読めるか():
    """`run: |` の中身を bash -n にかける。

    2026-09-19、街頭窃盗統計の検査ステップが**構文エラーで壊れていた。**
    行継続を `\\`（バックスラッシュ2つ）にしていた。bash では行継続にならない。
    月次の実行がそこで落ちていて、`cat -A` で見るまで気づかなかった。
    **目で読むと `\` と `\\` は同じに見える。** だから機械で見る。

    **この検査で捕まるのは、一覧や制御構文の途中で切れた形だけ。**
    `python3 a.py \\` のように単純なコマンドの末尾だと、bash は
    「バックスラッシュという引数」と読むので**合法**で、鳴らない。
    見張りは、知っている形しか見つけられない。
    """
    import glob
    import re
    import subprocess
    bad, n = [], 0
    for path in sorted(workflow_files()):
        lines = open(path, encoding="utf-8").read().splitlines()
        i = 0
        while i < len(lines):
            m = re.match(r"^(\s*)run:\s*\|\s*$", lines[i])
            if not m:
                i += 1
                continue
            indent = len(m.group(1)) + 2
            body, j = [], i + 1
            while j < len(lines) and (
                    not lines[j].strip()
                    or len(lines[j]) - len(lines[j].lstrip()) >= indent):
                body.append(lines[j][indent:] if lines[j].strip() else "")
                j += 1
            # GitHub が先に置き換えるところは、bash から見れば ただの文字
            script = re.sub(r"\$\{\{[^}]*\}\}", "GH_EXPR", "\n".join(body))
            n += 1
            r = subprocess.run(["bash", "-n"], input=script, text=True,
                               capture_output=True)
            if r.returncode != 0:
                first = (r.stderr.strip().splitlines() or ["(理由不明)"])[0]
                bad.append(f"{os.path.basename(path)}:{i + 1} → {first}")
            i = j
    if n == 0:
        raise AssertionError("`run: |` のブロックが1つも見つからない。数え方が壊れている")
    if bad:
        raise AssertionError("workflow の中のシェルが読めない：\n  " + "\n  ".join(bad))


def test_公開側のworkflowにupload_artifactが無いか():
    """**生データを成果物（artifact）へ逃がす道を、コードで閉じる。**

    2026-09-25、共通指示書1で取得の入口をカードの門（common/kado.py）につないだ。
    門を通っても、workflow 側に `actions/upload-artifact` の段が残っていれば、
    そこから生データが public な成果物へ出てしまう（90日で消えるだけで、
    消えるまでの90日は公開されている）。

    ここは公開側の workflow（.github/workflows/*.yml・*.yaml。拡張子を
    決め打ちしない・9節）を歩いて、`actions/upload-artifact` を使っている
    段が無いかを見る。`actions/upload-pages-artifact`（GitHub Pages への
    公開）は別物なので許す——公開してよいと決めたサイト本体を配る段であって、
    生データではない。
    """
    import re as _re
    bad = []
    michi_ra = workflow_files()
    if not michi_ra:
        raise AssertionError("workflow が1本も見つからない。拾い方が壊れている")
    for path in michi_ra:
        for i, line in enumerate(open(path, encoding="utf-8").read().splitlines(), 1):
            if _re.search(r"\bactions/upload-artifact\b", line):
                bad.append(f"{os.path.basename(path)}:{i}")
    if bad:
        raise AssertionError(
            "公開側の workflow に actions/upload-artifact が残っている"
            "（生データが成果物へ逃げる道。upload-pages-artifact は別）：\n  "
            + "\n  ".join(bad))


def test_文字コードを決めつけずに読む():
    """2026-09-19。国交省の位置参照情報のページは EUC-JP だった。

    Content-Type に charset が無く、utf-8 で読んでタイトルが化けた。
    URL は ASCII なので探し物には響かなかったが、**化けたまま
    「読めている」と思っていた。**
    """
    import ref_youto

    # ① charset の宣言がどこにも無い EUC-JP のページ（実物がこれだった）
    t, enc = ref_youto.decode_html("位置参照情報 ダウンロードサービス".encode("euc-jp"),
                                   "text/html")
    eq(t, "位置参照情報 ダウンロードサービス", "宣言が無くても EUC-JP を読む")
    eq(enc, "euc-jp", "どれで読んだかを返す")

    # ② Content-Type にあるほうを先に使う
    t, enc = ref_youto.decode_html("ふつうのページ".encode("utf-8"),
                                   "text/html; charset=UTF-8")
    eq(t, "ふつうのページ", "UTF-8 のページはそのまま")

    # ③ zip の中の名前。zipfile が cp437 として読んだものを読み直す。
    #    左は 2026-09-19 の報告に実際に出ていた文字列
    eq(ref_youto._zname("âVâFü[âvâtâ@âCâïî`Ä«", 0), "シェープファイル形式",
       "zip の中の日本語の名前を読み直す")
    eq(ref_youto._zname("シェープファイル形式", 0x800), "シェープファイル形式",
       "UTF-8 の印が立っていれば触らない")
    eq(ref_youto._zname("A29-19_27140.shp", 0), "A29-19_27140.shp",
       "ASCII の名前は変わらない")


def test_zip_は_href_の外にもある():
    """2026-09-19。href だけを見ていたので「0本」だった。実物はこう：

        onclick="javascript:DownLd('3.77MB','A29-11_27_GML.zip',
                 '../data/A29/A29-11/A29-11_27_GML.zip' ,this);"

    「0本」は「無い」ではなく「その探し方では見えない」だった。
    """
    import re
    import ref_youto
    # 報告が持って帰った実物を、そのまま使う
    html = (
        '<td class="bgc6" id="prefecture27">大阪</td>'
        '<td class="txtCenter">A29-11_27_GML.zip</td>'
        '<a onclick="javascript:DownLd(\'3.77MB\',\'A29-11_27_GML.zip\','
        '\'../data/A29/A29-11/A29-11_27_GML.zip\' ,this);"></a>'
        '<a onclick="javascript:DownLd(\'4.10MB\',\'A29-19_27_GML.zip\','
        '\'../data/A29/A29-19/A29-19_27_GML.zip\' ,this);"></a>'
        '<a onclick="javascript:DownLd(\'1.00MB\',\'A29-11_26_GML.zip\','
        '\'../data/A29/A29-11/A29-11_26_GML.zip\' ,this);"></a>')
    pat = re.compile(r"A29[-_][^\"']*?_(\d{2})[_.][^\"']*\.zip", re.I)
    base = "https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-A29-v2_1.html"
    found = ref_youto.links(html, base, pat)

    if "27" not in found:
        raise AssertionError("onclick の中の zip を拾えていない（href だけ見ている）")
    eq(len(found["27"]), 2, "大阪府の候補は2本（A29-11 と A29-19）")
    eq(sorted(found["27"], key=ref_youto._ver)[-1],
       "https://nlftp.mlit.go.jp/ksj/gml/data/A29/A29-19/A29-19_27_GML.zip",
       "いちばん新しい年を選ぶ")
    # 対象の府県だけ。京都（26）は PREFS に無いので入らない
    eq("26" in found, False, "対象外の府県は入らない")

    # 数として比べる。文字として並べると A29-9 が A29-11 の後ろに来る
    v = sorted(["/A29-9/a_27.zip", "/A29-11/a_27.zip"], key=ref_youto._ver)
    eq(v[-1], "/A29-11/a_27.zip", "版の数字は数として比べる")


def test_報告は数ではなく実物を持って帰る():
    """3.4「届かない相手のことは、報告に実物を持って帰る」。

    1回目の ref_youto.py は「cgi が3本ありました」と**数だけ**書いて、
    URL を置いてきた。ページの実物は金庫にあるが、金庫はセッションから
    読めないので、次の一手が決められなかった（2026-09-19）。
    """
    import re
    import ref_youto
    html = (
        '<script src="/js/datalist.js"></script>'
        '<a href="/ksj/gml/cgi/downloadfile.cgi?id=A29-27">大阪府</a>'
        '<h3 id="prefecture27">大阪府</h3>'
        '<td data-file="A29-11_27_GML.zip">令和5年</td>'
        '<script>var b="/ksj/gml/cgi/downloadfile.cgi";</script>')
    pat = re.compile(r"A29[-_][^\"']*?_(\d{2})[_.][^\"']*\.zip", re.I)
    lines = ref_youto.evidence(html, pat)

    # **節ごとに見る。** 最初はまとめて `in` で見ていたが、cgi の URL が
    # 「印のまわり」の切り出しにも入っていたので、cgi の節を空にしても通った。
    # 別の道で通る検査は、鳴らない（9節「書いた検査が鳴らないのが、いちばんこわい」）
    sections, cur = {}, None
    for ln in lines:
        if ln.startswith("- **"):
            cur = ln
            sections[cur] = []
        elif cur:
            sections[cur].append(ln)

    def under(word, must):
        for head, body in sections.items():
            if word in head:
                if any(must in b for b in body):
                    return
                raise AssertionError(
                    f"報告の「{word}」の節に実物が無い： {must!r}。"
                    "数だけ持って帰ると、金庫を読めない側は次の一手を決められない")
        raise AssertionError(f"報告に「{word}」の節が無い")

    under(".cgi", "/ksj/gml/cgi/downloadfile.cgi?id=A29-27")   # cgi の URL そのもの
    under("script の src", "/js/datalist.js")                  # 組み立てている JS
    under("27 の印のまわり", 'id="prefecture27"')              # 印のまわりの実物
    under("ページ全体", "A29-11_27_GML.zip")                   # href の外にある zip


# ---------------------------------------------------------------- 4節 addr.py と 6節 index.json
def test_住所が別の市を名乗る行は0件のまま():
    """食い違いの数を、一度数えて終わりにしない。0でなくなった日に止まる。

    4節「「測った」は「そのときの一覧では」の意味しかない」。
    出どころは、ある日から別の市の土地を載せはじめる。
    """
    import json
    from common import addr
    path = os.path.join(HERE, "data", "all.json")
    if not os.path.exists(path):
        return
    bad = []
    with open(path, encoding="utf-8") as f:
        for r in json.load(f):
            try:
                addr.normalize(r.get("pref", ""), r.get("city", ""), r.get("address", ""))
            except ValueError as e:
                bad.append(str(e))
            except Exception:
                pass          # 読めないのは別の話（6節 unresolved）
    if bad:
        raise AssertionError(
            f"住所が呼ぶ側と別の市を名乗っている行が {len(bad)} 件。"
            f"市を被せずに、どう扱うか決めること（4節）：\n  " + "\n  ".join(bad[:5]))


def test_addr_normalize():
    """共通仕様4節のテスト値をそのまま通す。期待値は具体的に書く。"""
    from common import addr
    codes = {("大阪府", "大阪市北区"): "27127", ("兵庫県", "尼崎市"): "28202", ("兵庫県", "西宮市"): "28204",
             ("大阪府", "豊中市"): "27203", ("兵庫県", "三田市"): "28219", ("大阪府", "大阪市淀川区"): "27123",
             # 同じ都道府県の別の市。これが無いと「堺市…」の食い違いを見つけられない。
             # 見張りは、知っている名前しか見つけられない（jis-codes.json から引いた）
             ("大阪府", "堺市"): "27140"}
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
    # 2026-09-22 に西宮市の一覧（435件）を入れたので、ここは②で決まるようになった。
    # **地番の 3 を町丁目に含めない**という元の狙いはそのまま見ている
    eq(r["addr_key_town"], "28204|上ケ原2番町",
       "4節 3件目：一覧が在るので②で決まる。「上ケ原2番町3」にはしない")
    r = addr.normalize("大阪府", "大阪市北区", "大阪市北区梅田1-1-1 ○○ビル3F", codes)
    eq(r["addr_key"], "27127|梅田1-1-1", "建物名の数字を地番に混ぜない（6.）")
    r = addr.normalize("大阪府", "豊中市", "服部西町一丁目８４７番地の１ほか", codes)
    eq(r["addr_key"], "27203|服部西町1-847-1", "番地の「の」と全角数字と「ほか」")
    eq(r["addr_key_town"], "27203|服部西町1", "town は丁目まで")
    r = addr.normalize("大阪府", "大阪市淀川区", "十三本町1-2-3", codes)
    eq(r["addr_key"], "27123|十三本町1-2-3", "地名の漢数字（十三）を壊さない")
    # 呼ぶ側と違う市を住所が名乗っていたら、繋げずに止める（2026-09-19）
    for bad in ("兵庫県西宮市甲子園町1-1", "堺市西区鳳東町7-733"):
        try:
            got = addr.normalize("大阪府", "大阪市北区", bad, codes)
            raise AssertionError(
                f"別の市を名乗る住所を繋げてしまった： {bad} -> {got['addr']}")
        except ValueError:
            pass
    # 同じ市を名乗っているのは落とすだけ。止めない
    r = addr.normalize("大阪府", "大阪市北区", "大阪府大阪市北区梅田1-1-1", codes)
    eq(r["addr"], "大阪市北区梅田1-1-1", "自分の都道府県＋市は落とすだけ")
    eq(r["addr_key"], "27127|梅田1-1-1", "落としたあとのキー")

    # 丁目が無い住所で、**地番が町丁目に入っていないか**（2026-09-19）。
    # 印を1種類にして「最初の印まで」を町丁目にすると、847 が町丁目に入る。
    # 実データ4,809件のうち845件がそうなっていて、index.json に出ていた
    for text, want_key in (("服部西町847番地の1", "27203|服部西町847-1"),
                           ("本町847番地の1", "27203|本町847-1"),
                           ("日本橋2番地", "27203|日本橋2")):
        got = addr.normalize("大阪府", "豊中市", text, codes)
        eq(got["addr_key_town"], "", f"丁目が無ければ町丁目は空（{text}）")
        eq(got["addr_key"], want_key, f"地番までの鍵は作れる（{text}）")

    # 町名の途中の数字で切らないか（開発系が「そちらも測って」と言ってきた形）。
    # 「甲子園七番町」「北十二条西」は、数字のあとに町名が続く。
    # 向こうは _TOWN_AFTER_NUM で止めている。**こちらは単位として見ていない**ので
    # そもそも当たらない——**仕掛けが違うので、同じ穴が開かない**（2026-09-19、実測）
    for text, want in (("甲子園七番町1-2-3", "28204|甲子園7番町1-2-3"),
                       ("甲子園七番町1-2-3ハイツ101", "28204|甲子園7番町1-2-3"),
                       ("北十二条西5-1", "28204|北十二条西5-1"),
                       ("鳳東町七丁733", "28204|鳳東町7-733")):
        got = addr.normalize("兵庫県", "西宮市", text, codes)
        eq(got["addr_key"], want, f"町名の途中で切らない（{text}）")

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
        # **逆向きを誰も見ていなかった**（2026-09-20 の監査 r1-14）。
        # 上の行は「個人の名前が出ていないか」だけを見る。
        # **法人名を1件残らず落としても、それは通る。**
        # 横断のハブは party で引くので、落ちれば黙って引けなくなる（6節）
        if r.get("party_kind") == "corp" and not (r.get("party") or "").strip():
            bad["party_kind が corp なのに party が空"] += 1
        if r.get("party_kind") != "corp" and (r.get("party") or "").strip():
            bad["party_kind が corp でないのに party に値がある"] += 1
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
    # **4つの値が1つに寄ったら、判定そのものが外れている。**
    # 1件ずつ見る検査は、全件が同じ間違いをしていると1件も鳴らない
    iro = Counter(r.get("party_kind") for r in d.get("records", []))
    if len(d.get("records", [])) >= 100 and len(iro) < 2:
        fails.append(f"index.json: party_kind が {iro} の1種類しかない。"
                     "**判定が外れている**")

    # **1〜2件の升を、法人だけなら実数で出す**（3.2・2026-09-20）。
    # 3.2 が守っているのは人なので、人がいない升には守るものが無い。
    # ここは**見分けられる材料で見る**——個票から当事者の種類を数え直して、
    # 実数で出ている小さい升が**本当に法人だけか**を確かめる（9節）。
    # 升の値だけを見ると「1が出ている」しか分からず、正しいのか見分けられない
    from collections import defaultdict
    masu_tousha = defaultdict(set)
    for r in d.get("records", []):
        if r.get("city_code") and r.get("date"):
            masu_tousha[(r["city_code"], r["kind"], r["date"][:4])].add(
                r.get("party_kind") or "individual")
    for c in d.get("counts_by_city", []):
        n, lab = c.get("count"), c.get("count_label")
        if n is None and lab != "1-2":
            bad["count が null なのに label が 1-2 でない"] += 1
        if isinstance(n, int) and str(n) != lab:
            bad["count と label が食い違う"] += 1
        if isinstance(n, int) and 1 <= n <= 2:
            # 個票の kind は `<制度>/<種別>`。升の kind も同じ形
            k = (c.get("city_code"), c.get("kind"), c.get("period"))
            shurui = masu_tousha.get(k)
            if not shurui:
                bad["小さい升が実数だが、突き合わせる個票が無い"] += 1
            elif shurui - {"corp", "none"}:
                bad["**人が混ざる升が実数のまま**"] += 1
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
    """表の rowspan / colspan を展開して、列の位置がずれないこと（parse.py）。"""
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
    """8節：訂正履歴のページがあり about から辿れる。「やらないと決めたこと」が about にある。"""
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
            # カードの門（common/kado.py）は**通す偽物**に差し替える（架空の
            # 置き場には torimoto-card.json が無い）。ここで見たいのは
            # 混雑（429）で止まるかどうかで、門そのものの挙動は別に確かめてある
            with contextlib.redirect_stdout(_io.StringIO()), toosu_kado_mon(recon):
                recon.main()
        finally:
            recon.HERE, recon.fetch, recon.check_robots, recon.follow_links, time.sleep = keep

    # 入口1本 ＋ 辿った先の1本目で 429 → そこで終わる
    eq(len(got), 2, f"混んでいると言われたのに押し込んでいる（{len(got)}回 要求した。2回で止まるはず）")


def test_every_fetcher_stops_when_busy():
    """3.4：取りに行くスクリプトは全部、429/503 でその回を中止すること。

    recon.py だけ is_busy を見ていなかった。1本忘れると、そこだけ押し込む。
    """
    # **名前で並べない**（2026-09-19）。同じ日に足した chizu_recon.py が
    # 一覧に入っていなかった。足した日に黙る形だった
    michi_ra = soto_ni_deru()
    if not michi_ra:
        raise AssertionError("外に出る .py が1つも見つからない。拾い方が壊れている")
    for michi in michi_ra:
        name = os.path.relpath(michi, HERE)
        src = open(michi, encoding="utf-8").read()
        # **`is_busy` を定義している側は、止める側ではない。**
        # 道具（common/fetch.py）と、道具を使う側を分ける。
        # **名前で外さない。** 「定義しているか」で外す
        if re.search(r"^def is_busy\(", src, re.M):
            continue
        # **門（common/kado.py）自身も、道具を使う側ではない。**
        # 429/503 は `is_busy`／`Konde` の慣用句ではなく、`KONDA` と
        # `_tomeru()`（相手ごとに止める）で持っている。tests/test_kado.py の
        # robotsの応答 クラス（test_429_503は混んでいる_その相手は止まる 等）で
        # 別に確かめてある。**名前では外さない。** `hajimeru()` を定義している
        # （＝門そのものである）かどうかで外す
        if re.search(r"^def hajimeru\(", src, re.M):
            continue
        # **止め方は2通りある。どちらも「その回を中止する」形。**
        #
        #   ① 自分で `is_busy(e)` を見て、その場で止める
        #   ② 取りに行く関数を借りて、**`except Konde` で止める**
        #
        # ②は `Konde` の説明にそのまま書いてある形——
        # 「呼ぶ側が `except Konde: raise` を1行足すだけで止まる」。
        # **`Konde` は 429/503 のときだけ上がる型**なので、
        # これを捕まえて止めるのは①と同じことをしている。
        #
        # 2026-09-21 に足した。それまで①しか見ておらず、
        # **取りに行く関数を1か所に置いた段が、止めているのに落ちた。**
        # ただし**「import しているか」では外さない。** 捕まえて
        # **止めているか**まで見る（捕まえて次へ進む形を通さないため）。
        jibun = "is_busy" in src
        karite = bool(re.search(
            r"except Konde(?:\s+as\s+\w+)?:(?:[^\n]*\n){1,8}?[ \t]*"
            r"(break|raise|return|continue)", src))
        eq(jibun or karite, True,
           f"{name} が 429/503 を見ていない（共通仕様3.4）")
        if not jibun:
            continue                      # ②の形。**止めているところまで確かめ済み**
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
    # ここは 2026-09-19 まで True を期待していた。正本違反のほうを固定していた。
    # 0件は、人口がいくら小さくても率を出す。率を伏せるのは「率×人口」で件数が
    # 戻るからで、0件には戻る先が無い。人口の小ささも同じ理由で効かない
    eq(privacy.suppress_rate(0, 400), False, "0件は人口が小さくても率を出す")
    eq(privacy.suppress_rate(0, 1), False, "人口1人でも、0件なら率を出す")
    # ここは 2026-09-19 に統括が False で書いた。**間違いだった。**
    # 人口0は伏せるのではなく、率そのものが定義できない（0では割れない）。
    # False にすると呼ぶ側が 0/0 でゼロ除算する。街頭窃盗統計が実際に踏んだ
    eq(privacy.suppress_rate(0, 0), True, "人口0は0件でも率を出さない（0では割れない）")
    eq(privacy.suppress_rate(0, -1), True, "人口が負でも率を出さない")
    eq(privacy.suppress_rate(1, 400), True, "1件で人口も小さいなら伏せる")
    eq(privacy.suppress_rate(9, 400), True, "0件でなければ人口の小ささが効く")

    # 条件が2つあるので、交差を全部当てる（9節）。片方ずつ当てると、
    # 不具合のある升（0件かつ小人口／0件かつ人口0）を一度も踏まない
    grid = {
        #  件数     人口0   人口400（小）  人口5000（十分）
        (0,    0): True,  (0,   400): False, (0,   5000): False,
        (1,    0): True,  (1,   400): True,  (1,   5000): True,
        (2,    0): True,  (2,   400): True,  (2,   5000): True,
        (3,    0): True,  (3,   400): True,  (3,   5000): False,
    }
    for (c, pop), want in grid.items():
        eq(privacy.suppress_rate(c, pop), want, f"交差 件数{c}×人口{pop}")


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
    for path in subete_no_py():
        name = os.path.basename(path)
        if name == "privacy.py":
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
    # 丸め忘れをここでも見る（5節「privacy.py を迂回した出力が1件でもあれば落ちる検査を書く」）
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
        # **「ほか◯者」は書き方の違いではない。** 共有者が付いた／消えたか、
        # 書き落としたか。どちらも中身の話なので、同じと言ってはいけない
        ("鯨屋都市開発株式会社", "鯨屋都市開発株式会社ほか６者"),
        ("㈱海猫百貨店　ほか", "㈱海猫百貨店"),
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
    targets = [f for f in subete_no_py()
               if os.path.basename(f) != "runday.py"]
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


def test_zoning_handles_wrapped_cell_text():
    """表のセルの中の改行を、区切りと取り違えていないか。

    用途地域の欄は、1店が複数の地域にまたがると複数入る。区切りは読点だが、
    **表のセルの中では改行でも区切られ、同じ改行が語の途中にも入る**（折り返し）。

        商業\n第一種住居              改行が区切り
        第二種中高層\n住居専用地域     改行が折り返し（1つの語）

    見分けられないので、くっつけたほうを先に試す（最長一致）。
    「第二種中高層」は単体でも解けるので、先に取ると「住居専用地域」が余る。
    4節の町丁目の最長一致と同じ理由。
    """
    sys.path.insert(0, os.path.join(HERE, "common"))
    import zoning as zoninglib

    cases = [
        # 折り返し（1つの語）
        ("第一種住居、\n第二種中高層\n住居専用地域",
         ["第一種住居地域", "第二種中高層住居専用地域"]),
        # 区切り（2つの語）
        ("商業\n第一種住居", ["商業地域", "第一種住居地域"]),
        ("商業地域\n準工業地域", ["商業地域", "準工業地域"]),
        ("準住居\n第一種住居", ["準住居地域", "第一種住居地域"]),
        # 読点
        ("準工業地域、第一種住居地域", ["準工業地域", "第一種住居地域"]),
        # 1つだけ
        ("準工業", ["準工業地域"]),
    ]
    for raw, want in cases:
        got, unknown = zoninglib.normalize(raw)
        if got != want or unknown:
            fails.append(f"用途地域の読み取りが違う（{raw!r} → {got} 余り{unknown}・期待 {want}）")


def test_every_python_file_parses():
    """このリポジトリの .py が、全部ちゃんと読めるか。

    検査は `*.py` を**文字として**走査しているが、**構文が通るかは見ていなかった。**
    2026-09-19、マージの衝突マーカーが入ったまま `git add -A` でコミットされ、
    `build_site.py` が `SyntaxError` になったのに、47本の検査は全部通った。
    **読んでいるのに、読めているかを見ていなかった。**

    衝突マーカー（`<<<<<<<`）も、ここで落ちる。
    """
    import ast
    bad = []
    # **検査そのものも読めなければ困る**ので、ここだけは test_ も入れる
    for f in subete_no_py(nozoku=()):
        try:
            with open(f, encoding="utf-8") as fh:
                ast.parse(fh.read(), filename=f)
        except SyntaxError as e:
            bad.append(f"{os.path.basename(f)}:{e.lineno} {e.msg}")
        except Exception as e:
            bad.append(f"{os.path.basename(f)} {type(e).__name__}")
    if bad:
        fails.append(f"読めない .py が {len(bad)}本（{bad[:3]}）")

    # マージの衝突マーカーは、.py 以外にも残る
    marks = []
    for f in (glob.glob(os.path.join(HERE, "*.md"))
              + glob.glob(os.path.join(HERE, "docs", "*.md"))
              + workflow_files()):
        with open(f, encoding="utf-8", errors="ignore") as fh:
            t = fh.read()
        if "\n<<<<<<< " in t or "\n>>>>>>> " in t:
            marks.append(os.path.basename(f))
    if marks:
        fails.append(f"マージの衝突マーカーが残っている {marks}")


def test_法人格の落とし方が正本の外に書かれていないか():
    """**同じ知識が2か所にあると、片方に足した日に、もう片方が黙る。**

    2026-09-20、`hako_rireki.py` が施設名を寄せるのに
    法人格の一覧を**自分でもう1本**持っていた。`privacy.corp_core` が正本。
    「合名会社」を足す日に、片方だけ足して黙る形だった。

    **この検査は、最初に書いたとき穴が開いていた。**
    `re.sub(r"(株式会社|…)")` という**その場で書く形**しか見ておらず、

        _HOUJIN = re.compile(r"(株式会社|…)")   ← 定数にしてから
        s = _HOUJIN.sub("", s)                    ← 別の行で使う

    という**実際にそこに在った形**を1件も捕まえなかった。
    **文字で探すと、書き方を変えられた分だけ漏れる。** なので構文木で見る。

    見るのは「**法人格の語が入った文字列が、正規表現か置換に渡っているか**」。
    docstring やコメントで語に触れるだけなら鳴らない。

    **捕まえないもの**：法人格の語を**判定に使う**こと（`is_corp` の中など）。
    落とす（消す）形だけを見る。
    """
    import ast as _ast
    GO = ("株式会社", "有限会社", "合同会社", "合名会社", "合資会社", "㈱", "㈲")
    WATASU = {"compile", "sub", "subn", "replace", "split", "findall", "match",
              "search", "fullmatch"}

    def houjin_moji(node):
        return (isinstance(node, _ast.Constant) and isinstance(node.value, str)
                and any(g in node.value for g in GO))

    OTOSU = {"sub", "subn", "replace"}   # **落とす**
    warui = []
    for f in subete_no_py():
        base = os.path.basename(f)
        if base == "privacy.py":
            continue  # **ここが正本**
        try:
            ki = _ast.parse(open(f, encoding="utf-8").read())
        except SyntaxError:
            continue  # 構文は別の検査が見る

        # ① その場で落としている形
        # ② 定数にしてから、別の行で `.sub(` している形（**最初これを見落とした**）
        tsukau = {n.func.attr: n.func.value.id
                  for n in _ast.walk(ki)
                  if isinstance(n, _ast.Call)
                  and isinstance(n.func, _ast.Attribute)
                  and isinstance(n.func.value, _ast.Name)
                  and n.func.attr in OTOSU}
        otosu_na = set(tsukau.values())

        for node in _ast.walk(ki):
            if isinstance(node, _ast.Assign) and any(houjin_moji(a)
                    for n2 in _ast.walk(node) if isinstance(n2, _ast.Call)
                    for a in n2.args):
                # 定数に入れた法人格の並び。**落とすのに使われていたら鳴る**
                mei = {t.id for t in node.targets if isinstance(t, _ast.Name)}
                if mei & otosu_na:
                    warui.append(f"{base}:{node.lineno}")
                continue
            if not isinstance(node, _ast.Call):
                continue
            na = node.func.attr if isinstance(node.func, _ast.Attribute) else (
                node.func.id if isinstance(node.func, _ast.Name) else "")
            if na not in OTOSU:
                continue  # **判定（compile/search）は捕まえない**
            if any(houjin_moji(a) for a in node.args):
                warui.append(f"{base}:{node.lineno}")
    if warui:
        raise AssertionError(
            f"法人格を自分で落としている: {sorted(set(warui))}。"
            "**`privacy.corp_core` を通すこと**（同じ知識を2か所に置かない）")


def test_公開していないと名乗るものが公開される場所に出ていないか():
    """**`data/` に置くと、リポジトリに入る＝URLで読める。**

    2026-09-20、`hako_rireki.py` の報告を `data/ref/` に書いて
    「まだ公開していない」と名乗るところだった。**名乗りが嘘になる**（ルール⑥）。

    site はリポジトリの根から配られるので、`data/ref/*.json` も
    **そのまま URL になる。** 「リポジトリに入れた」と「公開した」は同じこと。

    公開しないと名乗るなら、**`.gitignore` の下に出す。**

    **読む側と書く側を分ける。** 最初に書いたときは分けていなくて、
    `data/all.json` を**読んでいる**だけで鳴った（誤報）。
    **鳴ることを確かめたら、鳴りすぎることも確かめる。**

    **捕まえないもの**：`.gitignore` の下に出しているものの中身。
    そちらは workflow の見張り（生データが混ざったら止まる）が見る。
    """
    import re as _re
    mushi = set()
    gi = os.path.join(HERE, ".gitignore")
    if os.path.exists(gi):
        for gyou in open(gi, encoding="utf-8"):
            gyou = gyou.split("#")[0].strip().strip("/")
            if gyou and "*" not in gyou:
                mushi.add(gyou)
    if not mushi:
        raise AssertionError(".gitignore が読めない。見張りが黙っている")

    nanori = _re.compile(r"(公開していない|まだ公開し|公開側には出さない)")
    # `NAME = HERE / "top" / ...` → NAME がどの置き場を指すか
    daiin = _re.compile(r'^\s*([A-Z_][A-Z0-9_]*)\s*=\s*HERE\s*/\s*"([^"]+)"', _re.M)
    warui = []
    for f in subete_no_py():
        honbun = open(f, encoding="utf-8").read()
        if not nanori.search(honbun):
            continue
        basho = dict(daiin.findall(honbun))
        for na, ue in basho.items():
            if ue in mushi:
                continue
            # **書いているところだけ見る。** 読んでいるだけなら関係ない
            kaku = _re.compile(
                rf'({na}\s*\.\s*(write_text|write_bytes|mkdir|open)\b'
                rf'|open\s*\(\s*{na}\s*,\s*["\']w)')
            if kaku.search(honbun):
                warui.append(f"{os.path.basename(f)}: {na} → {ue}/")
    if warui:
        raise AssertionError(
            f"「公開していない」と名乗りながら、公開される場所に書いている: {warui}。"
            "**リポジトリに入れた時点で URL になる**")


def test_箱の履歴が箱と中身を混ぜていないか():
    """**寄せの向きが、欄によって逆になる。**

    2026-09-20 に実測した。

        施設名を寄せない    → 同じ施設が別扱い → **出来事が減る**（下限）
        事業者名を寄せない  → 書き方の違いが出来事 → **出来事が増える**（上限）

    混ぜて1つの数字にすると、**両方向に間違えた数字**になる。
    実際、寄せる前は設置者の出来事が440件で、正本の見比べを通したら338件だった。

    ここが見るのは、**出来事に「箱」か「中身」かの札が付いているか**と、
    **中身の札が付いたものに注意書きが付いているか**。
    """
    import importlib.util as _iu
    f = os.path.join(HERE, "hako_rireki.py")
    if not os.path.exists(f):
        return  # まだ無い日は黙ってよい（**足した日に鳴る側**ではない）
    spec = _iu.spec_from_file_location("hako_rireki", f)
    mod = _iu.module_from_spec(spec)
    spec.loader.exec_module(mod)

    recs = [
        {"store": "テスト施設", "notified_on": "2020-01-01",
         "parking": 100, "retailer_display": "架空商事株式会社"},
        {"store": "テスト施設", "notified_on": "2021-01-01",
         "parking": 80, "retailer_display": "架空商事㈱"},
        {"store": "テスト施設", "notified_on": "2022-01-01",
         "parking": 80, "retailer_display": "別の架空株式会社"},
    ]
    ev = mod.dekigoto(recs)
    fuda = {e["kind"] for e in ev}
    if not fuda <= {"箱", "中身", "廃止"}:
        raise AssertionError(f"知らない札が付いている: {fuda - {'箱', '中身', '廃止'}}")

    hako = [e for e in ev if e["kind"] == "箱"]
    naka = [e for e in ev if e["kind"] == "中身"]
    eq(len(hako), 1, "駐車場が1回変わったのに、箱の出来事の数が合わない")
    # **書き方だけの違い（架空商事株式会社 → 架空商事㈱）は出来事にしない**
    eq(len(naka), 1, "書き方だけの違いを出来事に数えている（正本の見比べを通していない）")
    for e in naka:
        if not e.get("note"):
            raise AssertionError(
                "中身の出来事に注意書きが無い。**「変わった」とは言えない**"
                "（商号変更・合併は見分けられない）")


def test_全角と半角で書かれた同じ店が同じ鍵になるか():
    """**同じ届出が2件のまま数えられていた（26件）。**

    2026-09-20。`merge.py` の店名の寄せ方に NFKC が無く、

        ｍｅｇａドンキホーテ   ←  別の店として残る
        megaドンキホーテ

    が別々に数えられていた。`(株)◯◯` も、括弧だけ先に落ちて `株◯◯` になっていた。

    **1件ずつ見る検査では鳴らない形**（9節）。どの1件も、それ自体は正しい。
    **2件そろって初めて、同じものだと分かる。**

    ここが見るのは**寄せ方そのもの**。鍵が同じになるかだけを見て、
    実データの件数は見ない（**件数は毎日変わる**ので、見張りにならない）。
    """
    import importlib.util as _iu
    f = os.path.join(HERE, "merge.py")
    spec = _iu.spec_from_file_location("merge_for_test", f)
    mod = _iu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    n = mod.norm_store

    kumi = [
        ("ｍｅｇａドンキホーテ", "megaドンキホーテ", "全角と半角の英字"),
        ("ｃｏｒｏｗａ甲子園", "corowa甲子園", "全角の英字だけの店名"),
        ("ＡＢＣ１番館", "ABC1番館", "全角の数字"),
        ("株式会社架空", "(株)架空", "法人格の書き方"),
        ("㈱架空", "株式会社架空", "丸囲みの法人格"),
        ("（仮称）架空モール", "架空モール", "仮称が付いているか"),
    ]
    for a, b, naze in kumi:
        if n(a) != n(b):
            raise AssertionError(
                f"同じ店が別の鍵になる（{naze}）: {a!r}→{n(a)!r} / {b!r}→{n(b)!r}。"
                "**同じ届出が2件のまま数えられる**")

    # **寄せすぎても困る。** 別の店が同じ鍵になったら、1件に潰れる
    betsu = [("架空モール北館", "架空モール南館"), ("架空ストア1号店", "架空ストア2号店")]
    for a, b in betsu:
        if n(a) == n(b):
            raise AssertionError(
                f"別の店が同じ鍵になる: {a!r} / {b!r} → {n(a)!r}。**1件に潰れる**")


def test_種が無い段が黙って0本にならないか():
    """**「0件」は、その道を1回も通っていないときにも出る**（9節）。

    2026-09-21、停電の段を足した。種（公的な一覧のURL）は**人が入れる**形にした——
    全国の会社のドメインを思い出して並べると、外れたとき
    **関係のない誰かのサーバーを叩く**（3.4）。

    危ないのは、**種が無いときに「0件でした」と言って緑で終わる**形。
    何も探していないのに、探して無かったように見える。

    ここが見るのは、**種を渡さずに呼んだら、0 以外を返すか**。
    ネットには出ない（種が無いので、出る前に止まる）。
    """
    import importlib.util as _iu
    f = os.path.join(HERE, "teiden_recon.py")
    if not os.path.exists(f):
        return
    spec = _iu.spec_from_file_location("teiden_recon", f)
    mod = _iu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    modoshi = mod.main([])
    if modoshi == 0:
        raise AssertionError(
            "種が無いのに 0 を返した。**探していないのに、探して無かったように見える**")


def test_速報と記録の語を分けているか():
    """**語が似ているものを混ぜない**（3.5）。

    2026-09-20、遅延で踏んだ。「遅延情報」は**いまの運行**、
    「遅延証明書」は**過去の記録**で、別物だった。

    停電も同じ形。「停電情報」は**いま停電しているか**で、他がやっている。
    こちらが欲しいのは「停電履歴」＝**過去の記録**。

    ここが見るのは、**2つの語の一覧が重なっていないか**。
    重なっていると、**速報を記録として拾う。**
    """
    import importlib.util as _iu
    f = os.path.join(HERE, "teiden_recon.py")
    if not os.path.exists(f):
        return
    spec = _iu.spec_from_file_location("teiden_recon2", f)
    mod = _iu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    kasanari = set(mod.KIROKU_GO) & set(mod.SOKUHO_GO)
    if kasanari:
        raise AssertionError(f"記録と速報で同じ語を使っている: {kasanari}")
    # 片方が他方の一部になっていても、先に当たったほうに倒れる
    for k in mod.KIROKU_GO:
        for sk in mod.SOKUHO_GO:
            if k in sk or sk in k:
                raise AssertionError(
                    f"語が入れ子になっている: 記録{k!r} と 速報{sk!r}。"
                    "**どちらに倒れるかが、並び順で決まってしまう**")


def test_robotsを確かめられなかったときに許可と言わないか():
    """**関所の名前が「確かめた」なのに、確かめていなかった。**

    2026-09-21。この箱から `enecho.meti.go.jp` に出ようとして、
    proxy が 403 を返した。**robots.txt を1バイトも読んでいない。**
    それなのに `check_robots` は **「よい」**を返した（ルール⑥）。

    そのまま本番で起きたら、**robots を見ないで取りに行くことになる**（3.4）。

    **「無い」と「読めなかった」を分ける。**

        404 / 410    **本当に無い。** これは答え。許可
        429 / 503    混んでいる                → 行かない
        401 / 403    相手が robots.txt を拒んだ → 行かない
        5xx          相手が壊れている           → 行かない
        つながらない  **こちらが出られていない**  → 行かない

    2026-09-25、robots.txt を取って判定する中身は `common/kado.py` の門へ
    引っ越した。**`urlopen` を差し替える代わりに、門の中の偽の相手（Nise）に
    答えさせる**——tests/test_kado.py の Nise・Oki と同じ形（本番のコードには
    「検査のときは通す」道を作らない。偽物は検査の中だけに置く）。
    ネットには出ない。**返り値だけ**を見る。
    """
    import email.message
    import io
    import json
    import os as _os
    import shutil
    import tempfile
    import urllib.error as _ue
    import urllib.request as _ur
    import urllib.response as _ures
    from common import fetch as _f, kado as _kado

    HOST = "kujiraya-kado-test.example.invalid"
    URL = f"https://{HOST}/a"

    class _Nise(_ur.BaseHandler):
        """偽の相手。tests/test_kado.py の Nise と同じ形。ネットには出ない。"""
        handler_order = 50

        def __init__(self, kotae):
            self.kotae = kotae

        def _open(self, req):
            if isinstance(self.kotae, Exception):
                raise self.kotae
            status, body = self.kotae
            msg = email.message.Message()
            msg["Content-Type"] = "text/plain"
            r = _ures.addinfourl(io.BytesIO(body.encode("utf-8")), msg, req.full_url, status)
            r.msg = "nise"
            return r
        https_open = _open
        http_open = _open

    def shirabe(kotae):
        """カードの門の「セッションの中」を、カードや承認は使わずに作って確かめる。

        `robots_kekka()` が見るのは `self._genzai`（いまのセッション）と
        相手台帳だけ。カードの門そのもの（`card_mon`）は試していないので、
        tests/test_kado.py の Oki が作る承認・git の履歴までは要らない。
        """
        root = tempfile.mkdtemp()
        try:
            _os.makedirs(_os.path.join(root, "data", "ref"))
            daicho = {"aite": {"ためし相手": {"host": [HOST], "担当": "ogataten-nippo"}}}
            with open(_os.path.join(root, "data", "ref", "aite-daicho.json"),
                     "w", encoding="utf-8") as f:
                json.dump(daicho, f, ensure_ascii=False)
            k = _kado.Kado(root, "ogataten-nippo", _f.UA, env={},
                           transport=_Nise(kotae), sleep=lambda s: None)
            k._genzai = ("tameshi", {"相手": "ためし相手"}, _kado.KOUI_TORU)
            moto = _kado._KADO
            _kado._KADO = k
            try:
                return _f.check_robots(URL)
            finally:
                _kado._KADO = moto
        finally:
            shutil.rmtree(root, ignore_errors=True)

    # ① 本当に無い（404）→ 許可。**これは答え**
    ok, _ = shirabe((404, ""))
    eq(ok, True, "robots.txt が無い（404）のに、許可にしていない")

    # ② 混んでいる → 行かない
    ok, _ = shirabe((503, ""))
    eq(ok, None, "robots.txt が 503 なのに、行く側に倒している")

    # ③ 相手が拒んだ → 行かない
    ok, naze = shirabe((403, ""))
    eq(ok, None, f"robots.txt が 403 なのに許可と言った（{naze}）")

    # ④ 相手が壊れている → 行かない
    ok, naze = shirabe((500, ""))
    eq(ok, None, f"robots.txt が 500 なのに許可と言った（{naze}）")

    # ⑤ **こちらが外に出られない** → 行かない（2026-09-21 に実際に起きた）
    ok, naze = shirabe(_ue.URLError("Tunnel connection failed: 403 Forbidden"))
    eq(ok, None, f"robots.txt に届いていないのに許可と言った（{naze}）")

    # ⑥ 読めて、拒否と書いてある → 行かない
    ok, _ = shirabe((200, "User-agent: *\nDisallow: /\n"))
    eq(ok, False, "robots.txt が拒否しているのに、行く側に倒している")

    # ⑦ 読めて、許可と書いてある → 行く
    ok, _ = shirabe((200, "User-agent: *\nAllow: /\n"))
    eq(ok, True, "robots.txt が許可しているのに、行かない側に倒している")


def test_人が指したURLをドメインに丸めていないか():
    """**人が「ここ」と指したURLは、そのまま使う。**

    2026-09-21。10社ぶんのURLを渡されたが、段が**ドメインだけに丸めて**いた。

        hepco.co.jp/network/index.html  →  hepco.co.jp/
        tepco.co.jp/pg/                 →  tepco.co.jp/

    **送配電会社の部屋ではなく、親会社の玄関**を開くことになる。
    **10社のうち6社がそうなるところだった。**

    種のページから**拾う**ときは丸めてよい（同じ会社のリンクが何本も出るので）。
    **人が渡したときは丸めない。** 拾うのと渡されるのは、別の道。
    """
    import importlib.util as _iu
    f = os.path.join(HERE, "teiden_recon.py")
    if not os.path.exists(f):
        return
    spec = _iu.spec_from_file_location("teiden_recon3", f)
    mod = _iu.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # **ネットにも出ないし、本番の記録も汚さない。**
    # 開く手前で止めて、置き場は使い捨てに差し替える
    import tempfile
    from pathlib import Path as _P
    hiraita = []
    moto, nemuru = mod.hitotsu, mod.time.sleep
    moto_inbox, moto_kiroku = mod.INBOX, mod.KIROKU
    mod.hitotsu = lambda top, hiduke: (hiraita.append(top) or {
        "top": top, "robots": True, "status": 200, "kiroku": [], "sokuho": [],
        "naze": ""})
    mod.time.sleep = lambda *_a: None
    with tempfile.TemporaryDirectory() as tmp:
        mod.INBOX = _P(tmp) / "inbox"
        mod.KIROKU = _P(tmp) / "teiden-recon.md"
        try:
            mod.main(["--tops",
                      "https://例.example/nw/index.html,https://例2.example/pg/",
                      "--limit", "2"])
        finally:
            mod.hitotsu, mod.time.sleep = moto, nemuru
            mod.INBOX, mod.KIROKU = moto_inbox, moto_kiroku

    for u in hiraita:
        if u.count("/") <= 3:
            raise AssertionError(
                f"人が渡したURLをドメインに丸めている: {u}。"
                "**指された部屋ではなく、親会社の玄関を開くことになる**")


def test_種類の数え方が一部にしかない欄に頼っていないか():
    """**欄が一部にしか無いと、数が小さく出る。**

    2026-09-21。廃止の届出を `kubun_raw` で数えていた。
    その欄は**一部の届出にしか無く、194件のうち49件しか当たらなかった。**
    **4分の1しか見ていないのに、それが全部だと思っていた。**

    `kind` は**全件に入っている**ので、そちらで数える。

    ここが見るのは、**片方が他方より少なくならないか**。
    実データの件数そのものは見ない（**毎日変わる**ので見張りにならない）。
    """
    import json as _json
    f = os.path.join(HERE, "data", "all.json")
    if not os.path.exists(f):
        return
    recs = _json.load(open(f, encoding="utf-8"))
    kind_de = sum(1 for r in recs if (r.get("kind") or "") == "廃止")
    kubun_de = sum(1 for r in recs if (r.get("kubun_raw") or "") == "廃止")
    if kind_de and kubun_de >= kind_de:
        return  # 欄が埋まるようになったなら、それでよい
    if kind_de > kubun_de:
        # **ここは正常。** 使う側が `kind` を見ているかを確かめる
        h = os.path.join(HERE, "hako_rireki.py")
        if os.path.exists(h):
            honbun = open(h, encoding="utf-8").read()
            if 'r.get("kubun_raw") or ""' in honbun and "== \"廃止\"" in honbun:
                raise AssertionError(
                    "廃止を `kubun_raw` で数えている。**その欄は一部にしか無い**。"
                    f"`kind` なら {kind_de} 件、`kubun_raw` なら {kubun_de} 件")


def test_停電の段が3段目を作っていないか():
    """**辿るほど、当たっているか誰も確かめられなくなる。**

    2026-09-21。トップだけ見る段に、1段もぐる道を足した。
    **2段で止める。** 3段目を作ると、

        トップ → 速報 → ？ → ？

    のどこで道を間違えたかが分からなくなる。**間違えた先は、他人のサーバー。**

    あわせて2つ見る。

        **記録が既に見つかっている社は、もぐらない**（もう用が足りている）
        **速報が0本の社も、もぐらない**（辿る先が無い）

    ネットには出ない。**もぐる関数を、辞書を渡して呼ぶだけ。**
    """
    import importlib.util as _iu
    f = os.path.join(HERE, "teiden_recon.py")
    if not os.path.exists(f):
        return
    spec = _iu.spec_from_file_location("teiden_recon4", f)
    mod = _iu.module_from_spec(spec)
    spec.loader.exec_module(mod)

    if not hasattr(mod, "moguru"):
        raise AssertionError("もぐる段が無い")

    # **3段目が無いこと**：もぐった先の結果に、さらにもぐった跡が無い
    honbun = open(f, encoding="utf-8").read()
    if honbun.count("moguru(") > 3:
        raise AssertionError(
            "もぐる段を呼んでいる所が多い。**3段目を作っていないか**")

    yonda = []
    moto_get, moto_robots = mod.get, mod.check_robots
    mod.get = lambda u: yonda.append(u) or (200, "text/html", b"<html></html>")
    mod.check_robots = lambda u: (True, "許可")
    nemuru = mod.time.sleep
    mod.time.sleep = lambda *_a: None
    try:
        # ① 記録が見つかっている社 → **もぐらない**
        d = mod.moguru({"kiroku": [{"url": "https://例.example/a", "moji": ""}],
                        "sokuho": [{"url": "https://例.example/b", "moji": ""}]},
                       "2026-01-01", 3)
        if yonda:
            raise AssertionError("記録が見つかっているのに、もぐっている")
        eq(d.get("mogutta"), [], "もぐっていないのに、もぐった跡がある")

        # ② 速報が0本の社 → **もぐらない**
        yonda.clear()
        mod.moguru({"kiroku": [], "sokuho": []}, "2026-01-01", 3)
        if yonda:
            raise AssertionError("辿る先が無いのに、取りに行っている")

        # ③ もぐる本数が、渡した数を超えない
        yonda.clear()
        mod.moguru({"kiroku": [],
                    "sokuho": [{"url": f"https://例.example/{i}", "moji": ""}
                               for i in range(9)]}, "2026-01-01", 2)
        if len(yonda) > 2:
            raise AssertionError(f"2本と言ったのに {len(yonda)} 本もぐった")
    finally:
        mod.get, mod.check_robots, mod.time.sleep = moto_get, moto_robots, nemuru


def test_停電の段が同じ相手に1日2回行かないか():
    """**相手の数で数える。手順書の本数ではない**（3.4）。

    1段目は押すだけ、2段目（毎日ためる段）は毎日走る。
    **同じ日に両方走ると、同じ相手に1日2回行く。**

    1段目の記録には走った日が書いてあるので、**そこを見て止まる。**
    **別に台帳を作らない**——同じ事実を2か所に置くと、片方が古くなる。

    あわせて、**黙って飛ばさない**ことも見る（9節）。0 を返して緑で終わらない。

    ネットには出ない。**記録の文字を差し替えて、返り値だけ見る。**
    """
    import importlib.util as _iu
    import tempfile
    from pathlib import Path as _P
    f = os.path.join(HERE, "teiden_get.py")
    if not os.path.exists(f):
        return
    spec = _iu.spec_from_file_location("teiden_get", f)
    mod = _iu.module_from_spec(spec)
    spec.loader.exec_module(mod)

    with tempfile.TemporaryDirectory() as tmp:
        recon = _P(tmp) / "teiden-recon.md"
        moto_recon, moto_today = mod.RECON, mod.today
        mod.RECON = recon
        mod.DAICHO = _P(tmp) / "ledger.json"
        mod.KIROKU = _P(tmp) / "get.md"
        mod.INBOX = _P(tmp) / "inbox"
        try:
            # ① 1段目が**今日**走っている → **止まる**
            recon.write_text(
                "**2026-09-21** に `teiden_recon.py` が走った。\n"
                "記録らしいリンク  1 本\n"
                "      - 例  https://例.example/a\n", encoding="utf-8")
            mod.today = lambda: "2026-09-21"
            modoshi = mod.main([])
            if modoshi == 0:
                raise AssertionError(
                    "1段目が同じ日に走っているのに、止まらなかった。"
                    "**同じ相手に1日2回行く**")

            # ② 1段目が**別の日**なら、止まらない（robots で行かないだけ）
            mod.today = lambda: "2026-09-22"
            moto_robots = mod.check_robots
            mod.check_robots = lambda u: (None, "確かめられなかった")
            nemuru = mod.time.sleep
            mod.time.sleep = lambda *_a: None
            try:
                modoshi2 = mod.main([])
            finally:
                mod.check_robots, mod.time.sleep = moto_robots, nemuru
            eq(modoshi2, 0, "別の日なのに止まっている")
        finally:
            mod.RECON, mod.today = moto_recon, moto_today


def test_指紋を長さで代用していないか():
    """**同じ長さで中身が変わることがある。**

    「差し替わった」を見つけるのに、バイト数だけ見ると**取りこぼす。**
    数字の訂正（500→700）は、**長さが変わらないことがある。**

    ネットには出ない。**指紋の関数に、同じ長さの別の中身を渡すだけ。**
    """
    import importlib.util as _iu
    f = os.path.join(HERE, "teiden_get.py")
    if not os.path.exists(f):
        return
    spec = _iu.spec_from_file_location("teiden_get2", f)
    mod = _iu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    a = "<p>約500軒</p>".encode()
    b = "<p>約700軒</p>".encode()
    eq(len(a), len(b), "検査の作りが悪い（長さが違う）")
    if mod.yubiwa(a) == mod.yubiwa(b):
        raise AssertionError(
            "同じ長さの別の中身が、同じ指紋になっている。**差し替わりを取りこぼす**")


def test_承継を名前でつないでいないか():
    """**「前と後」が要るところは、外れない鍵を使う。**

    2026-09-21。承継の届出は198件あるのに、**誰から誰へは19件しか言えなかった。**

    理由は「取れていない」ではなかった。
    **元の表に「前の設置者」の列が無い。** 前は、**前の届出にしか無い。**

        **施設名を寄せる**   どの出どころでも使えるが、**表記ゆれで外れる**
        **店舗番号**         1つの出どころにしか無いが、**外れない**

    番号でつないだら **19件 → 104件** になった。

    **ただし番号は、その出どころの中でしか通じない。**
    施設名の寄せ方は**置き換えない**。片方に寄せると、
    **番号の無い出どころが丸ごと落ちる。**

    ネットには出ない。**作った記録を渡して、つながるかだけ見る。**
    """
    import importlib.util as _iu
    f = os.path.join(HERE, "hako_rireki.py")
    if not os.path.exists(f):
        return
    spec = _iu.spec_from_file_location("hako_rireki_sk", f)
    mod = _iu.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # **同じ番号・違う書き方の施設名。** 名前で寄せたらつながらない形
    recs = [
        {"source": "例", "store_no": "01-05", "kind": "新設",
         "notified_on": "2010-01-01", "store": "ＡＢＣモール",
         "operator_display": "架空商事株式会社", "operator_kind": "corp"},
        {"source": "例", "store_no": "01-05", "kind": "承継",
         "notified_on": "2015-01-01", "store": "abcモール　別館表記",
         "operator_display": "別の架空株式会社", "operator_kind": "corp"},
        # **番号が無い出どころ。**「無い」ではなく「つなげない」
        {"source": "他", "kind": "承継", "notified_on": "2016-01-01",
         "store": "番号なしモール", "operator_display": "架空乙株式会社",
         "operator_kind": "corp"},
    ]
    sk = mod.shoukei(recs)
    if len(sk) != 1:
        # **eq() は続きを走らせる。** ここで止めないと、次の行が
        # IndexError になって**理由が読めなくなる**（2026-09-21）
        raise AssertionError(
            f"番号でつながった承継が {len(sk)} 件。1件のはず。"
            "**名前で寄せていないか**（表記ゆれで外れる）")
    e = sk[0]
    eq(e["from"], "架空商事株式会社", "前の設置者が違う")
    eq(e["to"], "別の架空株式会社", "後の設置者が違う")
    eq((e["after"], e["before"]), ("2010-01-01", "2015-01-01"),
       "変わった区間が点になっている")

    # **書き方だけの違いは、印を立てて落とせる形になっているか**
    recs2 = [
        {"source": "例", "store_no": "02-01", "kind": "新設",
         "notified_on": "2010-01-01", "store": "甲モール",
         "operator_display": "架空商事株式会社", "operator_kind": "corp"},
        {"source": "例", "store_no": "02-01", "kind": "承継",
         "notified_on": "2015-01-01", "store": "甲モール",
         "operator_display": "架空商事㈱", "operator_kind": "corp"},
    ]
    sk2 = mod.shoukei(recs2)
    if len(sk2) != 1:
        raise AssertionError(
            f"書き方だけ違う承継が {len(sk2)} 件。1件のはず。"
            "**最初から落としている**（印を立てて残すこと）")
    if not sk2[0]["kakikata"]:
        raise AssertionError(
            "書き方だけの違いに印が立っていない。**交代として数えてしまう**")


def test_金庫の鍵の形が手順書でそろっているか():
    """**鍵の形を足した日に、片方の手順書が黙る。**

    2026-09-21。金庫の鍵は SSH の deploy key だけだった。
    **作るのにターミナルが要る**ので、GitHubの画面だけで作れる形（トークン）も足した。

    足すときに、**3本のうち1本を直し忘れると、その手順書だけ金庫に入らない。**
    しかも**赤くならない**——「鍵が無い回」として、今まで通り緑で終わる。
    **黙って生データが金庫に入らない。**

    ここが見るのは、**金庫を見ている手順書が、2つの鍵をそろって見ているか**。

    **捕まえないもの**：鍵が本当に効くか。そちらは走らせないと分からない。
    """
    import re as _re
    warui = []
    for f in workflow_files():
        honbun = open(f, encoding="utf-8").read()
        na = os.path.basename(f)
        miru = "RAW_DEPLOY_KEY" in honbun or "RAW_TOKEN" in honbun
        if not miru:
            continue  # 金庫を見ていない手順書。**名前の一覧で決め打ちしない**
        if "RAW_DEPLOY_KEY" not in honbun:
            warui.append(f"{na}: SSH の鍵を見ていない")
        if "RAW_TOKEN" not in honbun:
            warui.append(f"{na}: **トークンを見ていない**（画面だけで作れるほう）")
        # 出し方のほうもそろっているか
        if "actions/checkout" in honbun and "ssh-key:" in honbun:
            if "token: ${{ secrets.RAW_TOKEN" not in honbun:
                warui.append(f"{na}: 出すときにトークンを渡していない")
    if warui:
        raise AssertionError(
            f"金庫の鍵の形がそろっていない: {warui}。"
            "**片方だけ入れた日に、その手順書だけ黙って金庫に入らない**")


def test_前向き観測が過去を混ぜていないか():
    """**過去は直せない。だから今日から先だけを貯める。**

    2026-09-21。「どれだけ早く知れるか」を測ろうとしたら、
    **まとめて取った日が混ざって**いて測れなかった（1,419件・714件）。

    そこで**前向き観測**を始めた。**始めた日より前は入れない。**

    ここが見るのは3つ。

        **始めた日が動いていないか**（動かすと、混ざったものが入り込む）
        **始めた日より前のものを拾っていないか**
        **公開の日が無いものを、こちらが見た日で埋めていないか**（ルール⑥）

    3つ目がいちばん危ない。埋めると、
    **相手が出した日と、こちらが見た日が、同じ欄で混ざる。**

    ネットには出ない。**作った記録を渡すだけ。**
    """
    import importlib.util as _iu
    f = os.path.join(HERE, "shinsetsu_sokuho.py")
    if not os.path.exists(f):
        return
    spec = _iu.spec_from_file_location("shinsetsu_sokuho", f)
    mod = _iu.module_from_spec(spec)
    spec.loader.exec_module(mod)

    eq(mod.KAISHI, "2026-09-21",
       "前向き観測の始めた日が動いている。**動かすと、混ざったものが入り込む**")

    recs = [
        # **始めた日より前。** 入ってはいけない
        {"kind": "新設", "store": "古いモール", "notified_on": "2026-01-01",
         "first_seen": "2026-09-11", "source": "例"},
        # 公開の日が**ある**もの
        {"kind": "新設", "store": "甲モール", "notified_on": "2026-09-01",
         "first_seen": "2026-09-25", "source": "例",
         "gazette_date": "2026-09-20"},
        # 公開の日が**無い**もの。**埋めてはいけない**
        {"kind": "新設", "store": "乙モール", "notified_on": "2026-09-02",
         "first_seen": "2026-09-26", "source": "他"},
        # 新設でないもの
        {"kind": "変更", "store": "丙モール", "notified_on": "2026-09-03",
         "first_seen": "2026-09-27", "source": "例"},
    ]
    de = mod.hirou(recs)
    eq(len(de), 2, "拾い方が違う（始めた日より前か、新設でないものを拾っている）")
    na = {e["store"] for e in de}
    if "古いモール" in na:
        raise AssertionError("**始めた日より前のものを拾っている**。混ざったものが入る")

    otsu = [e for e in de if e["store"] == "乙モール"][0]
    if otsu["koukai_bi"] is not None:
        raise AssertionError(
            f"公開の日が無いのに {otsu['koukai_bi']!r} が入っている。"
            "**こちらが見た日で埋めている**（相手が出した日と混ざる）")
    eq(otsu["koukai_no_moto"], "分からない", "分からないと名乗っていない")

    kou = [e for e in de if e["store"] == "甲モール"][0]
    eq(kou["koukai_bi"], "2026-09-20", "公告の日を拾えていない")


def test_フロアマップの関所が分からないを通ったことにしていないか():
    """**取ってよいと確かめられていないのに、取りに行っていないか。**

    フロアマップは役所の届出と違って、**相手に見せる義務が無い**。
    だから関所を通らなかったときは、**そこで止まる**のが既定。

    捕まえるのは1つだけ——`check_robots` が
    **拒否（False）や分からない（None）を返したのに、ページを開きに行く**形。

    2026-09-21、手元で6施設とも `None`（この箱が外に出られない）だった。
    **その回にトップを開きに行っていたら、robots を1バイトも読まずに叩いていた。**

    ネットには出ない。`check_robots` と `get` を差し替えて、**呼ばれた回数**を見る。
    """
    import floor_kanmon as fk

    moto_robots, moto_get = fk.check_robots, fk.get
    moto_sleep = fk.time.sleep
    try:
        fk.time.sleep = lambda *a: None
        for kotae, mei in ((False, "拒否"), (None, "分からない")):
            yonda = []
            fk.check_robots = lambda u, _k=kotae: (_k, "（差し替え）")
            fk.get = lambda u: yonda.append(u) or (200, "text/html", b"")
            d = fk.hitotsu("甲モール", "どこか", "https://例.example/",
                           "https://例.example/floor")
            if yonda:
                raise AssertionError(
                    f"robots が「{mei}」なのに {len(yonda)} 回開きに行った: {yonda}")
            if d["robots"] != mei:
                raise AssertionError(f"robots の答えを「{mei}」と書いていない（{d['robots']}）")

        # 許可のときだけ開く。**開かないほうに倒していないか**も見る
        yonda = []
        fk.check_robots = lambda u: (True, "許可")
        fk.get = lambda u: yonda.append(u) or (
            200, "text/html; charset=utf-8",
            '<a href="/policy">サイトのご利用について</a>'.encode())
        d = fk.hitotsu("乙モール", "どこか", "https://例.example/",
                       "https://例.example/floor")
        eq(len(yonda), 1, "robots が許可なのにトップを開いていない")
        eq([x["url"] for x in d["約束"]], ["https://例.example/policy"],
           "人への約束の在りかを拾えていない")
    finally:
        fk.check_robots, fk.get, fk.time.sleep = moto_robots, moto_get, moto_sleep


def test_フロアマップの関所が中身を公開側に書いていないか():
    """**関所の記録に、フロアマップの中身が混ざっていないか。**

    関所が書いてよいのは「robots が何と言ったか」「約束がどこにあるか」まで。
    **店の名前や区画は1つも入らない。**

    `data/ref/` はリポジトリに入れた時点で URL になる（2026-09-20 に踏んだ）。
    規約が転載を禁じている相手のものを、**取ってよいかを調べる段で先に配る**のは順番が逆。
    """
    import floor_kanmon as fk

    if "inbox" not in str(fk.INBOX):
        raise AssertionError(f"生のバイトの置き場が inbox の外にある: {fk.INBOX}")
    kekka = [{"名前": "甲モール", "場所": "どこか",
              "トップ": "https://例.example/",
              "フロアマップ": "https://例.example/floor",
              "robots": "許可", "robots_riyuu": "許可",
              "約束": [{"text": "利用規約", "url": "https://例.example/terms"}],
              # 取った中身が d に残っていても、報告には出ないこと
              "本文": "1F ユニクロ／2F 空区画", "note": ""}]
    md = fk.houkoku(kekka, "2026-09-21")
    for ng in ("ユニクロ", "空区画", "本文"):
        if ng in md:
            raise AssertionError(f"関所の記録に中身が混ざっている: {ng}")


def test_生データを公開側が追跡していないか():
    """**金庫に移したあと、また公開側に戻っていないか。**

    2026-09-21、公開側は `data/raw` `data/files` `data/ocr` `data/wayback` を
    **1,978件、追跡したままだった。**伏せ処理を通す前の HTML・PDF・OCR なので、
    氏名と地番がそのまま入っている。同じ日に金庫（private）へ移した。

    `data/*.md`（走らせた記録）も同じ。生の値を含みうる。

    2026-09-22、`data/koho`（兵庫県公報の本文と目録）を同じ形にした。
    **公開側から外したのに `.gitignore` に書き足すのを忘れていた**（#173）。
    許可リストから外れていても、`.gitignore` に無ければ
    `git add data` のような書き方1つで戻る。**外すことと、戻らないことは別。**

    **戻り方は「誰かが git add した」だけではない。**`.gitignore` の書き方でも戻る——
    巡回中この4つは金庫への **symlink** になるので、`data/raw/` と末尾に `/` を
    付けると**ディレクトリにしか当たらず、symlink のほうが追跡されてしまう。**

    **捕まえないもの**：過去のコミットに残っているもの。**そちらは消えていない。**
    消すには履歴の書き換えが要る（force-push）ので、人が決める。
    ここが見るのは「いまの木」だけ。
    """
    import subprocess
    try:
        de = subprocess.run(
            ["git", "ls-files", "--", "data/raw", "data/files", "data/ocr", "data/wayback",
             "data/koho", ":(glob)data/*.md"],
            cwd=HERE, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return          # git が無い場所では見ない（**「0件」と言わない**）
    if de.returncode != 0:
        return
    nokori = [x for x in de.stdout.splitlines() if x.strip()]
    if nokori:
        raise AssertionError(
            f"生データか走らせた記録を公開側が追跡している（{len(nokori)}件）。"
            f"例: {nokori[:3]}。金庫 VirgoB77/ogataten-nippo-raw に置く（9節）")

    # `.gitignore` の書き方で戻らないか。**末尾の / を付けない**
    gi = open(os.path.join(HERE, ".gitignore"), encoding="utf-8").read().splitlines()
    gyou = {x.strip() for x in gi if x.strip() and not x.strip().startswith("#")}
    for michi in ("data/raw", "data/files", "data/ocr", "data/wayback", "data/koho"):
        if michi + "/" in gyou:
            raise AssertionError(
                f"`.gitignore` が `{michi}/` と書いている。"
                "巡回中はここが symlink になるので、ディレクトリにしか当たらない")
        if michi not in gyou:
            raise AssertionError(f"`.gitignore` に `{michi}` が無い")


def test_フロアマップを人が規約を読む前に取りに行かないか():
    """**robots は機械が読めるが、利用規約は読めない。**

    大店立地法の届出は公開が法律で決まっているが、**フロアマップは相手の持ち物**で、
    見せる義務が無い。だから関所を2つにした。

        robots.txt   この箱が毎回見る
        `ok_hi`      **人が規約を読んで「取ってよい」と決めた日**

    **`ok_hi` が空のうちは、robots が許可でも取りに行かない。**
    ここを通してしまうと、**誰も読んでいないものを「確かめた」と名乗る**（ルール⑥）。

    ネットには出ない。`check_robots` と `get` を差し替えて、**呼ばれた回数**を見る。
    カードの門（common/kado.py）は**通す偽物**に差し替える——ここで見たいのは
    利用規約の関所であって、門そのものの挙動は tests/test_kado.py が確かめている。
    """
    import floor_get as fg

    moto_robots, moto_get, moto_sleep = fg.check_robots, fg.get, fg.time.sleep
    try:
        fg.time.sleep = lambda *a: None
        yonda = []
        fg.check_robots = lambda u: (True, "許可")          # robots は許可
        fg.get = lambda u: yonda.append(u) or (
            200, b"x", "",
            {"todoita": True, "owari": True, "moto_kensuu": None})

        with toosu_kado_mon(fg):
            k = {"id": "kou", "mei": "甲モール", "unei": "甲",
                 "chizu": "https://例.example/floor",
                 "yakusoku": {"mita_hi": "", "kekka": "未確認", "riyuu": "", "url": ""}}
            d = fg.hitotsu(k, {"shisetsu": {}}, "2026-09-21")
            if yonda:
                raise AssertionError(
                    f"人が規約を読む前に {len(yonda)} 回取りに行った: {yonda}")
            if d["kekka"] != "見送り":
                raise AssertionError(f"見送っていない（{d['kekka']}）")

            # **相手が禁じている**とき。robots が許可でも通さない。
            # **「未確認」と同じ顔にしない**——理由が記録に残ること
            k["yakusoku"] = {"mita_hi": "2026-09-21", "kekka": "取ってはいけない",
                             "riyuu": "複製・二次利用を禁じている", "url": "サイトポリシー"}
            d = fg.hitotsu(k, {"shisetsu": {}}, "2026-09-21")
            if yonda:
                raise AssertionError(f"禁じられているのに {len(yonda)} 回取りに行った: {yonda}")
            eq(d["kekka"], "見送り", "禁じられているのに見送っていない")
            if "禁じ" not in d["riyuu"]:
                raise AssertionError(f"禁じられたことが理由に残っていない（{d['riyuu']}）")

            # **「取ってよい」なのに読んだ日が無い**のも通さない。いつの判断か分からない
            k["yakusoku"] = {"mita_hi": "", "kekka": "取ってよい", "riyuu": "", "url": ""}
            d = fg.hitotsu(k, {"shisetsu": {}}, "2026-09-21")
            if yonda:
                raise AssertionError("読んだ日が無いのに取りに行った")

            # 人が読んで「取ってよい」と決めていれば、取りに行く。**行かない側に倒していないか**
            k["yakusoku"] = {"mita_hi": "2026-09-21", "kekka": "取ってよい",
                             "riyuu": "禁止が書かれていない", "url": "サイトポリシー"}
            d = fg.hitotsu(k, {"shisetsu": {}}, "2026-09-21")
            eq(len(yonda), 1, "人が読んだ日が入っているのに取りに行っていない")
            eq(d["kekka"], "取れた", "取れたと書いていない")
            eq(d["henka"], "はじめて", "1枚目を「はじめて」と書いていない")
    finally:
        fg.check_robots, fg.get, fg.time.sleep = moto_robots, moto_get, moto_sleep


def test_フロアマップの指紋と回数の数え方():
    """**「変わっていない」と「2回見ていない」を同じ顔にしない。**

    ① 1枚目は「はじめて」。**「変わっていない」ではない**
    ② 指紋は sha256。**長さで代用しない**——1文字だけ差し替わると長さは同じまま通る
    ③ 同じ日に2回目は行かない（**相手の数で数える**）
    """
    import floor_get as fg

    # ② 長さが同じで中身が違うものを、別の指紋にする
    a, b = b"1F ABC", b"1F ABD"
    eq(len(a), len(b), "この検査の前提（長さが同じ）が崩れている")
    if fg.yubiwa(a) == fg.yubiwa(b):
        raise AssertionError("長さが同じだと指紋も同じになっている。長さで代用している")

    # ③ 今日すでに見た施設は、もう行かない
    # **観測元も入れる。** 入っていない記録は「比べる相手ではない」に倒れる
    dai = {"shisetsu": {"kou": {"mei": "甲", "kiroku": [
        {"hi": "2026-09-21", "yubiwa": fg.yubiwa(a),
         "moto_url": "https://例.example/floor"}]}}}
    if not fg.kyou_mita(dai, "kou", "2026-09-21"):
        raise AssertionError("今日の記録があるのに「まだ見ていない」と言っている")
    if fg.kyou_mita(dai, "kou", "2026-09-22"):
        raise AssertionError("別の日の記録を今日のものと数えている")

    moto_robots, moto_get, moto_sleep = fg.check_robots, fg.get, fg.time.sleep
    try:
        fg.time.sleep = lambda *a: None
        yonda = []
        fg.check_robots = lambda u: (True, "許可")
        fg.get = lambda u: yonda.append(u) or (
            200, b, "",
            {"todoita": True, "owari": True, "moto_kensuu": None})
        with toosu_kado_mon(fg):
            k = {"id": "kou", "mei": "甲モール", "unei": "甲",
                 "chizu": "https://例.example/floor",
                 "yakusoku": {"mita_hi": "2026-09-21", "kekka": "取ってよい",
                              "riyuu": "", "url": ""}}
            d = fg.hitotsu(k, dai, "2026-09-21")
            if yonda:
                raise AssertionError("同じ相手に1日2回行った")
            eq(d["kekka"], "見送り", "今日すでに見たのに取りに行っている")

            # 次の日。指紋が違えば「変わった」
            d = fg.hitotsu(k, dai, "2026-09-22")
            eq(d["henka"], "**変わった**", "指紋が違うのに「変わった」と書いていない")
    finally:
        fg.check_robots, fg.get, fg.time.sleep = moto_robots, moto_get, moto_sleep


def test_フロアマップの精度の分母が膨らんでいないか():
    """**原典に無いものを作ったとき、分母に入れると精度が上がってしまう。**

    「作った」行は**原典にある数に入れない。**入れると、でっちあげるほど
    分母が増えて、見かけの精度が良くなる。**いちばん危ない数え方**。

    ここは `floor_kumu.kazoeru` の算数だけを見る。ネットにも出ないし、読み取りもしない。
    """
    import floor_kumu as fk

    d = {"id": "kou", "mei": "甲モール", "mita_hi": "2026-09-21",
         "moto": {"donoyouni": "人が渡した", "katachi": "文字", "hani": "全部",
                  "moji": 10, "bytes": 10},
         "kukaku": [{"kai": "1F", "mise": f"店{i}", "jotai": "営業中"} for i in range(1, 6)]}
    # 5行出した。3行目の店名が違う。5行目は原典に無い。原典にあるのに落とした店が1つ
    awase = {"chigau": [{"gyo": 3, "ran": "mise", "tadashii": "本当の店"}],
             "otoshita": [{"kai": "2F", "mise": "落ちた店"}],
             "tsukutta": [5]}
    n = fk.kazoeru(d, awase)
    eq(n["合っていた"], 3, "合っていた数がちがう")
    eq(n["直した"], 1, "直した数がちがう")
    eq(n["落とした"], 1, "落とした数がちがう")
    eq(n["作った"], 1, "作った数がちがう")
    # **分母は 3+1+1 = 5。作った1行は入れない**
    eq(n["原典にある数（分母）"], 5, "作った行を分母に入れている（精度が水増しされる）")
    eq(round(n["店名の精度"], 4), 0.6, "精度の出し方がちがう")

    # 作った行の店名を「直した」に混ぜても、二重に数えない
    awase2 = dict(awase, chigau=awase["chigau"] + [{"gyo": 5, "ran": "mise", "tadashii": "x"}])
    n2 = fk.kazoeru(d, awase2)
    eq(n2["直した"], 1, "作った行を「直した」にも数えている（二重）")
    eq(n2["原典にある数（分母）"], 5, "分母が動いている")


def test_画面の写真を文字数で測ったことにしていないか():
    """**測れないものに、数を入れない。**

    2026-09-21 の1枚目は、人がスマホで撮った**画面の写真**だった。
    型のほうは「文字数」を必ず入れる形にしていたので、**画像に文字数を書く**か、
    **0 と書く**しかなくなっていた。どちらも**測ったことにならない**（ルール⑥）。

    直した形：

        文字で渡された      `moji`（文字数）が要る
        画面の写真で渡された `maisu`（枚数）が要る。**`moji` は入れてはいけない**

    どちらも `bytes` は要る。**トークン数はどちらでも数えていないので、書かない。**
    """
    import floor_kumu as fk

    moto_ga = {"donoyouni": "人が渡した", "katachi": "画面の写真", "hani": "全部",
               "maisu": 2, "bytes": 991929}
    d = {"id": "kou", "mei": "甲", "mita_hi": "2026-09-21", "moto": moto_ga,
         "kukaku": [{"kai": "2F", "mise": "店", "jotai": "営業中"}]}
    eq(fk.kensa(d), [], "画面の写真なのに型が落ちている")

    # **文字数を入れたら落ちる。** 測れないものを測ったことにしない
    d2 = dict(d, moto=dict(moto_ga, moji=1234))
    if not any("moji" in w for w in fk.kensa(d2)):
        raise AssertionError("画面の写真に文字数が入っているのに、通している")

    # 枚数が無ければ落ちる
    d3 = dict(d, moto={k: v for k, v in moto_ga.items() if k != "maisu"})
    if not any("maisu" in w for w in fk.kensa(d3)):
        raise AssertionError("枚数が無いのに通している")

    # 文字で渡されたほうは、文字数が要る
    d4 = dict(d, moto={"donoyouni": "この箱が取った", "katachi": "文字",
                       "hani": "全部", "bytes": 10})
    if not any("moji" in w for w in fk.kensa(d4)):
        raise AssertionError("文字で渡されたのに、文字数が無くても通している")


def test_一部だけ読んだものを全部の精度として数えないか():
    """**分母が「原典にある数」ではなく「こちらが見た範囲」になっていないか。**

    2026-09-21。1枚目の1Fは、**地図の赤帯（予告）だけ**を読んだ。全区画は読んでいない。
    そのまま数えると、**見た2行のうち2行が合っていて「精度100%」**になる。
    **見ていないものは、落としたことにもならない**（9節「0件は、正しさの証拠ではない」）。

    だから「どこまで読んだか」を欄にして、**全部でなければ数えない。**

    予告そのものも検査する。**年は足さない**——地図に書いていないので、
    「9/18」に今年を足すのは作文（3.4）。
    """
    import floor_kumu as fk

    moto = {"donoyouni": "人が渡した", "katachi": "画面の写真", "maisu": 2,
            "bytes": 100, "hani": "予告だけ"}
    d = {"id": "kou", "mei": "甲", "mita_hi": "2026-09-21", "moto": moto,
         "kukaku": [{"kai": "1F", "mise": "店", "jotai": "分からない",
                     "yokoku": {"hi": "9/18", "nani": "OPEN"}}]}
    eq(fk.kensa(d), [], "予告だけの記録で型が落ちている")
    try:
        fk.kazoeru(d, {})
    except ValueError:
        pass
    else:
        raise AssertionError("一部だけ読んだものの精度を出している（分母が見た範囲になる）")

    # 全部読んだと書けば数える
    d2 = dict(d, moto=dict(moto, hani="全部"))
    n = fk.kazoeru(d2, {})
    eq(n["合っていた"], 1, "全部読んだ記録で数えられていない")

    # 予告の型。**知らない言葉は通さない**
    d3 = dict(d, kukaku=[dict(d["kukaku"][0], yokoku={"hi": "9/18", "nani": "しめる"})])
    if not any("yokoku.nani" in w for w in fk.kensa(d3)):
        raise AssertionError("知らない予告の言葉を通している")

    # **年を足していないか。** 日は文字のまま持つ
    d4 = dict(d, kukaku=[dict(d["kukaku"][0], yokoku={"hi": 918, "nani": "OPEN"})])
    if not any("yokoku.hi" in w for w in fk.kensa(d4)):
        raise AssertionError("予告の日が文字でないのに通している")


def test_テナントの下見が規約より先に開いていないか():
    """**規約 → robots → 下見。この順を飛ばしていないか。**

    「HTMLなら軽い」は、**規約の話を何も変えない。**
    2026-09-21 に確かめた2施設の文面は、どちらも「掲載している**情報**」が対象で、
    画像かHTMLかを分けていない。**取り方を変えても、壁は同じ場所にある。**

    そしてもう1つ——**「未確認」と「技術的に取得困難」を混ぜない。**
    前者は確認・判定・承認が済めば変わりうる。後者は相手の作りの話。
    混ぜると「あと何をすれば進むのか」が分からなくなる。
    """
    import tenant_recon as tr

    moto_robots, moto_get, moto_sleep = tr.check_robots, tr.get, tr.time.sleep
    try:
        tr.time.sleep = lambda *a: None
        mita = []
        tr.check_robots = lambda u: mita.append(("robots", u)) or (True, "許可")
        tr.get = lambda u: mita.append(("get", u)) or (200, "text/html", b"")

        for kekka in ("未確認", "取ってはいけない"):
            mita.clear()
            k = {"id": "kou", "mei": "甲", "unei": "甲",
                 "chizu": "https://例.example/shop",
                 "yakusoku": {"kekka": kekka, "mita_hi": "2026-09-21"}}
            d = tr.hitotsu(k, "2026-09-21")
            if mita:
                raise AssertionError(
                    f"規約が「{kekka}」なのに {len(mita)} 回さわった: {mita}")
            eq(d["robots"], "見ていない", f"規約が「{kekka}」なのに robots を見ている")
        eq(d["wake"], "拒否", "禁じられているのに「拒否」にしていない")
    finally:
        tr.check_robots, tr.get, tr.time.sleep = moto_robots, moto_get, moto_sleep

    # **分け方。** 未確認と技術的に取得困難を取り違えていないか
    moto = {"yakusoku": "取ってよい", "robots": "許可"}
    wake, _ = tr.wakeru(dict(moto, shitami=None))
    eq(wake, "未確認", "下見をしていないのに、取得困難のせいにしている")

    # JS が描いている画面
    wake, _ = tr.wakeru(dict(moto, shitami={
        "zenbu_moji": 10000, "mieru_moji": 200,
        "kotei_url": {"katachi": "/shop/＊", "kazu": 120}}))
    eq(wake, "技術的に取得困難", "JS を落とすと空なのに「許可」にしている")

    # 固定URLが見当たらない
    wake, _ = tr.wakeru(dict(moto, shitami={
        "zenbu_moji": 10000, "mieru_moji": 9000, "kotei_url": {"katachi": "/a", "kazu": 3}}))
    eq(wake, "技術的に取得困難", "固定URLが3本しかないのに「許可」にしている")

    # 取れる形
    wake, _ = tr.wakeru(dict(moto, shitami={
        "zenbu_moji": 10000, "mieru_moji": 9000,
        "kotei_url": {"katachi": "/shop/＊", "kazu": 120}}))
    eq(wake, "許可", "取れる形なのに「許可」にしていない")


def test_テナントの下見が店の名前を持ち帰っていないか():
    """**下見は形だけを測る。店の名前は1つも返さない。**

    記録は公開側（`data/ref/`）に置く。リポジトリに入れた時点でURLになるので、
    **規約を確かめる前の相手の店名が、そこに出てはいけない**（2026-09-20 に踏んだ形）。

    `kata()` は URL の形を作る関数。**数字を含む区切りを伏せる**ので、
    店番号もそのまま残らない。
    """
    import tenant_recon as tr

    h = ('<html><body><a href="/shop/detail/1234">甲という店</a>'
         '<a href="/shop/detail/5678">乙という店</a>'
         '<script>var x="丙という店";</script>'
         '<p>1F と 2F と 地下1階</p></body></html>').encode()
    s = tr.shitami("https://例.example/shop", h, "text/html; charset=utf-8")
    nakami = json.dumps(s, ensure_ascii=False)
    for na in ("甲という店", "乙という店", "丙という店", "1234", "5678"):
        if na in nakami:
            raise AssertionError(f"下見の結果に店の名前か番号が残っている: {na}")
    eq(s["kotei_url"]["kazu"], 2, "同じ形のリンクを数えられていない")
    eq(s["kotei_url"]["katachi"], "/shop/detail/＊", "URL の形が伏せられていない")
    # **JS の中の文字は数に入れない。** 画面に出ていないものを「入っている」と数えない
    if "丙" in str(s.get("mieru_moji")):
        raise AssertionError("ありえない形")
    eq(s["kai_kazu"], 3, f"階の表記を数えられていない（{s['kai_hyouki']}）")


def test_一部だけ答え合わせしたものを精度と呼んでいないか():
    """**確かめる行を選ぶのは人。だからその分母で割ったものは精度ではない。**

    2026-09-21、70行のうち**5行だけ**人が確かめた。しかもその5行は
    **こちらが「自信が無い」と印をつけた行**から選ばれている。
    そのまま割ると**低く出る。** 逆に自信のある行から確かめれば**高く出る。**
    **どちらも精度ではない。**

    だから `mita`（確かめた行番号）が全部を覆っていないときは、

        店名の精度        出さない
        人の手間          出さない
        落とした          **確かめていない**（0ではない）
        原典にある数      **確かめていない**

    とし、代わりに「**確かめた範囲での合致率**」を、精度とは別の名前で出す。

    `test_一部だけ読んだものを全部の精度として数えないか` は**読む側**の話。
    こちらは**答え合わせ側**。**同じ間違いが2か所で起きる。**
    """
    import floor_kumu as fk

    d = {"id": "kou", "mei": "甲", "mita_hi": "2026-09-21",
         "moto": {"donoyouni": "人が渡した", "katachi": "文字", "hani": "全部",
                  "moji": 10, "bytes": 10},
         "kukaku": [{"kai": "1F", "mise": f"店{i}", "jotai": "営業中"}
                    for i in range(1, 11)]}

    # 10行出して、5行だけ確かめた。うち1行は名前が違い、1行は原典に無かった
    n = fk.kazoeru(d, {"mita": [1, 2, 3, 4, 5],
                       "chigau": [{"gyo": 2, "ran": "mise", "tadashii": "本当の店"}],
                       "tsukutta": [3]})
    eq(n["全部を確かめたか"], False, "一部なのに全部を確かめたことにしている")
    eq(n["確かめた行数"], 5, "確かめた行数がちがう")
    eq(n["合っていた"], 3, "確かめた範囲の合致数がちがう")
    if n["店名の精度"] is not None:
        raise AssertionError("一部しか確かめていないのに精度を出している")
    if n["落とした"] is not None:
        raise AssertionError("確かめていない「落とした」を0として出している")
    if n["原典にある数（分母）"] is not None:
        raise AssertionError("確かめていない分母を出している")
    eq(round(n["確かめた範囲での合致率"], 2), 0.6, "合致率の出し方がちがう")

    # **確かめた範囲の外にある指摘は数えない。** 範囲外を混ぜると分母と合わなくなる
    n2 = fk.kazoeru(d, {"mita": [1, 2], "tsukutta": [9],
                        "chigau": [{"gyo": 8, "ran": "mise", "tadashii": "x"}]})
    eq(n2["作った"], 0, "確かめた範囲の外の「作った」を数えている")
    eq(n2["直した"], 0, "確かめた範囲の外の「直した」を数えている")
    eq(n2["合っていた"], 2, "確かめた範囲の合致数がちがう")

    # 全部確かめれば、今まで通り精度が出る
    n3 = fk.kazoeru(d, {"mita": list(range(1, 11)), "tsukutta": [3], "otoshita": [{}]})
    eq(n3["全部を確かめたか"], True, "全部確かめたのに一部扱いにしている")
    if n3["店名の精度"] is None:
        raise AssertionError("全部確かめたのに精度を出していない")
    eq(n3["落とした"], 1, "落とした数がちがう")

    # `mita` を書かなければ、今まで通り「全部確かめた」とみなす
    n4 = fk.kazoeru(d, {"tsukutta": [3]})
    eq(n4["全部を確かめたか"], True, "mita が無いのに一部扱いにしている")


def test_企業側でも規約の関所を通しているか():
    """**向きが変わっても関所は同じ。**

    「施設の規約が厳しいから、テナント企業側なら取ってよい」——**これは通さない。**
    企業ごとに robots と利用規約を確かめる。

    そして**分け方を2か所に書かない。** `tenanto_kanmon` は
    `tenant_recon.wakeru` を呼ぶ。同じ言葉で違う判定をする形は、監査で何度も出ている。
    """
    import tenant_recon as tr
    import tenanto_kanmon as tk

    if tk.wakeru is not tr.wakeru:
        raise AssertionError("分け方が2か所にある。`tenant_recon.wakeru` を使う")

    moto_robots, moto_get, moto_sleep = tk.check_robots, tk.get, tk.time.sleep
    try:
        tk.time.sleep = lambda *a: None
        mita = []
        tk.check_robots = lambda u: mita.append(("robots", u)) or (True, "許可")
        tk.get = lambda u: mita.append(("get", u)) or (200, "text/html", b"")

        k = {"id": "kou", "mei": "甲社", "kibo": "大手",
             "ichiran": "https://例.example/shop", "ichiran_note": "", "kaihei": "",
             "yakusoku": {"kekka": "未確認", "mita_hi": ""}}
        d = tk.hitotsu(k, "2026-09-21")
        if mita:
            raise AssertionError(f"規約を読む前に {len(mita)} 回さわった: {mita}")
        eq(d["wake"], "未確認", "未確認になっていない")

        # **一覧のURLが無いとき。**「無い」ではなく「まだ見つけていない」
        k2 = dict(k, ichiran="")
        d2 = tk.hitotsu(k2, "2026-09-21")
        eq(d2["wake"], "未確認", "URLが未特定なのに未確認にしていない")
        if "無い" in d2["riyuu"] and "とは限らない" not in d2["riyuu"]:
            raise AssertionError(f"見つけていないものを「無い」と書いている（{d2['riyuu']}）")

        # 人が読んで「取ってよい」なら、robots を見て開く
        k3 = dict(k, yakusoku={"kekka": "取ってよい", "mita_hi": "2026-09-21"})
        tk.get = lambda u: mita.append(("get", u)) or (
            200, "text/html; charset=utf-8",
            ("<html><body>" + "".join(
                f'<a href="/shop/{i}">店{i}</a>' for i in range(30))
             + "</body></html>").encode())
        mita.clear()
        d3 = tk.hitotsu(k3, "2026-09-21")
        eq([x[0] for x in mita], ["robots", "get"], "規約→robots→下見 の順になっていない")
        eq(d3["wake"], "許可", f"取れる形なのに許可にしていない（{d3['riyuu']}）")
    finally:
        tk.check_robots, tk.get, tk.time.sleep = moto_robots, moto_get, moto_sleep


def test_規約を取る段が本文を持ち帰っていないか():
    """**相手の規約は相手の著作物。記録に1文字も入れない。**

    入れてよいのは「①〜⑤に当たる語が出たか」と「その語が何回出たか」まで。
    **前後の文を入れた時点で、相手の文章を写したことになる。**
    記録は `data/ref/` に置く＝リポジトリに入れた時点でURLになるので、ここが要。

    もう1つ——**「語が無い」を「禁止が無い」と書いていないか。**
    別の言い回しで書いてあることがある。**決めるのは人。**
    """
    import yakusoku_get as yg

    h = ("<html><body><h1>サイトポリシー</h1>"
         "<p>当サイトの掲載内容の著作権は当社に帰属し、無断転載を禁じます。</p>"
         "<p>スクレイピングその他の自動取得はご遠慮ください。</p>"
         "<script>var x='データベース';</script>"
         "</body></html>").encode()
    y = yg.kazoeru_kou(h, "text/html; charset=utf-8")
    nakami = json.dumps(y, ensure_ascii=False)
    # **文がそのまま残っていないか**
    for bun in ("帰属し", "禁じます", "ご遠慮ください", "その他の"):
        if bun in nakami:
            raise AssertionError(f"規約の本文が記録に残っている: {bun}")
    kou = {x["no"]: x for x in y["kou"]}
    eq(kou["1"]["atta"], True, "著作物の項を拾えていない")
    eq(kou["2"]["atta"], True, "掲載内容の項を拾えていない")
    eq(kou["4"]["atta"], True, "自動取得の項を拾えていない")
    # **JS の中の語は数えない。** 画面に出ていないものを「書いてある」と数えない
    eq(kou["5"]["atta"], False, "JS の中の語を本文として数えている")
    eq(kou["3"]["atta"], False, "無い項を「あり」にしている")

    # 記録の文面が「語が無い＝禁止が無い」と言っていないか
    md = yg.houkoku([{"id": "kou", "mei": "甲社", "top": "https://例.example/",
                      "arika": [{"text": "サイトポリシー", "url": "https://例.example/p"}],
                      "yonda": dict(y, url="https://例.example/p"),
                      "robots_top": "許可", "robots_yakusoku": "許可", "note": ""}],
                    "2026-09-21")
    for bun in ("帰属し", "禁じます", "ご遠慮ください"):
        if bun in md:
            raise AssertionError(f"記録の md に規約の本文が出ている: {bun}")
    if "「語が無い」は「禁止が無い」ではない" not in md:
        raise AssertionError("「語が無い」を「禁止が無い」と読ませない断りが記録に無い")


def test_規約を取る段の関所がrobotsだけだと書いてあるか():
    """**輪を解くために関所を1つに落とした。その理由を書き残しているか。**

    2026-09-21、関所を「規約が通るまで1バイトも開かない」にしたら、
    **規約のページも開けなくなった。** 判定が永久に「未確認」になる。

    解き方は**2つの行為を分けること**——

        規約を**1回**取る   関所は **robots だけ**
        店舗情報を**毎日**取る 関所は robots ＋ **人が読んだ結果**

    **理由が消えると、次の人は「関所が1つしかない段」を穴だと思って塞ぐ。**
    塞ぐと、また輪に戻る。だから検査で文面を留める。
    """
    import yakusoku_get as yg

    doc = yg.__doc__ or ""
    for kotoba in ("輪", "robots.txt だけ", "店舗情報"):
        if kotoba not in doc:
            raise AssertionError(f"なぜ関所を1つにしたかの説明に「{kotoba}」が無い")
    # **店舗情報を取る側と混ざっていないか。**
    #
    # 2026-09-21、ここは「`shitami` を持っていたら落とす」と書いていた。
    # **その言い分はもう古い。** 企業側では、開くページ自体が店舗一覧
    # （フッターの規約を見るため）なので、**開くこと自体は逸脱ではない。**
    #
    # 本当に守りたい線はこちら——**ページの形を測って「なぜ0本か」を残すのはよい。
    # 店の顔ぶれを記録に出すのはだめ。**
    src = open(os.path.join(HERE, "yakusoku_get.py"), encoding="utf-8").read()
    for na in ("mise_katachi", "shisetsu_go", "kai_hyouki"):
        if na in src:
            raise AssertionError(
                f"規約を取る段が、店の形（{na}）まで記録に出している。"
                "**この段が見てよいのは、なぜ0本かを分ける形だけ**")
    # 形を測るなら、**呼ぶのは1か所の道具**（2か所に書かない）
    if "def shitami(" in src:
        raise AssertionError("形の測り方を2か所に書いている。既にあるものを呼ぶ")


def test_1回だけ見た回を許可にしていないか():
    """**見たことを、許されたことにしない。**

    2026-09-21、統括から「quadro の技術構造を**1回だけ**確認したい」と来た。
    **継続取得の依頼でも、許可判定の依頼でもない。**

    今日ここで作った線をそのまま当てる——

        1回だけ見る   関所は **robots.txt だけ**
        毎日取る      関所は robots ＋ **人が読んだ結果**

    捕まえるのは2つ。

    ① `--ikkai` で下見が通っても、**分けが「許可」にならないこと**
    ② `--ikkai` は **1社ずつしか見られないこと**（`--id` が要る）

    そして**止めた理由と書いた理由を合わせる。**
    robots で止まったのに「規約が未確認だから」と書くのは、ルール⑥そのもの。
    """
    import tenanto_kanmon as tk

    moto_robots, moto_get, moto_sleep = tk.check_robots, tk.get, tk.time.sleep
    try:
        tk.time.sleep = lambda *a: None
        tk.check_robots = lambda u: (True, "許可")
        tk.get = lambda u: (200, "text/html; charset=utf-8",
                            ("<html><body>" + "".join(
                                f'<a href="/shop/{i}">甲モール{i}店</a>'
                                for i in range(30)) + "</body></html>").encode())
        k = {"id": "kou", "mei": "甲社", "kibo": "小規模",
             "ichiran": "https://例.example/shop", "ichiran_note": "", "kaihei": "",
             "yakusoku": {"kekka": "未確認", "mita_hi": ""}}

        d = tk.hitotsu(k, "2026-09-21", ikkai=True)
        eq(d["wake"], "未確認",
           f"1回見ただけで「{d['wake']}」にしている。**見たことを許されたことにしている**")
        eq(d["yakusoku"], "未確認", "1回見た回で規約の欄が動いている")
        if not d.get("shitami"):
            raise AssertionError("1回見る回なのに構造を測っていない")
        # **店の名前は持ち帰らない**
        nakami = json.dumps(d["shitami"], ensure_ascii=False)
        if "甲モール" in nakami:
            raise AssertionError("1回見た結果に店の名前が残っている")
        eq(d["shitami"]["mise_katachi"], 30, "「◯◯店」の形を数えられていない")
        eq(d["shitami"]["shisetsu_go"], 30, "出店先らしい語を数えられていない")

        # **止めた理由と書いた理由を合わせる。** robots で止まったら robots と書く
        tk.check_robots = lambda u: (None, "届かなかった")
        d2 = tk.hitotsu(k, "2026-09-21", ikkai=True)
        if "robots" not in d2["riyuu"]:
            raise AssertionError(
                f"robots で止まったのに、別の理由を書いている（{d2['riyuu']}）")
    finally:
        tk.check_robots, tk.get, tk.time.sleep = moto_robots, moto_get, moto_sleep

    # ② 1社ずつしか見られない
    import contextlib, io as _io
    try:
        with contextlib.redirect_stderr(_io.StringIO()):
            tk.main(["--ikkai"])
    except SystemExit as e:
        if e.code == 0:
            raise AssertionError("--ikkai を --id 無しで通している")
    else:
        raise AssertionError("--ikkai を --id 無しで通している")


def test_規約の在りかを強い順に並べているか():
    """**別物を拾うと、そこから先が全部ずれる。**

    2026-09-21、リンクの語に強弱を付けずに「最初に当たったもの」を取ったら、
    ある会社で**ソーシャルメディアポリシーを拾った。**「著作権」を含んでいたため。
    **店舗情報のページに適用される規約ではない。**

    「著作権」「免責」「禁止事項」は**規約の中の章の名前**なので、
    単独で当てると別物を拾う。**サイト全体の約束を指す語を上に置く。**

    そして**ソーシャルメディア・会員・返品・個人情報**などを含むリンクは、
    サイト全体の約束ではないので後ろへ回す。**消さずに後ろへ回す**——
    ほかに何も無いときは、それでも手がかりになる。
    """
    import yakusoku_get as yg

    h = ('<html><body>'
         '<a href="/socialmediapolicy/">ソーシャルメディアポリシー（著作権について）</a>'
         '<a href="/kaiin/">会員規約</a>'
         '<a href="/terms/">サイトのご利用について</a>'
         '<a href="/copyright/">著作権</a>'
         '</body></html>').encode()
    de = yg.arika("https://例.example/shop/", h, "text/html; charset=utf-8")
    eq([x["url"] for x in de][:2],
       ["https://例.example/terms/", "https://例.example/copyright/"],
       "強い順に並んでいない（1本目を取りに行くので、ここがずれると全部ずれる)")
    # **消していない。**後ろに回っているだけ。
    # 「会員規約」は**そもそも当たらない**——語の一覧に「規約」単独を入れていないため
    # （入れるとポイント規約や返品規約まで拾う）
    eq(len(de), 3, "弱いものを消している。後ろに回すだけにする")
    owari = [x["url"] for x in de][2:]
    if "https://例.example/socialmediapolicy/" not in owari:
        raise AssertionError("ソーシャルメディアポリシーが後ろに回っていない")


def test_規約の記録が読む場所を示せているか():
    """**キーワードの件数だけでは、人が読む場所が分からない。**

    2026-09-21、統括から「規約URLと①〜⑤の該当箇所を渡してほしい」と来た。
    **判定は人がする**ので、**どこを読めばよいか**を機械が示す必要がある。

    出してよいのは**見出しと、あればアンカー付きURL**まで。
    **本文そのものは出さない。**（相手の著作物で、記録は公開側に置くため）
    """
    import yakusoku_get as yg

    h = ('<html><body>'
         '<h1>サイトポリシー</h1>'
         '<h2 id="copyright">著作権について</h2>'
         '<p>当サイトの掲載情報を無断転載することを禁じます。</p>'
         '<h2 id="bot">禁止事項</h2>'
         '<p>スクレイピングはご遠慮ください。</p>'
         '</body></html>').encode()
    y = yg.kazoeru_kou(h, "text/html; charset=utf-8")
    kou = {x["no"]: x for x in y["kou"]}

    # ①は「著作権について」の下、④は「禁止事項」の下に出たと分かること
    m1 = {b["midashi"] for b in kou["1"]["basho"]}
    if "著作権について" not in m1:
        raise AssertionError(f"①の場所を示せていない（{m1}）")
    m4 = {b["midashi"] for b in kou["4"]["basho"]}
    if "禁止事項" not in m4:
        raise AssertionError(f"④の場所を示せていない（{m4}）")
    # アンカーも拾えていること（人がそのまま開ける）
    a4 = {b["anchor"] for b in kou["4"]["basho"]}
    if "bot" not in a4:
        raise AssertionError(f"アンカーを拾えていない（{a4}）")

    # **本文は出していない**
    nakami = json.dumps(y, ensure_ascii=False)
    for bun in ("禁じます", "ご遠慮ください", "当サイトの掲載情報を"):
        if bun in nakami:
            raise AssertionError(f"規約の本文が記録に残っている: {bun}")


def test_人が渡した規約URLを探さずに取りに行くか():
    """**機械で規約を特定できない相手がいる、というのが結論だった。**

    2026-09-21、店舗一覧ページのフッターから規約を辿る形を試したところ、
    **JS でフッターを描いている相手には届かなかった。**
    人がブラウザで開けば見えるのに、静的HTMLには無い。

    そこで**人が開いてURLを渡す口**を作った。捕まえるのは2つ。

    ① 渡されていれば、**探さずに直に取りに行く**（フッターを見に行かない）
    ② **渡されたURLを作り変えない**——ドメインに丸めたり、末尾を足したりしない
       （`teiden_recon` で踏んだ形。10社中6社が親会社の玄関になるところだった）

    **robots は渡されたときも見る。** 人が渡したことは、相手の指示を上書きしない。
    """
    import yakusoku_get as yg

    moto_robots, moto_get, moto_sleep = yg.check_robots, yg.get, yg.time.sleep
    moto_inbox = yg.INBOX
    import tempfile, pathlib
    try:
        yg.time.sleep = lambda *a: None
        mita = []
        yg.check_robots = lambda u: mita.append(("robots", u)) or (True, "許可")
        yg.get = lambda u: mita.append(("get", u)) or (
            200, "text/html; charset=utf-8",
            "<html><body><h1>サイトポリシー</h1></body></html>".encode())
        with tempfile.TemporaryDirectory() as d:
            yg.INBOX = pathlib.Path(d)
            watashita = "https://例.example/a/b/terms.html?x=1"
            k = {"id": "kou", "mei": "甲社",
                 "top": "https://例.example/shop/", "yakusoku_url": watashita}
            r = yg.hitotsu(k, "2026-09-21")

        # ① 店舗一覧のフッターを見に行っていない
        itta = [u for na, u in mita if na == "get"]
        eq(itta, [watashita],
           f"渡されているのに、ほかのページも開いている（{itta}）")
        # ② URL を作り変えていない
        eq(r["yonda"]["url"], watashita, "渡されたURLを作り変えている")
        # robots は渡されたときも見ている
        if not any(na == "robots" and u == watashita for na, u in mita):
            raise AssertionError("人が渡したときに robots を見ていない")
    finally:
        yg.check_robots, yg.get, yg.time.sleep = moto_robots, moto_get, moto_sleep
        yg.INBOX = moto_inbox


def test_書いていない禁止を書いてあることにしていないか():
    """**④が「なし」の相手を、「自動取得が禁止されている」と書かない。**

    2026-09-21、ある会社で止める判断が出た。**理由は④⑤ではない。**

        ④ 自動取得の明示的禁止   **確認されなかった**
        ⑤ データベース化の禁止    **確認されなかった**
        止めた理由              「本サイトの内容」を承諾なく複製その他利用する
                                ことを**広く制限している**ため。
                                そして**迷ったら止まる**という自分たちの線

    **この2つを混ぜると、後で「禁止されていた」と読み違える。**
    止めたのはこちらの判断であって、相手が名指しで禁じたのではない。
    **書いていないことを、書いてあることにしない**（ルール⑥）。

    捕まえるのは、**④が「なし」なのに理由へ「スクレイピング」「クローリング」
    「自動取得が禁止」と書いている**形。
    """
    import tenanto_kanmon as tk

    NG = ("スクレイピングが禁止", "スクレイピングを禁止", "クローリングが禁止",
          "自動取得が禁止", "自動取得を禁止", "自動収集が禁止")
    for k in tk.KAISHA:
        ya = k.get("yakusoku") or {}
        kou = ya.get("kou") or {}
        riyuu = ya.get("riyuu") or ""
        yon = kou.get("4", "")
        if yon and "なし" in yon:
            for ng in NG:
                if ng in riyuu:
                    raise AssertionError(
                        f"{k['mei']}：④は「{yon}」なのに、理由に「{ng}」と書いている。"
                        "**書いていない禁止を、書いてあることにしている**")
        # **止めたときは、なぜ止めたかが理由に残っていること**
        if ya.get("kekka") == "取ってはいけない" and len(riyuu) < 20:
            raise AssertionError(f"{k['mei']}：止めたのに理由が書かれていない")

    # **まとめの一言で、書いてある理由を上書きしていないか。**
    # 「利用規約が断っている」と出してしまうと、**こちらが迷って止めた場合も
    # 相手が名指しで禁じたように読める**（2026-09-21）
    moto_robots, moto_get, moto_sleep = tk.check_robots, tk.get, tk.time.sleep
    try:
        tk.time.sleep = lambda *a: None
        tk.check_robots = lambda u: (True, "許可")
        tk.get = lambda u: (200, "text/html", b"")
        for k in tk.KAISHA:
            ya = k.get("yakusoku") or {}
            if not ya.get("riyuu"):
                continue
            d = tk.hitotsu(k, "2026-09-21")
            if d["riyuu"] != ya["riyuu"]:
                raise AssertionError(
                    f"{k['mei']}：表に書いた理由が、まとめの一言に上書きされている"
                    f"（出た値: {d['riyuu'][:40]}…）")
    finally:
        tk.check_robots, tk.get, tk.time.sleep = moto_robots, moto_get, moto_sleep


def test_日本語が無いページの0を禁止が無いと書いていないか():
    """**探している語が全部日本語なら、英語のページでは必ず0になる。**

    2026-09-21、ある会社の規約URLを開いたら、**返ってきたのは英語の商品一覧**だった
    （見出しが全部商品名）。①〜⑤はすべて0。
    **そのまま「なし」と並べると、「禁止が無い会社」に見える。**

    **0の理由が「禁止が無い」なのか「日本語の規約を読んでいない」なのかは、
    まるで違う。** 前者は判断材料になるが、後者は**まだ何も見ていない。**

    日本語の字が1割に満たないページでは、**「なし」ではなく「日本語なし」**と書く。
    """
    import yakusoku_get as yg

    # 英語だけのページ
    en = ("<html><body><h1>Terms</h1>"
          "<p>All rights reserved. Do not reproduce.</p></body></html>").encode()
    y = yg.kazoeru_kou(en, "text/html; charset=utf-8")
    if y["nihongo"] >= 0.10:
        raise AssertionError(f"英語のページを日本語と見ている（{y['nihongo']}）")
    md = yg.houkoku([{"id": "kou", "mei": "甲社", "top": "https://例.example/",
                      "arika": [{"text": "Terms", "url": "https://例.example/t"}],
                      "yonda": dict(y, url="https://例.example/t"),
                      "robots_top": "許可", "robots_yakusoku": "許可",
                      "hi": "2026-09-21", "note": ""}], "2026-09-21")
    if "日本語なし" not in md:
        raise AssertionError("日本語が無いページで「なし」と並べている")
    if "日本語の規約を読んでいない" not in md:
        raise AssertionError("0の理由についての断りが記録に無い")

    # 日本語のページでは今までどおり
    ja = ("<html><body><h1>サイトポリシー</h1>"
          "<p>当サイトの掲載情報の無断転載を禁じます。</p></body></html>").encode()
    y2 = yg.kazoeru_kou(ja, "text/html; charset=utf-8")
    if y2["nihongo"] < 0.10:
        raise AssertionError(f"日本語のページを英語と見ている（{y2['nihongo']}）")
    md2 = yg.houkoku([{"id": "otsu", "mei": "乙社", "top": "https://例.example/",
                       "arika": [{"text": "規約", "url": "https://例.example/t"}],
                       "yonda": dict(y2, url="https://例.example/t"),
                       "robots_top": "許可", "robots_yakusoku": "許可",
                       "hi": "2026-09-21", "note": ""}], "2026-09-21")
    if "日本語なし" in md2:
        raise AssertionError("日本語のページなのに「日本語なし」と書いている")


def test_やめたことを不可能と書いていないか():
    """**「やめた」と「できない」は別。**

    2026-09-21、テナント企業の経路で追加調査を止める判断が出た。
    **止めた理由は「不可能だから」ではない。**

        分かったこと    初期5社で1社も確認できなかった
        止めた理由      残りを解くのに要る人手とJS対応に対して、いま優先度が低い
        分かっていない  この経路が原理的にだめかどうか

    **「不可能」と書くと、条件のよい相手が見つかっても誰も戻ってこない。**
    実際、統括は「利用条件が明確で CSV/API や静的HTML で出している企業が
    見つかれば再検討する」と言っている。**道を閉じない。**
    """
    import tenanto_kanmon as tk

    doc = tk.__doc__ or ""
    NG = ("不可能", "この経路は使えない", "成立しない", "見込みがない", "無理")
    # **禁じている文と、言っている文を分ける。**
    # 「『不可能』とは記録しない」という行まで捕まえると、
    # **戒めを書けなくなる**（2026-09-21、この検査が自分の文で落ちた）
    YURUSU = ("記録しない", "書かない", "とは言えない", "と読まない", "扱わない")
    for gyou in doc.splitlines():
        if any(y in gyou for y in YURUSU):
            continue
        for ng in NG:
            if ng in gyou:
                raise AssertionError(
                    f"やめたことを「{ng}」と書いている。"
                    f"**分かっていないことを書かない**（{gyou.strip()[:50]}）")
    # **止めたこと自体は書いてあること**（黙ってやめない）
    for iru in ("停止", "初期5社", "再検討"):
        if iru not in doc:
            raise AssertionError(f"止めた記録に「{iru}」が無い")

def test_復元の数え方が先に決まっているか():
    """**測る前に決める。** あとから決めると、都合のいい数え方を選べてしまう。

    2026-09-21、過去の在籍を復元する話になった。**まだ1件も測っていない。**
    測る前に、数え方だけを正本に置いた。捕まえるのは3つ。

    ① 判定は3つだけ。**「どちらも確認できない」を「不在」に寄せない**
    ② **分母を2つに分ける。**「いた」と「いなかった」を1つの割合にしない
    ③ 出どころで**一次と二次を分ける**

    **沈黙が証拠になってはいけない。** リリースに書かれるのは「変化」であって
    「在籍」ではない。10年いる店はどこにも出てこない。
    **出てこないことは、無かったことではない。**
    """
    import fukugen_kata as fk

    eq(len(fk.HANTEI), 3, "判定が3つ以外になっている")
    if "どちらも確認できない" not in fk.HANTEI:
        raise AssertionError("「どちらも確認できない」が無い。**沈黙が証拠になる**")

    # ② 分母が2つ。**全体を1つの割合にしていない**
    n = fk.kazoeru(["在籍を確認できた"] * 3 + ["不在を確認できた"]
                   + ["どちらも確認できない"] * 6)
    eq(round(n["在籍の確認できた率"], 4), round(3 / 9, 4), "在籍の分母がちがう")
    eq(round(n["不在の確認できた率"], 4), round(1 / 7, 4), "不在の分母がちがう")
    for k in n:
        if "率" in k and k not in ("在籍の確認できた率", "不在の確認できた率"):
            raise AssertionError(f"ひとまとめの割合を出している: {k}")

    # **知らない判定は通さない**
    try:
        fk.kazoeru(["たぶんいた"])
    except ValueError:
        pass
    else:
        raise AssertionError("知らない判定を通している")

    # ③ 出どころで一次と二次を分けている
    ichi = [d for d in fk.DEDOKORO if d[2] == "一次"]
    ni = [d for d in fk.DEDOKORO if "二次" in d[2]]
    eq(len(fk.DEDOKORO), 5, "出どころが5つ以外になっている")
    if not ni:
        raise AssertionError("二次情報の欄が無い。**伝聞が一次の顔をする**")
    eq(len(ichi), 4, "一次情報の数がちがう")

    # **この段は取りに行かない**
    src = open(os.path.join(HERE, "fukugen_kata.py"), encoding="utf-8").read()
    for na in ("urlopen", "check_robots", "requests"):
        if na in src:
            raise AssertionError(f"数え方の正本が外に出ようとしている: {na}")


def test_規約未確定を未確認や禁止と混ぜていないか():
    """**読んでいないのか、読んでも決まらなかったのかを分ける。**

    2026-09-21、統括が阪急阪神ホールディングスについて判断を出した——
    robots は許可、④自動取得・⑤DB化の明示的な禁止は語として出てこない。
    それでもコンテンツの利用制限があるため、**「迷ったら止まる」で継続観測は保留。**
    **拒否とも許可とも扱わない。**

    これを既存の2つのどちらに入れても、事実と違うことになる。

        「未確認」に入れる      **まだ調べる余地があるように見える。** 読んだのに
        「取ってはいけない」    **相手が書いていない禁止を、書いてあることにする**

    捕まえるのは3つ。

    ① 語が4つあり、**1か所（関所）だけで持っている**
    ② 数える側が**自前の並びを持っていない**（2か所に書くと必ずずれる）
    ③ 「規約未確定」の施設で、**理由が他の2つの文面にならない**
    """
    import floor_get as fg
    import floor_kanmon as fk

    eq(len(fk.KEKKA), 4, "規約の結果の語が4つ以外になっている")
    for iru in ("取ってよい", "未確認", "規約未確定", "取ってはいけない"):
        if iru not in fk.KEKKA:
            raise AssertionError(f"規約の結果に「{iru}」が無い")

    # ② 数える側が KEKKA を使っているか。**自前で並べていないか**
    src = open(os.path.join(HERE, "floor_get.py"), encoding="utf-8").read()
    if '("取ってよい", "未確認"' in src or '("取ってよい","未確認"' in src:
        raise AssertionError(
            "数える側が語の並びを自前で持っている。**関所の KEKKA を使う**")
    if "KEKKA" not in src:
        raise AssertionError("数える側が KEKKA を読んでいない")

    # ③ 見送りの理由が、他の2つと同じ文面になっていないか
    k = {"id": "test", "mei": "丙モール", "unei": "どこか",
         "top": "https://例.example/", "chizu": "https://例.example/floor",
         "yakusoku": {"mita_hi": "2026-09-21", "kekka": "規約未確定",
                      "riyuu": "読んだが決まらなかった", "url": ""}}
    d = fg.hitotsu(k, {"shisetsu": {}}, "2026-09-21")
    eq(d["kekka"], "見送り", "規約未確定なのに取りに行っている")
    eq(d.get("yakusoku"), "規約未確定", "規約の欄が書き換わっている")
    riyuu = d.get("riyuu", "")
    if "まだ人が読んでいない" in riyuu:
        raise AssertionError("読んだのに「読んでいない」と書いている（ルール⑥）")
    if "**禁じられている**" in riyuu:
        raise AssertionError(
            "相手が書いていない禁止を、書いてあることにしている（ルール⑥）")
    if "規約未確定" not in riyuu:
        raise AssertionError("見送りの理由に「規約未確定」が出ていない")


def test_運営会社の規約を施設の規約の代わりにしていないか():
    """**欄を分ける。片方で他方を代用しない**（robots と規約と同じ形）。

    施設の欄は施設のサイトポリシーで、運営会社の欄は運営会社の規約で決める。
    **同じ運営でも、答えは別々に出る。**

    ここを混ぜると2方向に転ぶ。

        運営が「規約未確定」だから施設も未確定     → **施設の禁止を薄める**
        施設が「取ってはいけない」だから運営も     → **相手が言っていないことを言わせる**

    捕まえるのは、**運営会社の規約を施設の欄の根拠にしていないか**と、
    **記録の上で2つが別の欄に出ているか**。

    **値が同じことは、流れ込んだ証拠にならない。** 2026-09-24、阪急西宮ガーデンズは
    施設のサイトポリシーだけを理由に「規約未確定」へ戻し、運営会社の欄と同じ値になった。
    値の一致で鳴らすと、施設の規約で決めた結果を止めてしまう。**見るのは根拠の在りか。**
    """
    import floor_get as fg
    import floor_kanmon as fk

    if not fk.UNEI_YAKUSOKU:
        raise AssertionError("運営会社の欄が空。**分けたのに何も入っていない**")
    for u in fk.UNEI_YAKUSOKU:
        if u["kekka"] not in fk.KEKKA:
            raise AssertionError(f"運営会社の結果が語の一覧に無い: {u['kekka']}")
        for iru in ("unei", "mei", "mita_hi", "riyuu"):
            if not u.get(iru):
                raise AssertionError(f"運営会社の欄に {iru} が無い: {u['mei']}")

    # **施設の欄が、運営会社の規約を根拠にしていないか**（在りかのホストで見る）
    from urllib.parse import urlparse as _up
    unei_host = {u["unei"]: _up(u.get("url") or "").netloc for u in fk.UNEI_YAKUSOKU}
    for k in fk.KOUHO:
        if not unei_host.get(k.get("unei")):
            continue
        ya = k.get("yakusoku") or {}
        if ya.get("kekka", "未確認") == "未確認":
            continue
        if _up(ya.get("url") or "").netloc == unei_host[k["unei"]]:
            raise AssertionError(
                f"{k['mei']} の欄の根拠が、運営会社の規約（{unei_host[k['unei']]}）になっている。"
                "**施設は施設の規約で決める**")

    # **記録に2つが別の欄で出ているか**
    md = fg.houkoku({"shisetsu": {}}, [], "2026-09-21")
    if "運営会社の側の規約" not in md:
        raise AssertionError("記録に運営会社の欄が出ていない")
    if "施設の規約の代わりにしない" not in md:
        raise AssertionError("代用しないことが記録に書かれていない")
    for u in fk.UNEI_YAKUSOKU:
        if u["mei"] not in md:
            raise AssertionError(f"運営会社の記録に {u['mei']} が出ていない")


def test_保健所の探す段が前の回を消していないか():
    """**1入口だけ回したら、他の入口の行き先が消えた。**

    2026-09-21 に実物で起きた。`--tane-id` で1つだけ走らせたら、
    記録が丸ごと書き直されて、**前の回に拾った他の入口の行き先が消えた。**
    git の履歴には残っていたが、**ためる段が読むのは記録のほう**なので、
    1入口を回すたびに、ためる段の行き先が消えることになる。

    規約の段で同じ形を踏んで直した。**同じ直し方をしたかを見張る。**

    捕まえるのは2つ。

    ① この回で見ていない入口が**台帳に残る**
    ② この回で見た入口は**新しいほうで上書きされる**
    """
    import json as _json
    import tempfile

    import hokenjo_recon as hr

    with tempfile.TemporaryDirectory() as d:
        michi = os.path.join(d, "hokenjo-recon.json")
        mae = [{"id": "kobe-city", "mei": "甲市", "url": "https://例.example/a",
                "mita_hi": "2026-09-20", "tadashi": [], "note": "",
                "file": [{"text": "一覧", "url": "https://例.example/a.csv"}]},
               {"id": "akashi-city", "mei": "乙市", "url": "https://例.example/b",
                "mita_hi": "2026-09-20", "tadashi": [], "note": "",
                "file": [{"text": "一覧", "url": "https://例.example/b.csv"}]}]
        with open(michi, "w", encoding="utf-8") as f:
            _json.dump({"hi": "2026-09-20", "tane": mae}, f, ensure_ascii=False)

        ima = [{"id": "nishinomiya-city", "mei": "丙市",
                "url": "https://例.example/c", "mita_hi": "2026-09-21",
                "file": [], "tadashi": [], "note": "0本"}]
        de = hr.daicho_awaseru(ima, michi)
        idd = {x["id"] for x in de}
        for iru in ("kobe-city", "akashi-city", "nishinomiya-city"):
            if iru not in idd:
                raise AssertionError(
                    f"1入口を回したら {iru} が消えた。**ためる段の行き先が消える**")

        ima2 = [{"id": "kobe-city", "mei": "甲市", "url": "https://例.example/a",
                 "mita_hi": "2026-09-21", "file": [], "tadashi": [], "note": "0本"}]
        de2 = hr.daicho_awaseru(ima2, michi)
        kobe = [x for x in de2 if x["id"] == "kobe-city"][0]
        eq(kobe["mita_hi"], "2026-09-21", "同じ入口が新しい回で上書きされていない")


def test_保健所の生データが公開側に入らないか():
    """**営業者氏名の欄がある。** 公開側に落ちる道を、約束ではなくコードで閉じる。

    正本5節「人の判断ではなくコードで守る」。捕まえるのは4つ。

    ① 生のバイトの置き場が `inbox/` の中（`.gitignore` の内側）
    ② **金庫が無い回は取りに行かない**（`KINKO` が立っていない回）
    ③ workflow が成果物（artifact）に逃がしていない——90日で消えるうえ氏名が入る
    ④ 人が読む記録に、取ってきた中身が混ざっていない
    """
    import hokenjo_get as hg

    if "inbox" not in str(hg.INBOX):
        raise AssertionError(f"生のバイトの置き場が inbox の外にある: {hg.INBOX}")

    moto = os.environ.pop("KINKO", None)
    try:
        yonda = []
        moto_get, moto_robots = hg.get, hg.check_robots
        hg.get = lambda u: yonda.append(u) or (200, "text/csv", b"")
        hg.check_robots = lambda u: yonda.append(u) or (True, "許可")
        try:
            d = hg.hitotsu({"url": "https://例.example/a.csv", "tane_id": "t",
                            "tane_mei": "どこか", "text": "一覧"},
                           {"file": {}}, "2026-09-21")
        finally:
            hg.get, hg.check_robots = moto_get, moto_robots
        if yonda:
            raise AssertionError(
                f"金庫が無いのに {len(yonda)} 回外に出ようとした: {yonda}")
        eq(d["kekka"], "見送り", "金庫が無いのに取りに行っている")
    finally:
        if moto is not None:
            os.environ["KINKO"] = moto

    mita_wf = 0
    for path in workflow_files():
        text = open(path, encoding="utf-8").read()
        if "hokenjo_get.py" not in text:
            continue
        mita_wf += 1
        if "upload-artifact" in text:
            raise AssertionError(
                f"{os.path.basename(path)} が生データを成果物に逃がしている。"
                "**90日で消えるうえ、氏名が入っている**")
        if "KINKO" not in text:
            raise AssertionError(
                f"{os.path.basename(path)} が KINKO を立てていない。"
                "**金庫が無い回に取りに行く形**")
    eq(mita_wf, 1, "ためる段を走らせる workflow が見つからない")

    dai = {"file": {"https://例.example/a.csv": {
        "tane_mei": "どこか", "text": "一覧",
        "mita": [{"hi": "2026-09-21", "yubiwa": "a" * 64, "bytes": 10,
                  "status": 200, "ctype": "text/csv", "hozon": "t-a.csv"}]}}}
    md = hg.houkoku(dai, [], "2026-09-21")
    if "同じホスト" not in md:
        raise AssertionError(
            "同じ相手に同じ日に行くことが記録に書かれていない。**黙って行かない**")
    if "除く" not in md:
        raise AssertionError("対象区域の但し書きが記録に出ていない")


def test_保健所の行き先を作文していないか():
    """**URL を作文しない**（3.4）。行き先は探す段の台帳から読む。

    台帳が空なら**0本のまま終わる。** 思い出して並べない。
    捕まえるのは、**ためる段のコードに行き先が直に書いてある**形。
    """
    import hokenjo_get as hg

    eq(hg.ikisaki(hg.RECON_JSON.parent / "この台帳は無い.json"), [],
       "台帳が無いのに行き先が出てきた（作文している）")

    src = open(os.path.join(HERE, "hokenjo_get.py"), encoding="utf-8").read()
    for i, gyou in enumerate(src.splitlines(), 1):
        migi = gyou.split("#", 1)[0]
        for kuo in ('"', "'"):
            # **`"http"` だけの行は形の判定**（`startswith`）。行き先ではない
            saki = max(migi.find(kuo + "http://"), migi.find(kuo + "https://"))
            if saki < 0:
                continue
            if "例.example" in migi[saki:saki + 40]:
                continue
            raise AssertionError(
                f"ためる段のコードに行き先が直に書いてある（{i}行目）。"
                "**台帳から読む**")


def test_保健所の指紋を長さで代用していないか():
    """**同じ長さで中身が変わる。** 上書き型かどうかを測るのはここ。

    「毎月20日頃に上書き」は**案出しの調査で、こちらは未実測。**
    2回以上見たファイルが出て初めてこちらの数になるので、
    **比べ方がまともかを先に見張る。**

    捕まえるのは2つ。

    ① 指紋が sha256（長さやバイト数で代用していない）
    ② **「はじめて」を「変わっていない」と書かない**
    """
    import hashlib as _h

    import hokenjo_get as hg

    eq(hg.yubiwa(b"abc"), _h.sha256(b"abc").hexdigest(), "指紋が sha256 でない")
    # **同じ長さで中身が違う**ものが、同じ指紋にならないこと
    if hg.yubiwa(b"1234") == hg.yubiwa(b"4321"):
        raise AssertionError("長さで代用している。**同じ長さで中身が変わる**")

    eq(hg.kurabe([], "a" * 64), "はじめて", "前が無いのに「はじめて」と言わない")
    eq(hg.kurabe([{"yubiwa": "a" * 64}], "a" * 64), "変わっていない",
       "同じ指紋を「変わった」と言っている")
    eq(hg.kurabe([{"yubiwa": "a" * 64}], "b" * 64), "**変わった**",
       "違う指紋を「変わっていない」と言っている")

def test_停電の1回見る段が中身を持ち帰っていないか():
    """**発生日時・復旧日時・地域・戸数は、規約が通るまで取らない**（統括の順番）。

    この段が持ち帰ってよいのは3つだけ。

        ページの形        `shitami()` の数字。**店の名前も個票も返さない**
        向こうの見出し    タイトルと h1〜h3。**こちらが名乗らない**（ルール⑥）
        規約の在りか      URL だけ。**取るのは別の段**

    捕まえるのは2つ。

    ① 形を**自前で測っていない**（`shitami()` を通す。2か所に書かない）
    ② 記録に**個票が出ない**
    """
    import teiden_ikkai as ti

    src = open(os.path.join(HERE, "teiden_ikkai.py"), encoding="utf-8").read()
    if "from tenant_recon import shitami" not in src:
        raise AssertionError("形の測り方を自前で書いている。**1か所に置く**")

    # ② 記録に個票が出ないこと。**入れても出ないことを見る**
    kekka = [{"text": "お知らせ", "url": "https://例.example/a", "hi": "2026-09-21",
              "robots": "許可", "kekka": "開けた", "title": "停電履歴",
              "midashi": ["停電履歴"],
              "katachi": {"mieru_moji": 100, "zenbu_moji": 200, "kotei_url": None,
                          "link_katachi": 3},
              # **持ち帰っていたら、ここに入る**
              "honbun": "2026-09-20 14:03 復旧 甲町 1,200戸",
              "saki": [], "yakusoku": []}]
    md = ti.houkoku(kekka, "2026-09-21")
    for ng in ("1,200戸", "14:03", "honbun"):
        if ng in md:
            raise AssertionError(f"記録に個票が混ざっている: {ng}")
    for iru in ("1件も取っていない", "許されたことにしない"):
        if iru not in md:
            raise AssertionError(f"記録に「{iru}」が無い。**黙って進めない**")


def test_停電の1回見る段が他社へ自動的に進んでいないか():
    """**1社で仮説そのものを確かめるまで広げない**（統括・2026-09-21）。

    捕まえるのは3つ。

    ① `--limit` の既定が 1
    ② 辿るのは **2本まで**（`id` や連番を作らない）
    ③ workflow に `schedule` が無い（**押したときだけ**）
    """
    import teiden_ikkai as ti

    src = open(os.path.join(HERE, "teiden_ikkai.py"), encoding="utf-8").read()
    if '"--limit", type=int, default=1' not in src:
        raise AssertionError("1社だけの既定が変わっている。**他社へ自動的に進まない**")
    if ti.MADE > 2:
        raise AssertionError(f"辿る本数が {ti.MADE}。**2本まで**（総当たりに近づく）")

    mita = 0
    for path in workflow_files():
        text = open(path, encoding="utf-8").read()
        if "teiden_ikkai.py" not in text:
            continue
        mita += 1
        if "schedule:" in text:
            raise AssertionError(
                f"{os.path.basename(path)} に schedule がある。"
                "**1回見る段は、押したときだけ**")
    eq(mita, 1, "1回見る段を走らせる workflow が見つからない")


def test_停電の1回見る段が許可を出していないか():
    """**1回見たことを、許されたことにしない**（9節「1回だけ見る」と「毎日取る」）。

    `tenanto_kanmon.py --ikkai` と同じ線。robots が通ったから1回開けた
    というだけで、**毎日取ってよいことにはならない。** 関所が別。

    捕まえるのは、**この段がためる段の関所に触っていないか。**
    """
    src = open(os.path.join(HERE, "teiden_ikkai.py"), encoding="utf-8").read()
    # **禁じている文と、使っている文を分ける。**
    # 「毎日取ってよいことにはならない」という戒めまで捕まえると、
    # **戒めを書けなくなる**（2026-09-21、規約の段で同じ形を踏んだ）
    YURUSU = ("ならない", "しない", "ではない", "別", "関所が")
    for gyou in src.splitlines():
        if any(y in gyou for y in YURUSU):
            continue
        for ng in ("取ってよい", "yakusoku.kekka", "teiden-ledger"):
            if ng in gyou:
                raise AssertionError(
                    f"1回見る段が、ためる段の関所に触っている: {ng}"
                    f"（{gyou.strip()[:50]}）")

    import teiden_ikkai as ti
    md = ti.houkoku([], "2026-09-21")
    if "「0本」は「無い」ではない" not in md:
        raise AssertionError("0本の読み方が記録に書かれていない（9節）")


def test_停電の1回見る段が行き先を作文していないか():
    """**URL を作文しない**（3.4）。行き先は探す段の記録から読む。

    2026-09-21 の探す段は、**記録らしいリンクが9社中1本**だった。
    **その1本だけを通す。** 社名からホストを組み立てない。
    """
    import teiden_ikkai as ti

    # **本番と同じ道**（`teiden_get.yomu()`）を通していること
    src = open(os.path.join(HERE, "teiden_ikkai.py"), encoding="utf-8").read()
    if "from teiden_get import yomu" not in src:
        raise AssertionError("行き先の正本を通っていない。**探す段の記録から読む**")

    for i, gyou in enumerate(src.splitlines(), 1):
        migi = gyou.split("#", 1)[0]
        for kuo in ('"', "'"):
            saki = max(migi.find(kuo + "http://"), migi.find(kuo + "https://"))
            if saki < 0:
                continue
            if "例.example" in migi[saki:saki + 40]:
                continue
            raise AssertionError(
                f"1回見る段のコードに行き先が直に書いてある（{i}行目）")

    # **辿った先は `ikisaki()` に出ない**（開いてみないと分からない）
    de = ti.ikisaki(0)
    eq(de, [], "見る社数が0なのに行き先が出てきた")

def test_書いた台帳を_workflow_が置いてきていないか():
    """**書いたのに、コミットしていない台帳があった。**

    2026-09-21 に実物で起きた。探す段が `data/ref/…json` を書くようにしたのに、
    workflow の `git add` は `.md` だけだった。**台帳は1度も main に出ず、
    次の段が読むと0本になる。**

    ここが効くのは、**落ちないから**。workflow は成功で終わり、記録も更新される。
    **消えているのは、機械しか読まないほうのファイル。**

    捕まえるのは、**その .py が書く `data/ref/*.json` / `*.md` のうち、
    workflow の `git add` に入っていないもの。**

    **捕まえないもの**：金庫（`inbox/`）に置くもの。そちらは別の手順で入る。
    """
    import glob
    import re as _re

    HASHIRU = _re.compile(r"python3?\s+([A-Za-z0-9_./-]+\.py)")
    # `X = … "ref" … "なまえ.json"` の形（os.path.join でも pathlib でも当たる）
    ASSIGN = _re.compile(
        r'^([A-Z][A-Z0-9_]*)\s*=[^\n]*"ref"[^\n]*"([a-z0-9][a-z0-9.-]*\.(?:json|md))"',
        _re.M)
    # `git add data` や `git add -A` は、下の階も含むので通す
    HIROI = _re.compile(r"git add (?:-A\b|[^\n]*\bdata\b(?!/))")

    nai, mita = [], 0
    for path in sorted(workflow_files()):
        text = open(path, encoding="utf-8").read()
        if HIROI.search(text):
            continue
        for name in sorted(set(HASHIRU.findall(text))):
            michi = os.path.join(HERE, name)
            if not os.path.exists(michi):
                continue
            src = open(michi, encoding="utf-8").read()
            for var, fn in ASSIGN.findall(src):
                kaku = (f"{var}.write_text(" in src
                        or _re.search(rf'open\(\s*{var}\s*,\s*"w', src))
                if not kaku:
                    continue          # 読むだけのものは、置いてきても困らない
                mita += 1
                if f"data/ref/{fn}" not in text:
                    nai.append(f"{os.path.basename(path)} → {name} が書く "
                               f"data/ref/{fn}")
    if mita == 0:
        raise AssertionError(
            "書いている台帳が1つも見つからない。数え方が壊れている")
    if nai:
        raise AssertionError(
            "書いたのに、workflow がコミットしていない：\n  "
            + "\n  ".join(nai)
            + "\n  **落ちないので気づかない。** git add に足すこと")

def test_規約の段が電力の在りかを作文していないか():
    """**在りかは、1回見る段が向こうのページから拾ったものだけ。**

    2026-09-21、停電の1社を見たら**規約の在りかが1本**出た。
    そこを読みに行く口を足したが、**URL を組み立てる口は作らない**（3.4）。

    捕まえるのは3つ。

    ① 記録が無ければ **0件で返す**（思い出して並べない）
    ② **いちばん強い1本だけ。** 弱い語まで取りに行かない
    ③ ためる段の関所に触っていない（**1回読めたことを、毎日取る許可にしない**）
    """
    import json as _json
    import tempfile

    import yakusoku_get as yg

    moto = yg.HERE
    with tempfile.TemporaryDirectory() as d:
        try:
            yg.HERE = __import__("pathlib").Path(d)
            eq(yg.taisho("denryoku"), [], "記録が無いのに相手が出てきた（作文）")

            ref = __import__("pathlib").Path(d) / "data" / "ref"
            ref.mkdir(parents=True)
            (ref / "teiden-ikkai.json").write_text(_json.dumps({"hi": "2026-09-21",
                "kekka": [{"title": "甲電力", "url": "https://例.example/a",
                           "yakusoku": [
                               {"text": "利用規約", "url": "https://例.example/rule",
                                "tsuyosa": 0},
                               {"text": "著作権", "url": "https://例.example/copy",
                                "tsuyosa": 9}]}]}, ensure_ascii=False),
                encoding="utf-8")
            de = yg.taisho("denryoku")
            eq(len(de), 1, "相手ごとに1本にまとまっていない")
            eq(de[0]["yakusoku_url"], "https://例.example/rule",
               "いちばん強い1本を選んでいない")
        finally:
            yg.HERE = moto

    # ③ ためる段の台帳に触っていないこと。
    #
    # **語では見ない。** 「取ってよい」は戒めの文にも出る
    # （「利用規約が『取ってよい』になるまで1バイトも開かない」）。
    # 2026-09-21 に同じ形を2回踏んだので、**触る先で見る。**
    src = open(os.path.join(HERE, "yakusoku_get.py"), encoding="utf-8").read()
    for ng in ("teiden-ledger", "floor-ledger", "hokenjo-ledger"):
        if ng in src:
            raise AssertionError(
                f"規約の段が、ためる段の台帳に触っている: {ng}")

def test_構造を見る段が規約で止まった施設に行かないか():
    """**規約で止まった施設には、二度と行かない**（統括・2026-09-21）。

    この段だけ、1回見る段より**関所が1つ多い。**

        ① 規約が「取ってよい」  **人が読んで決めた結果**
        ② robots.txt が許可     この段が毎回見る
        ③ 形を測る              1回だけ

    捕まえるのは3つ。

    ① 「取ってはいけない」が候補に**入らない**
    ② 「未確認」「規約未確定」も**入らない**（人が決めるまで行かない）
    ③ 候補に入らないものは `ikisaki()` にも出ない（＝**取りに行かない**）
    """
    import floor_kanmon as fk
    import shisetsu_kouzou as sk

    for kekka in ("取ってはいけない", "未確認", "規約未確定"):
        mochi = [k["mei"] for k in fk.KOUHO
                 if (k.get("yakusoku") or {}).get("kekka", "未確認") == kekka]
        for mei in mochi:
            if any(d["mei"] == mei for d in sk.erabu()):
                raise AssertionError(
                    f"{mei} は「{kekka}」なのに候補に入っている")

    # **施設を名指ししない。** 規約の欄は人の判断で動く（2026-09-21、実際に動いた）。
    # **いまの欄を読んで確かめる**——名指しすると、判断が変わった日に嘘になる
    dame = [k["id"] for k in fk.KOUHO
            if (k.get("yakusoku") or {}).get("kekka") == "取ってはいけない"]
    for sid in dame:
        eq(sk.erabu(sid), [], f"取ってはいけない施設が候補に入っている: {sid}")
    # **候補に無いものは、行き先にも出ない**
    de = sk.ikisaki(99)
    for u in de:
        mochi = [k for k in fk.KOUHO if k.get("chizu") == u]
        if mochi and (mochi[0].get("yakusoku") or {}).get("kekka") != "取ってよい":
            raise AssertionError(f"規約が通っていないのに行き先に出ている: {u}")


def test_構造を見る段が店の名前を持ち帰っていないか():
    """**入るのは形だけ。値は1つも入らない。**

    **辞書のキーに店名を使う作り**が在りうるので、形だけ見て素通しにしない。

    捕まえるのは3つ。

    ① `katachi_dake()` が**値を返さない**
    ② キーの名前に店名らしい形があれば**伏せる**
    ③ 記録に中身が混ざらない
    """
    import shisetsu_kouzou as sk

    naka = {"shops": [{"name": "甲ショップ", "floor": "2F", "tel": "000"}],
            "甲モール店": {"x": 1}}
    k = sk.katachi_dake(naka)
    moji = json.dumps(k, ensure_ascii=False)
    for ng in ("甲ショップ", "2F", "000"):
        if ng in moji:
            raise AssertionError(f"構造に値が入っている: {ng}")
    if "甲モール店" in moji:
        raise AssertionError("店名らしいキーが伏せられていない")
    if "（店名らしきキー）" not in moji:
        raise AssertionError("伏せた印が出ていない")

    md = sk.houkoku([{"id": "x", "mei": "丁モール", "unei": "どこか",
                      "url": "https://例.example/floor", "hi": "2026-09-21",
                      "yakusoku": "取ってよい", "robots": "許可", "kekka": "見た",
                      "dokokara": "静的HTML", "dokokara_riyuu": "—",
                      "honbun": "1F 甲ショップ／2F 空区画",
                      "kouzou": {"ldjson_kazu": 0, "ldjson_kata": [],
                                 "shirushi": [], "json_saki": [],
                                 "img_kazu": 3,
                                 "shitami": {"mieru_moji": 10, "zenbu_moji": 20,
                                             "mise_katachi": 1,
                                             "kotei_url": None}}}],
                     "2026-09-21")
    for ng in ("甲ショップ", "空区画", "honbun"):
        if ng in md:
            raise AssertionError(f"記録に中身が混ざっている: {ng}")


def test_構造を見る段が在りかを作文していないか():
    """**探しに行かない。組み立てない**（3.4）。

    捕まえるのは4つ。

    ① コードに行き先が直に書いていない
    ② **1レスポンスまで**（2本目を開かない）
    ③ workflow に `schedule` が無い（押したときだけ）
    ④ 分け方が5つある（**「その他」を消さない**）
    """
    import shisetsu_kouzou as sk

    eq(sk.MADE, 1, "1レスポンスを超えて開こうとしている")
    eq(len(sk.DOKOKARA), 5, "分け方が5つ以外になっている")
    if "その他" not in sk.DOKOKARA:
        raise AssertionError("「その他」が無い。**分からないものの置き場を消さない**")

    src = open(os.path.join(HERE, "shisetsu_kouzou.py"), encoding="utf-8").read()
    for i, gyou in enumerate(src.splitlines(), 1):
        migi = gyou.split("#", 1)[0]
        for kuo in ('"', "'"):
            saki = max(migi.find(kuo + "http://"), migi.find(kuo + "https://"))
            if saki < 0:
                continue
            if "例.example" in migi[saki:saki + 40]:
                continue
            raise AssertionError(
                f"構造を見る段のコードに行き先が直に書いてある（{i}行目）")

    mita = 0
    for path in workflow_files():
        text = open(path, encoding="utf-8").read()
        if "shisetsu_kouzou.py" not in text:
            continue
        mita += 1
        if "schedule:" in text:
            raise AssertionError(
                f"{os.path.basename(path)} に schedule がある。**押したときだけ**")
    eq(mita, 1, "構造を見る段を走らせる workflow が見つからない")


def test_条件付きGETを変わっていないと書いていないか():
    """**304 は「相手がそう言った」。こちらは中身を持っていない。**

    統括の決定（2026-09-21）——「ETag / Last-Modified が使える場合は条件付きGET。
    非対応の場合は従来取得へフォールバックし、**最終的な変更判定は従来どおり
    内容の指紋で行う**」。

    捕まえるのは3つ。

    ① 目印は**相手が返したものだけ**（こちらで作らない）
    ② 目印が無ければ**条件付きGETを付けない**（従来どおり取る）
    ③ 304 の回の指紋が **None**（**「変わっていない」と書かない**）
    """
    import hokenjo_get as hg

    eq(hg.shirushi({"mita": []}), ("", ""), "目印が無いのに何か付けようとしている")
    eq(hg.shirushi({"mita": [{"etag": '"abc"'}]}), ('"abc"', ""),
       "相手が返した目印を使っていない")
    # **新しいほうを使う**
    eq(hg.shirushi({"mita": [{"etag": '"a"'}, {"etag": '"b"'}]}), ('"b"', ""),
       "古い目印を使っている")

    src = open(os.path.join(HERE, "hokenjo_get.py"), encoding="utf-8").read()
    for iru in ("If-None-Match", "If-Modified-Since"):
        if iru not in src:
            raise AssertionError(f"条件付きGET の {iru} が無い")

    # ③ 304 の回は、指紋を置かない
    moto = os.environ.get("KINKO")
    os.environ["KINKO"] = "1"
    try:
        moto_get, moto_robots, moto_sleep = hg.get, hg.check_robots, hg.time.sleep
        hg.time.sleep = lambda *a: None
        hg.check_robots = lambda u: (True, "許可")
        hg.get = lambda u, e="", l="": (304, "", None, e, l)
        try:
            dai = {"file": {}}
            with toosu_kado_mon(hg):
                d = hg.hitotsu({"url": "https://例.example/a.csv", "tane_id": "hyogo-pref",
                                "tane_mei": "どこか", "text": "一覧"}, dai, "2026-09-21")
        finally:
            hg.get, hg.check_robots, hg.time.sleep = moto_get, moto_robots, moto_sleep
    finally:
        if moto is None:
            os.environ.pop("KINKO", None)
        else:
            os.environ["KINKO"] = moto

    eq(d["kekka"], "304", "304 を別の結果にしている")
    ki = dai["file"]["https://例.example/a.csv"]["mita"]
    if ki[-1]["yubiwa"] is not None:
        raise AssertionError(
            "中身が来ていないのに指紋を置いている。**取っていないものを測らない**")
    if "変わっていない" == d.get("henka"):
        raise AssertionError(
            "304 を「変わっていない」と書いている。**相手が言っただけ**")
    md = hg.houkoku(dai, [d], "2026-09-21")
    if "こちらは中身を1バイトも持っていない" not in md:
        raise AssertionError("304 の読み方が記録に書かれていない")

def test_開いて0本と開いていないを同じ顔で出していないか():
    """**「0本」は、その道を1回も通っていないときにも出る**（9節）。

    2026-09-21 に実物で並んだ。片方は**トップを開いて規約リンクが0本**、
    もう片方は**相手が混んでいて（HTTP 503）トップを開いていない。**
    表ではどちらも「**0本**」だった。

        開いて0本      語の一覧が足りない／JSで出している。**調べ方の話**
        開いていない   相手が混んでいた・届かなかった。**こちらが見ていない話**

    **次にやることが違う。** 混ぜると、見ていないものを「無い」と読む。

    **429・503 をリトライで突破しない**（3.4）ので、開いていない回は
    **開いていないまま記録に残す。**
    """
    import yakusoku_get as yg

    # 開いていない回（相手が混んでいた）
    mada = {"id": "a", "mei": "甲", "hi": "2026-09-21", "arika": [],
            "yonda": None, "hiraita": False, "robots_top": "許可",
            "note": "相手が混んでいると言っている（HTTP 503）。その回は中止"}
    # 開いて0本だった回
    aita = {"id": "b", "mei": "乙", "hi": "2026-09-21", "arika": [],
            "yonda": None, "hiraita": True, "robots_top": "許可",
            "note": "規約らしいリンクが0本。**無いとは限らない**"}
    md = yg.houkoku([mada, aita], "2026-09-21")

    gyou = {}
    for g in md.splitlines():
        for d in (mada, aita):
            if g.startswith(f"| {d['mei']} |"):
                gyou[d["id"]] = g
    if len(gyou) != 2:
        raise AssertionError("表に2行とも出ていない")
    if gyou["a"].replace(" ", "") == gyou["b"].replace(" ", ""):
        raise AssertionError(
            "開いていない回と、開いて0本だった回が、表で同じ顔をしている")
    if "開いていない" not in gyou["a"]:
        raise AssertionError(
            "開いていない回が「開いていない」と出ていない。"
            "**見ていないものを0本と書かない**")
    if "0本" not in gyou["b"]:
        raise AssertionError("開いて0本だった回が「0本」と出ていない")

def test_規約の文そのものを公開側に出していないか():
    """**相手の規約は相手の著作物。** 分析のために写した分も、外に出さない。

    2026-09-21、統括から「複製・二次利用・自動取得・クローリング・
    スクレイピング・DB化・商用利用を**分けて整理してほしい**」と言われた。
    分けるには**文を見る**必要があるが、**文を公開側に置くのは別の話。**

        公開側   語・回数・どの見出しの下か・同じ文にあった対象語まで
        金庫     該当した文そのもの（**人が読むため**）

    捕まえるのは3つ。

    ① `komaka()` が文を**別の欄**で返す（混ぜない）
    ② 人が読む記録に**文が1つも出ない**
    ③ 文の置き場が `inbox/` の中（`.gitignore` の内側）
    """
    import yakusoku_get as yg

    HON = ("<html><body><h2>著作権について</h2>"
           "<p>本サイトに掲載しているデジタル素材を許可無く無断で複製・"
           "二次利用などする事はできません。</p>"
           "<h2>禁止事項</h2><p>商用のご利用はお断りします。</p>"
           "</body></html>").encode("utf-8")

    km = yg.komaka(HON, "text/html; charset=utf-8")
    if "bun" not in km:
        raise AssertionError("該当した文が別の欄で返っていない")
    if not km["bun"]:
        raise AssertionError("該当した文が1つも拾えていない（分け方が効いていない）")

    fuku = [g for g in km["go"] if g["go"] == "複製"][0]
    eq(fuku["kazu"], 1, "「複製」が数えられていない")
    if "デジタル素材" not in fuku["taishou"]:
        raise AssertionError("同じ文にあった対象語を拾えていない")
    if fuku["jijitsu"]:
        raise AssertionError("事実の語が無いのに在ることにしている")
    if km["kubetsu"]:
        raise AssertionError(
            "分ける文言が無いのに「在った」と書いている。**明示なしは明示なし**")

    # ② 人が読む記録に文が出ないこと
    bun = km.pop("bun")
    d = {"id": "x", "mei": "甲モール", "hi": "2026-09-21", "arika": [{"text": "利用規約", "url": "https://例.example/p"}],
         "hiraita": True, "robots_top": "許可", "robots_yakusoku": "許可",
         "komaka": km,
         "yonda": {"url": "https://例.example/p", "moji": 100, "nihongo": 0.9,
                   "kou": [{"no": str(i), "mei": f"項{i}", "atta": False,
                            "go": [], "kazu": 0, "basho": []}
                           for i in range(1, 6)],
                   "midashi": []}}
    md = yg.houkoku([d], "2026-09-21")
    for b in bun:
        if b in md:
            raise AssertionError(f"人が読む記録に規約の文が出ている: {b[:30]}")
    if "複製" not in md:
        raise AssertionError("語ごとの表が出ていない")

    # ③ 文の置き場
    if "inbox" not in str(yg.INBOX):
        raise AssertionError(f"生の置き場が inbox の外にある: {yg.INBOX}")
    src = open(os.path.join(HERE, "yakusoku_get.py"), encoding="utf-8").read()
    if "jobun-" not in src:
        raise AssertionError("文の置き場が決まっていない")
    for path in workflow_files():
        text = open(path, encoding="utf-8").read()
        if "yakusoku_get.py" not in text:
            continue
        if "data/ref/yakusoku-get.json" not in text:
            raise AssertionError("台帳がコミットされていない")
        if "jobun" in text:
            raise AssertionError("文を公開側にコミットしようとしている")

def test_規約で止まった相手に停電の段が行かないか():
    """**robots が許可でも、規約が断っていれば通さない**（関所が別・正本9節）。

    2026-09-21、統括の判断——九州電力送配電の利用規約の「禁止事項」が、
    **掲載データをプログラム等で機械的に取得する行為を明示的に禁止**している。
    **robots は許可。それとは別に断られている。**

    捕まえるのは4つ。

    ① 「取ってはいけない」の相手が `ikisaki()` に出ない（＝**行かない**）
    ② **robots の欄と規約の欄が別々に残っている**（片方で他方を代用しない）
    ③ **止めたことを黙らない**（0本の理由が記録に出る）
    ④ **この経路が使えないとは書かない**（止めたのはこの相手だけ）
    """
    import teiden_get as tg
    import teiden_recon as tr

    tome = [h for h, v in tr.YAKUSOKU.items() if v["kekka"] == "取ってはいけない"]
    if not tome:
        raise AssertionError("止めた相手が1つも無い。判断が記録に入っていない")

    # ① 行き先に出ない
    import urllib.parse as _up
    for u in tg.ikisaki():
        if _up.urlsplit(u).netloc in tome:
            raise AssertionError(f"規約で止まった相手が行き先に出ている: {u}")

    # ② robots と規約が別の欄
    for h in tome:
        v = tr.YAKUSOKU[h]
        for iru in ("robots", "kekka", "riyuu", "mita_hi"):
            if not v.get(iru):
                raise AssertionError(f"{h} の欄に {iru} が無い")
        if v["robots"] == v["kekka"]:
            raise AssertionError(f"{h} の robots と規約が同じ欄になっている")

    # ③ 止めたことが記録に出る
    md = tg.houkoku([], "2026-09-21", {})
    if "規約で止まっている相手" not in md:
        raise AssertionError("止めた相手が記録に出ていない。**黙って0本にしない**")
    if "robots" not in md:
        raise AssertionError("robots の欄が記録に出ていない")

    # ④ 経路そのものを閉じていない
    NG = ("停電は不可能", "この経路は使えない", "停電DBは成立しない")
    for ng in NG:
        if ng in md:
            raise AssertionError(f"経路そのものを閉じている: {ng}")
    if "この相手だけ" not in md:
        raise AssertionError(
            "止めたのがこの相手だけだと書かれていない。**道を閉じない**")


def test_記録の在りかを_def_のときに固めていないか():
    """**差し替えたつもりの検査が、本物の記録を読み続けていた。**

    2026-09-21 に実物で起きた。`def yomu(michi=RECON)` と書くと、
    既定は **`def` が走ったときの値**で固まる。あとから `mod.RECON` を
    差し替えても、**引数なしで呼ぶ限り本物のファイルを読む。**

    検査は通り続けるが、**見ているものが違う。**
    「処理成功」と「観測成功」を同一視しない、の検査の側の形。

    捕まえるのは、**記録の在りかを既定引数で固めている段。**
    """
    import re as _re

    NAKAMA = ("teiden_get.py", "hokenjo_get.py", "teiden_ikkai.py")
    warui = []
    for na in NAKAMA:
        michi = os.path.join(HERE, na)
        if not os.path.exists(michi):
            continue
        src = open(michi, encoding="utf-8").read()
        for m in _re.finditer(r"def (\w+)\([^)]*=\s*([A-Z][A-Z0-9_]*)\s*[,)]",
                              src):
            if m.group(2) in ("WAIT", "TIMEOUT", "UA", "MADE"):
                continue
            warui.append(f"{na} の {m.group(1)}() が {m.group(2)} を既定で固めている")
    if warui:
        raise AssertionError(
            "記録の在りかを def のときに固めている：\n  " + "\n  ".join(warui)
            + "\n  **呼ばれたときに見る**（michi = michi or RECON）")

def test_相手の言葉とこちらの読みを分けているか():
    """**相手が書いていないことを、書いてあることにしない**（ルール⑥）。

    2026-09-21、統括から「以前の『取ってはいけない』は**強すぎた可能性がある**」
    と言われた。記録を読み直したら、理由の中で

        相手が書いていること   「複製・二次利用などする事はできません」
        **こちらの読み**       「取って保存することが複製、抽出して配ることが二次利用」

    が**地続きに並んでいた。** 後半は**相手はそこまで書いていない。**

    捕まえるのは、**逐語の引用と、こちらの解釈が、印で分かれているか。**

    「取ってはいけない」は**いちばん重い欄**なので、
    **どこまでが相手の言葉かが、あとから分かる形で残っていること。**
    """
    import floor_kanmon as fk

    omoi = [k for k in fk.KOUHO
            if (k.get("yakusoku") or {}).get("kekka") == "取ってはいけない"]
    if not omoi:
        raise AssertionError("「取ってはいけない」が1件も無い。数え方が壊れている")

    for k in omoi:
        ya = k["yakusoku"]
        riyuu = ya.get("riyuu") or ""
        if not riyuu:
            raise AssertionError(f"{k['mei']} の理由が空")
        # **こちらの読みが混ざっているなら、印が要る**
        YOMI = ("と読んだ", "にあたる", "と解した", "とみている")
        if any(y in riyuu for y in YOMI) and "こちらの読み" not in riyuu:
            raise AssertionError(
                f"{k['mei']} の理由で、相手の言葉とこちらの読みが地続きになっている。"
                "**どこまでが相手の言葉かを、印で分ける**（ルール⑥）")


def test_人が画面で読んだだけのものを機械が読んだことにしていないか():
    """**「人が画面で読んだ」と「この箱が読んだ」は別。**

    2026-09-21、統括から「既に確認したサイトポリシーを対象に」と言われたが、
    **こちらは1度も機械で読んでいなかった。** URL すら記録に無かった。
    **「確認した」の主語が違っていた**（ルール⑥）。

    捕まえるのは、**規約の在りかの欄に、URL でないものが入っている形。**
    人が画面で読んだだけなら、**そう書いてあること**（URL の顔をしない）。
    """
    import floor_kanmon as fk

    for k in fk.KOUHO:
        ya = k.get("yakusoku") or {}
        u = ya.get("url") or ""
        if not u:
            continue
        if u.startswith("http"):
            continue
        # URL でないなら、**読んだのが誰かが書いてあること**
        if "人が" not in u and "画面" not in u:
            raise AssertionError(
                f"{k['mei']} の規約の在りかが URL でも、読んだ人の断りでもない: {u}")

def test_1相手ずつ回す段が前の回を消していないか():
    """**1社ずつ回すと、書き直しで前の社が消える。**

    2026-09-21 に3つの段で同じ形を踏んだ（探す段・規約の段・1回見る段）。
    **相手ごとに最後の1回を持つ**形に揃える。

    **この回で見ていない相手も残す**——「見ていない」と「0本だった」は別（9節）。
    """
    import json as _json
    import tempfile
    from pathlib import Path as _P

    import teiden_ikkai as ti

    with tempfile.TemporaryDirectory() as d:
        michi = _P(d) / "teiden-ikkai.json"
        mae = [{"url": "https://甲.example/a", "title": "甲電力", "kekka": "開けた",
                "hi": "2026-09-20", "saki": [], "yakusoku": []}]
        michi.write_text(_json.dumps({"hi": "2026-09-20", "kekka": mae},
                                     ensure_ascii=False), encoding="utf-8")

        ima = [{"url": "https://乙.example/b", "title": "乙電力", "kekka": "開けた",
                "hi": "2026-09-21", "saki": [], "yakusoku": []}]
        de = ti.awaseru(ima, michi)
        host = {__import__("urllib.parse", fromlist=["parse"]).urlsplit(x["url"]).netloc
                for x in de}
        for iru in ("甲.example", "乙.example"):
            if iru not in host:
                raise AssertionError(f"1社ずつ回したら {iru} が消えた")

        # 同じ相手は、新しいほうで上書きされる
        ima2 = [{"url": "https://甲.example/a", "title": "甲電力", "kekka": "開けた",
                 "hi": "2026-09-21", "saki": [], "yakusoku": []}]
        de2 = ti.awaseru(ima2, michi)
        kou = [x for x in de2 if "甲" in x["url"]][0]
        eq(kou["hi"], "2026-09-21", "同じ相手が新しい回で上書きされていない")


def test_相手ごとの台帳を持つ段が揃っているか():
    """**同じ穴を3回踏んだので、形で見張る。**

    1相手ずつ回す段は、**相手ごとに最後の1回を持つ**こと。
    持っていない段は、**回すたびに前の相手が消える。**

    捕まえるのは、**`data/ref/*.json` を書く段のうち、
    前の回を読み直していないもの。**
    """
    import re as _re

    IRU = ("hokenjo_recon.py", "yakusoku_get.py", "teiden_ikkai.py")
    nai = []
    for na in IRU:
        michi = os.path.join(HERE, na)
        if not os.path.exists(michi):
            nai.append(f"{na} が無い")
            continue
        src = open(michi, encoding="utf-8").read()
        # **前の回を読み直しているか。** json.load(s) で自分の台帳を開く形
        if not _re.search(r"json\.load", src):
            nai.append(f"{na} が前の回を読み直していない")
    if nai:
        raise AssertionError(
            "相手ごとの台帳を持っていない段がある：\n  " + "\n  ".join(nai)
            + "\n  **1相手ずつ回すと、前の相手が消える**")

def test_途中で切れた回を大量退店にしていないか():
    """**これがいちばん怖い事故。**

    64店のうち30店しか取れなかった回を「**34店が退店**」と書いてしまうと、
    **あとから直せない。** その日に34店消えた記録が残り、
    **次の回で34店が入店に化ける。** 履歴が二重に壊れる。

    3つの入り方で試す。**どれでも差分を出さないこと。**

        a  取得の層が「切れた」と言えている
        b  取得の層が**何も言っていない**（印が無い）
        c  取得の層が「完全」と言っているのに**中身が欠けている** ← いちばん危ない
    """
    import json as _json

    import floor_sabun as fs

    mae = [{"kai": "2F", "mei": f"店{i:02d}", "gyotai": "x", "ichi": "北"}
           for i in range(1, 65)]

    for nokori in (10, 30, 63):
        ato = mae[:nokori]
        for na, shirushi in (
                ("切れたと分かる", {"todoita": False, "owari": True,
                                    "moto_kensuu": None}),
                ("印が無い", None),
                ("完全と言っている", {"todoita": True, "owari": True,
                                      "moto_kensuu": None})):
            d = fs.sabun(mae, ato, shirushi)
            if d["差分判定"]:
                raise AssertionError(
                    f"{nokori}店しか無いのに差分を確定した（{na}）。"
                    f"**{64 - nokori}店が退店したことにされる**")

    # **原典が件数を言っているなら、それも見る**
    d = fs.sabun(mae, mae[:30], {"todoita": True, "owari": True,
                                 "moto_kensuu": 64})
    if d["観測"]:
        raise AssertionError(
            "原典が「全64件」と言っているのに30件で観測成功にしている")

    # **ふつうの閉店は止めない**（止めすぎると、誰も使わなくなる）
    ato = mae[:30] + mae[31:]
    d = fs.sabun(mae, ato, {"todoita": True, "owari": True, "moto_kensuu": None})
    eq(len(d["taiten"]), 1, "まんなかの1店の退店を拾えていない")
    if not d["差分判定"]:
        raise AssertionError(
            "ふつうの閉店まで止めている。**止めすぎると誰も使わなくなる**")


def test_差分の段が4つの成功を別々に持っているか():
    """**処理・観測・保存・差分判定を、1つにまとめない。**

    上3つが立っても、4つ目は立たないことがある——
    **完全に受け取れていても、差分の形が取得事故に似ている**なら保留する。
    """
    import floor_sabun as fs

    eq(len(fs.SEIKOU), 4, "成功の欄が4つ以外になっている")
    for iru in ("処理", "観測", "保存", "差分判定"):
        if iru not in fs.SEIKOU:
            raise AssertionError(f"成功の欄に「{iru}」が無い")

    mae = [{"kai": "2F", "mei": f"店{i:02d}"} for i in range(1, 65)]
    d = fs.sabun(mae, mae[:30], {"todoita": True, "owari": True,
                                 "moto_kensuu": None})
    for iru in fs.SEIKOU:
        if iru not in d:
            raise AssertionError(f"結果に「{iru}」の欄が無い")
    # **観測は成功、差分判定は失敗**という組み合わせが出せること
    if not (d["観測"] and not d["差分判定"]):
        raise AssertionError(
            "「受け取れたが、差分は出せない」を表せていない。**1つにまとめている**")


def test_固定のしきい値を本番のルールにしていないか():
    """**「前回64店だから、次回60店未満なら失敗」は根拠が無い**（統括・2026-09-21）。

    **何店まで減るのが普通か**は、観測を続けないと分からない（いまは1枚しかない）。
    数ではなく**形**で見る——**消えた店が並びの末尾に固まっているか。**

    捕まえるのは、**差分の段のコードに、店数のしきい値が直に書いてある形。**
    """
    import re as _re

    src = open(os.path.join(HERE, "floor_sabun.py"), encoding="utf-8").read()
    # 人工データの店数（10/30/63/64）と、説明の中の数字は除く
    for i, gyou in enumerate(src.splitlines(), 1):
        migi = gyou.split("#", 1)[0]
        if "def tsukuru" in migi or "nokori in" in migi:
            continue
        m = _re.search(r"(len\(\w+\)|kazu)\s*[<>]=?\s*\d+", migi)
        if m:
            raise AssertionError(
                f"店数のしきい値が直に書いてある（{i}行目・{m.group(0)}）。"
                "**根拠が無い数を本番のルールにしない**")


def test_揃えないと決めた範囲を勝手に揃えていないか():
    """**無理に全部を同一視するルールは作らない**（統括・2026-09-21）。

    揃えるのは、**機械が確実に同じだと言える範囲**だけ。

        揃える    全角/半角の英数・カタカナ・記号、空白の有無、大小
        **揃えない** 長音「ー」と負符号「-」。**別の字**

    揃えすぎると、**本当に別の店を同じ店にしてしまう。**
    そちらは**あとから気づけない**ので、控えめな側に倒す。
    """
    import floor_sabun as fs

    SOROU = [("ＡＢＣ", "ABC"), ("ａｂｃ", "ABC"), ("A B C", "ABC"),
             ("　ABC", "ABC"), ("ｱｲｳ", "アイウ"), ("A･B", "A・B"),
             ("Ａ＆Ｂ", "A&B")]
    for a, b in SOROU:
        if fs.naraberu(a) != fs.naraberu(b):
            raise AssertionError(f"揃うはずのものが揃っていない: {a} / {b}")

    SOROWANU = [("コーヒー", "コ-ヒ-")]
    for a, b in SOROWANU:
        if fs.naraberu(a) == fs.naraberu(b):
            raise AssertionError(
                f"揃えないと決めたものを揃えている: {a} / {b}。"
                "**別の店を同じ店にすると、あとから気づけない**")

    # **状態の表記は外す。** 在籍は在籍
    for s in ("甲店（改装中）", "甲店 一時休業", "甲店（準備中）"):
        na, tsuita = fs.jotai_wo_hazusu(s)
        if not tsuita or fs.naraberu(na) != fs.naraberu("甲店"):
            raise AssertionError(f"状態の表記を外せていない: {s} → {na}")

def test_取得の層が完全かを言えているか():
    """**差分の段は推測しない。取得の層が知っていることを渡す**（2026-09-21）。

    差分検出器を人工データで壊して分かった——一の矢はここ。
    **取得の層が「完全だ」と言えない回は、差分を出さない。**

    捕まえるのは4つ。

    ① 印が3つ揃っている（todoita / owari / moto_kensuu）
    ② **比べられない回を「大丈夫」に倒していない**（圧縮・ヘッダ無し → None）
    ③ **途中で切れた回を捕まえる**（長さが違う／終わりの印が無い）
    ④ **印が台帳に残る**（あとから作れないので、取った回に書く）
    """
    import floor_get as fg

    MARU = '<html><body>ABC 全 64 件</body></html>'.encode()

    # ① 完全な回
    d = fg.kansei_no_shirushi(MARU, {"Content-Length": str(len(MARU)),
                                     "Content-Type": "text/html; charset=utf-8"},
                              False)
    for iru in ("todoita", "owari", "moto_kensuu"):
        if iru not in d:
            raise AssertionError(f"印に {iru} が無い")
    eq(d["todoita"], True, "完全な回を完全と言えていない")
    eq(d["owari"], True, "終わりの印を見ていない")
    eq(d["moto_kensuu"], 64, "原典が言っている件数を拾えていない")

    # ② **分からない回を True に倒さない**
    for na, atama in (("圧縮", {"Content-Length": "20", "Content-Encoding": "gzip"}),
                      ("ヘッダ無し", {})):
        d = fg.kansei_no_shirushi(MARU, atama, False)
        if d["todoita"] is True:
            raise AssertionError(
                f"{na}で比べられないのに「届いた」と言っている。"
                "**分からないを大丈夫に倒さない**")

    # ③ 途中で切れた回
    kire = '<html><body>AB'.encode()
    d = fg.kansei_no_shirushi(kire, {"Content-Length": "999"}, False)
    eq(d["todoita"], False, "長さが違うのに気づいていない")
    d = fg.kansei_no_shirushi('<html><body>ABC'.encode(),
                              {"Content-Length": "15"}, False)
    eq(d["owari"], False, "終わりの印が無いのに在ることにしている")
    d = fg.kansei_no_shirushi(None, {}, True)
    eq(d["todoita"], False, "読んでいる途中で切れた回を捕まえていない")

    # ④ 台帳に残る
    dai = {"shisetsu": {}}
    fg.daicho_kaku(dai, [{"id": "x", "mei": "甲", "unei": "—", "kekka": "取れた",
                          "yubiwa": "a" * 64, "bytes": 10, "hozon": "h",
                          "koukai": "原典で見えた", "henka": "はじめて",
                          "kansoku": True,
                          "kansei": {"todoita": True, "owari": True,
                                     "moto_kensuu": None}}], "2026-09-21")
    ki = dai["shisetsu"]["x"]["kiroku"][0]
    if "kansei" not in ki or "kansoku" not in ki:
        raise AssertionError(
            "印が台帳に残っていない。**あとから作れないので、取った回に書く**")

    # **差分の段が、この印をそのまま受け取れること**
    import floor_sabun as fs
    mae = [{"kai": "2F", "mei": f"店{i}"} for i in range(64)]
    d = fs.sabun(mae, mae[:30], ki["kansei"])
    if d["差分判定"]:
        raise AssertionError("印を渡しても差分を止められていない")

def test_第1観測を差分0件と書いていないか():
    """**比べる相手が無い回は「差分未判定」。**

    2026-09-21、統括の指摘で見つかった。**大量退店の裏返し**だった——
    前が無い回に差分を出すと、**64店が「入店した」ことになる。**

        **書いてよい**   差分未判定（比べる相手が無い）
        **書かない**     差分0件／変化なし

    **何も起きていないとは言えない。** 見ていない間のことは分からない。
    """
    import floor_sabun as fs

    ato = [{"kai": "2F", "mei": f"店{i}"} for i in range(64)]
    MARU = {"todoita": True, "owari": True, "moto_kensuu": None}
    d = fs.sabun([], ato, MARU)

    eq(len(d["hairi"]), 0, "第1観測で入店を出している。**全部が新規に見える**")
    eq(len(d["taiten"]), 0, "第1観測で退店を出している")
    eq(d["差分判定"], False, "比べる相手が無いのに差分を確定している")
    eq(d.get("hatsu"), True, "第1観測だと分かる欄が無い")
    for ng in ("差分0件", "変化なし", "変わっていない"):
        # **戒めの文は飛ばす。**「とは書かない」まで捕まえると戒めが書けない
        nokori = iikae_wo_nozoku(d.get("riyuu") or "", ng)
        if nokori:
            raise AssertionError(
                f"第1観測に「{ng}」と書いている（{nokori[0][:40]}）")
    if "未判定" not in (d.get("riyuu") or ""):
        raise AssertionError("「差分未判定」と書かれていない")


def test_完全かを1条件で断定していないか():
    """**「`</html>` があるから絶対完全」と書かない**（統括・2026-09-21）。

    **印ごとに、何を保証して、何を保証しないかを並べて残す。**

        Content-Length 一致  **相手の申告と一致した**ことは言える
                             **相手の申告そのものが途中まで**なら分からない
        `</html>` が在る     **末尾が届いている**ことは言える
                             **途中の要素が欠けていても末尾は在りうる**
        指紋                 **同じバイトか**は言える。**完全かは言えない**

    捕まえるのは3つ。

    ① 印ごとに「保証する／保証しない」が付いている
    ② **1条件だけで「完全」にしていない**（2つ以上を見ている）
    ③ **あとから検証できる欄がある**（時刻・指紋・版・ETag など）
    """
    import floor_get as fg

    raw = '<html><body><a href="/s/1">甲</a> 全 64 件</body></html>'.encode()
    d = fg.kansei_no_shirushi(
        raw, {"Content-Length": str(len(raw)),
              "Content-Type": "text/html; charset=utf-8",
              "ETag": '"x"', "Last-Modified": "Sun, 21 Sep 2026 00:00:00 GMT"},
        False, base="https://例.example/floor")

    # ① 保証の欄
    ha = d.get("hosho") or []
    if len(ha) < 3:
        raise AssertionError("印ごとの保証の欄が足りない")
    for h in ha:
        for iru in ("na", "kekka", "保証する", "保証しない"):
            if iru not in h:
                raise AssertionError(f"保証の欄に {iru} が無い: {h.get('na')}")
        if not h["保証しない"]:
            raise AssertionError(
                f"「保証しない」が空: {h['na']}。**1条件で断定している**")

    # ② 終わりの印だけでは完全にしない
    owari_dake = fg.kansei_no_shirushi(raw, {}, False)   # Content-Length 無し
    if owari_dake["todoita"] is True:
        raise AssertionError(
            "Content-Length が無いのに「届いた」と言っている。"
            "**1条件で断定しない**")

    # ③ あとから確かめられる欄
    for iru in ("parser", "totta_nichiji", "raw_hash", "etag", "last_modified",
                "bytes", "parsed_count", "katachi_kazu", "moto_kensuu"):
        if iru not in d:
            raise AssertionError(f"あとから確かめるための欄が無い: {iru}")
    # **読み取っていない段が、読み取った数を名乗らない**
    if d["parsed_count"] is not None:
        raise AssertionError(
            "読み取らない段が parsed_count を埋めている。"
            "**形の繰り返しの数と、店の数を混ぜない**")


def test_規約の条件を記録に残しているか():
    """**条件付きで戻した相手は、条件も一緒に残す**（統括・2026-09-21）。

    「取ってよい」だけを残すと、**なぜ良いのかが消える。**
    条件が守れなくなったときに、**戻る場所が無くなる。**
    """
    import floor_kanmon as fk

    yoi = [k for k in fk.KOUHO
           if (k.get("yakusoku") or {}).get("kekka") == "取ってよい"]
    if not yoi:
        return                     # **まだ1件も無い。それ自体は問題ではない**
    for k in yoi:
        ya = k["yakusoku"]
        if not ya.get("mita_hi"):
            raise AssertionError(f"{k['mei']}：読んだ日が入っていない")
        if not ya.get("url", "").startswith("http"):
            raise AssertionError(f"{k['mei']}：規約の在りかが URL でない")
        if not ya.get("riyuu"):
            raise AssertionError(f"{k['mei']}：理由が空")
        if not ya.get("jouken"):
            raise AssertionError(
                f"{k['mei']}：**条件が残っていない。**"
                "なぜ良いのかが消えると、戻る場所が無くなる")

def test_1枚を全部だと思っていないか():
    """**転送も文書も完全なのに、原典の一部しか入っていない**形がある。

    2026-09-21、正式第1観測で出た。**1枚に32店。原典は「314件」と言っていた。**
    ページ送りが10枚ぶん在った。

        転送      完全
        文書      完全（`</html>` あり）
        **中身**  **原典の1割しか入っていない**

    **たまたま安全側に倒れて助かった**（Content-Length が無かったので
    「分からない」で止まった）。**付いていたら「完全」と書いていた。**

    捕まえるのは2つ。

    ① **数字と単位の間にタグが入っていても、原典の件数を拾う**
       （`検索結果<span>314</span>件` を取りこぼしていた）
    ② **ページ送りが見えたら、その1枚では完全にしない**
    """
    import floor_get as fg

    # ① タグが割り込んだ件数
    HON = ('<html><body><p class="result">検索結果<span>314</span>件</p>'
           '</body></html>').encode()
    d = fg.kansei_no_shirushi(HON, {"Content-Type": "text/html; charset=utf-8"},
                              False)
    eq(d["moto_kensuu"], 314,
       "数字と単位の間にタグが入ると、原典の件数を取りこぼす")

    # ② ページ送り
    PAGE = ('<html><body><a href="/shopguide?page=2">2</a>'
            '<a href="/shopguide?page=10">10</a></body></html>').encode()
    d2 = fg.kansei_no_shirushi(PAGE, {"Content-Length": str(len(PAGE)),
                                      "Content-Type": "text/html"}, False)
    eq(d2["pager"], 10, "ページ送りを数えられていない")
    eq(d2["todoita"], True, "長さは合っているのに「届いていない」にしている")
    eq(d2["owari"], True, "終わりの印があるのに見ていない")
    # **転送も文書も完全。それでも「完全」にしない**
    ha = {h["na"]: h["kekka"] for h in d2["hosho"]}
    if ha.get("ページ送りが無いか") is not False:
        raise AssertionError(
            "ページ送りが見えているのに、保証の欄が立っている")
    if "全部ではない" not in (d2.get("wake") or ""):
        raise AssertionError("1枚が全部ではないことが書かれていない")

    # ③ **印の版を上げているか**（作り方を変えたら上げる）
    if fg.INSHI_VERSION == "kansei-2":
        raise AssertionError(
            "印の作り方を変えたのに版が上がっていない。"
            "**古い記録を新しい作り方で読んだつもりにならないため**")

def test_抜いた結果に図形が入っていないか():
    """**図形・画像そのものは保存資産にしない**（統括・2026-09-21）。

    必要なのは**識別子・属性・事実**であって、図ではない。
    **捨てると決めたものは、捨てたことを毎回確かめる**（言うだけにしない）。

    捕まえるのは3つ。

    ① 抜いた結果に **座標・`d`・`points`・`svg` が1つも無い**
    ② **店の側のIDと、場所の側のIDが別の欄**
    ③ **場所の側を、こちらの確定IDと呼んでいない**
    """
    import json as _json

    import floor_chushutsu as fc

    HON = ('<html><body>'
           '<option data-detail-url="https://x/shopguide/detail/147"'
           ' data-floor-id="2" value="map10201"'
           ' data-shop-name="甲店"'
           ' data-connection-value="shopName=甲店/floorId=2/value=map10201"'
           ' data-sub-search="こう">甲店</option>'
           '<option value="map_stairs_1f"'
           ' data-connection-value="shopName=階段（本館1F）/floorId=1'
           '/value=map_stairs_1f">階段</option>'
           '<svg viewBox="0 0 825 802"><a href="https://x/shopguide/detail/147"'
           ' class="map10201"><polygon class="cls-6" points="352.95 482.06 347 463.38"/>'
           '</a></svg>'
           '</body></html>').encode()

    d = fc.chushutsu(HON, "text/html; charset=utf-8")

    # ① 図形が混ざっていない
    warui = fc.zukei_ga_haitteinaika(d)
    if warui:
        raise AssertionError(f"抜いた結果に図形が混ざっている: {warui}")
    moji = _json.dumps(d, ensure_ascii=False)
    for ng in ("352.95", "482.06", "cls-6"):
        if ng in moji:
            raise AssertionError(f"座標や描き方が残っている: {ng}")

    # ② 別の欄
    eq(len(d["mise"]), 1, "店を拾えていない")
    m = d["mise"][0]
    eq(m["shop_source_id"], "147", "店の側のIDを拾えていない")
    eq(m["map_id_candidate"], "map10201", "場所の側の候補を拾えていない")
    if m["shop_source_id"] == m["map_id_candidate"]:
        raise AssertionError("店の側と場所の側が同じ欄になっている")
    eq(m["floor_id"], "2", "階を拾えていない")
    eq(m["tatemono_kigou"], "map", "館の記号を拾えていない")

    # 共用部の側
    eq(len(d["kyoyou"]), 1, "店と結びついていないものを拾えていない")
    if "shop_source_id" in d["kyoyou"][0]:
        raise AssertionError("店と結びついていないのに、店のIDの欄がある")

    # ③ 確定IDと呼んでいない
    # **戒めの文は飛ばす**（「unit_id にしない」まで捕まえると戒めが書けない）。
    # 2026-09-21、同じ形を**6回**踏んだ。**道具が在るのに使い忘れた**
    src = open(os.path.join(HERE, "floor_chushutsu.py"), encoding="utf-8").read()
    nokori = iikae_wo_nozoku(src, "unit_id")
    if nokori:
        raise AssertionError(
            f"場所の側を unit_id（確定ID）と呼んでいる（{nokori[0][:40]}）")
    for key in ("mise", "kyoyou"):
        for r in d[key]:
            if "unit_id" in r:
                raise AssertionError("抜いた結果に unit_id の欄がある")


def test_空き区画の数を推測していないか():
    """**「394 − 314 = 80 だから80空き区画」とは推測しない**（統括・2026-09-21）。

    店と結びついていない `map_id_candidate` は、
    **共用部・設備・重複・別用途・実装上の要素**のことがある。

    **語で分けて数えるところまで。判定はしない。**
    """
    import floor_chushutsu as fc

    # 語で分けられること
    eq(fc.bunrui("階段（本館1F）"), "階段", "階段を分けられていない")
    eq(fc.bunrui("みんなのトイレ"), "トイレ", "トイレを分けられていない")
    # **どれにも当たらなければ「分からない」。**勝手に空きにしない
    eq(fc.bunrui("なにかの名前"), "分からない",
       "分からないものを、分かったことにしている")

    src = open(os.path.join(HERE, "floor_chushutsu.py"), encoding="utf-8").read()
    for ng in ("空き区画", "空区画", "空きテナント"):
        nokori = iikae_wo_nozoku(src, ng)
        if nokori:
            raise AssertionError(
                f"「{ng}」と書いている（{nokori[0][:40]}）。**推測しない**")

def test_観測元が変わった回を前と比べていないか():
    """**別のページ同士を比べると、中身と関係なく全部が入れ替わって見える。**

    2026-09-21、統括の判断で観測元を替えた日に出かけた。
    台帳は**施設ごと**なので、そのままだと
    **ショップガイドの回とフロアのページの回を比べる。**
    指紋は当然ちがうので「**変わった**」と出る。**中身は無関係なのに。**

    **大量退店・全部入店と同じ家族の事故。**

    捕まえるのは3つ。

    ① 台帳に**観測元のURL**が残る
    ② **観測元がちがう前の回とは比べない**（「はじめて」に倒す）
    ③ **観測元が入っていない古い記録**も、比べる相手にしない
    """
    import floor_get as fg

    b = b"<html><body>x</body></html>"
    MARU = {"todoita": True, "owari": True, "moto_kensuu": None}
    moto_robots, moto_get, moto_sleep = fg.check_robots, fg.get, fg.time.sleep
    try:
        fg.time.sleep = lambda *a: None
        fg.check_robots = lambda u: (True, "許可")
        fg.get = lambda u: (200, b, "", MARU)
        k = {"id": "kou", "mei": "甲モール", "unei": "甲",
             "chizu": "https://例.example/floor/1",
             "yakusoku": {"mita_hi": "2026-09-21", "kekka": "取ってよい",
                          "riyuu": "", "url": ""}}

        with toosu_kado_mon(fg):
            # ② 前の回が**別のページ**
            dai = {"shisetsu": {"kou": {"mei": "甲", "kiroku": [
                {"hi": "2026-09-20", "yubiwa": "a" * 64,
                 "moto_url": "https://例.example/shopguide"}]}}}
            d = fg.hitotsu(k, dai, "2026-09-21")
            if d["henka"] == "**変わった**":
                raise AssertionError(
                    "観測元がちがうのに「変わった」と書いている。"
                    "**中身と関係なく全部が入れ替わって見える**")
            if "観測元が変わった" not in d["henka"]:
                raise AssertionError(f"観測元が変わったと書かれていない: {d['henka']}")

            # ③ 前の回に**観測元が入っていない**（古い記録）
            dai2 = {"shisetsu": {"kou": {"mei": "甲", "kiroku": [
                {"hi": "2026-09-20", "yubiwa": "a" * 64}]}}}
            d2 = fg.hitotsu(k, dai2, "2026-09-21")
            if d2["henka"] == "**変わった**":
                raise AssertionError(
                    "観測元が分からない記録と比べている。**分からないを大丈夫に倒さない**")

        # ① 台帳に残る
        dai3 = {"shisetsu": {}}
        fg.daicho_kaku(dai3, [dict(d, kekka="取れた", yubiwa="b" * 64, bytes=9,
                                   hozon="h", koukai="原典で見えた")], "2026-09-21")
        ki = dai3["shisetsu"]["kou"]["kiroku"][0]
        if not ki.get("moto_url"):
            raise AssertionError("台帳に観測元のURLが残っていない")

        # **同じページなら、ちゃんと「変わった」と言えること**（止めすぎない）
        with toosu_kado_mon(fg):
            dai4 = {"shisetsu": {"kou": {"mei": "甲", "kiroku": [
                {"hi": "2026-09-20", "yubiwa": "a" * 64,
                 "moto_url": "https://例.example/floor/1"}]}}}
            d4 = fg.hitotsu(k, dai4, "2026-09-21")
        eq(d4["henka"], "**変わった**",
           "同じページなのに「変わった」と言えていない。**止めすぎている**")
    finally:
        fg.check_robots, fg.get, fg.time.sleep = moto_robots, moto_get, moto_sleep

def iikae_wo_nozoku(text, ng):
    """**禁じている文と、言っている文を分ける。**

    2026-09-21、同じ形を**5回**踏んだ。
    「『差分0件』とは書かない」という**戒め**まで捕まえると、
    **戒めを書けなくなる。**

    その語を含む文を取り出して、**打ち消しの言い回しが同じ文にあれば飛ばす。**
    残った文だけを返す。**残りが空なら、言っていない。**
    """
    import re as _re

    # **打ち消しの言い回し。** ここに当たる文は「言っている」ではなく「戒め」。
    #
    # **広すぎると、本当の違反を見逃す。** 「ていない」は広いが、
    # 日本語の打ち消しとしては外せない（2026-09-21、
    # 「空き区画の数を**出していない**」という戒めが捕まった）。
    # **広さと見逃しは取引**なので、ここを直すときは両方を見る。
    KESHI = ("書かない", "とも", "とは", "しない", "ではない", "ならない",
             "記録しない", "と読まない", "扱わない", "名乗らない",
             "ていない", "呼ばない", "数えない", "入れない")
    nokori = []
    for bun in _re.split(r"[。\n]", text or ""):
        if ng not in bun:
            continue
        if any(k in bun for k in KESHI):
            continue
        nokori.append(bun.strip())
    return nokori



def test_地図_年度をファイル名から読んでいるか():
    """**読めなかった年度を 0 にも今年にもしない**（推測で欠損を埋めない）。

    統括の条件（2026-09-21）に「推測で欠損を埋めないこと」がある。
    年度はファイル名にしか書かれていないので、**読めたときだけ入れる。**
    """
    import chizu_get as cg
    eq(cg.nendo("27102-1203-2025.zip"), 2025, "ファイル名から年度を読めていない")
    eq(cg.nendo("27102-1203-2025.Zip"), 2025, "大文字の .Zip を読めていない")
    for warui in ("", None, "houmusyouchizu.zip", "27102-2025.zip",
                  "27102-1203-2025.xml"):
        eq(cg.nendo(warui), None,
           f"読めない名（{warui!r}）から年度を作っている。**推測で埋めている**")


def test_地図_URLを組み立てていないか():
    """**向こうが書いた URL をそのまま使う**（正本9節「作文しない」）。

    リソース名は `{市区町村コード}-{登記所コード}-{年度}.zip` の形だが、
    **登記所コードは手元に無い。** 当てに行くと作文になる。
    目録の記録に載っている URL を、**1文字も変えずに**持ち出せること。
    """
    import tempfile, os as _os
    import chizu_get as cg
    URL = ("https://www.geospatial.jp/ckan/dataset/"
           "2759b37d-8c09-4536-b758-b6c2ad04bb79/resource/"
           "164ffe37-8144-4042-a31b-a7df006dc93e/download/27102-1203-2025.zip")
    body = ("| 市区町村 | データセット | リソース | 形式 | 置き場 |\n"
            "|---|---|---|---|---|\n"
            f"| `27102` 大阪府大阪市都島区 | ある目録 | 27102-1203-2025.zip "
            f"| ZIP | {URL} |\n")
    with tempfile.TemporaryDirectory() as d:
        michi = _os.path.join(d, "recon.md")
        open(michi, "w", encoding="utf-8").write(body)
        rows, yomenai = cg.mokuroku(michi)
    eq(len(rows), 1, "目録の記録から1行も読めていない")
    eq(yomenai, 0, "読めなかった行を数えていない")
    eq(rows[0]["url"], URL, "URL が変わっている。**そのまま使っていない**")
    eq(rows[0]["dataset_id"], "2759b37d-8c09-4536-b758-b6c2ad04bb79",
       "取得元データセットID を URL から読めていない")
    eq(rows[0]["nendo"], 2025, "年度を読めていない")


def test_地図_同じ市区町村同じ年度の重なりを拾えるか():
    """**データセットID が違えば別の目録。** ファイル名が同じでも同一と読まない。

    それを確かめるのが案B（統括・2026-09-21）。**先に「同じ」と決めない。**
    """
    import chizu_get as cg
    def r(code, nen, ds, fmt="ZIP"):
        return {"code": code, "nendo": nen, "dataset_id": ds, "format": fmt,
                "name": "どこかの市", "filename": f"{code}-1203-{nen}.zip"}
    rows = [r("27102", 2025, "A"), r("27102", 2025, "B"),   # 重なり
            r("27102", 2024, "A"),                            # 1本だけ
            r("27103", 2025, "A"), r("27103", 2025, "A"),   # 同じ目録＝重なりでない
            r("27104", 2025, "A", "PDF"), r("27104", 2025, "B", "PDF")]
    k = dict(cg.kasanari(rows))
    eq(("27102", 2025) in k, True, "重なっている組を拾えていない")
    eq(("27102", 2024) in k, False, "1本しか無い組を重なりにしている")
    eq(("27103", 2025) in k, False,
       "同じデータセットID を2本と数えている。**目録は1つ**")
    eq(("27104", 2025) in k, False, "ZIP でないものを組にしている")
    eq(len(k[("27102", 2025)]), 2, "組の中の本数が合わない")


def test_地図_比べる相手が欠けたら未判定か():
    """**1つでも見えていなければ「一致」と書かない**（正本9節）。

    「大きさと SHA が同じ。zip は開けなかった」を**一致**と書くと、
    **開けなかったことが「同じだった」に化ける。**
    """
    import chizu_get as cg
    MARU = {"bytes": 10, "sha256": "a", "nakami_yubiwa": "z"}
    eq(cg.kuraberu(MARU, dict(MARU))[0], "一致", "3つそろって同じなのに一致でない")

    kake = dict(MARU, nakami_yubiwa=None)
    h, onaji, chigau, mienai = cg.kuraberu(MARU, kake)
    eq(h, "未判定", "zip を開けなかったのに一致と書いている")
    eq("zip の中の一覧" in mienai, True, "見えなかった欄を数えていない")
    eq(len(onaji), 2, "見えた欄まで落としている")

    # **見えない欄があっても、見えている欄が違えば「不一致」。**
    # 未判定に倒すと、違いが「分からない」に化ける
    eq(cg.kuraberu(MARU, dict(MARU, bytes=11, nakami_yubiwa=None))[0],
       "不一致", "違いが見えているのに未判定にしている")
    eq(cg.kuraberu({"bytes": None, "sha256": None, "nakami_yubiwa": None},
                   dict(MARU))[0], "未判定", "何も見えていないのに判定している")


def test_地図_一致は3つそろったときだけか():
    """大きさ・SHA-256・zip の中の一覧。**どれか1つ違えば不一致。**"""
    import chizu_get as cg
    MARU = {"bytes": 10, "sha256": "a", "nakami_yubiwa": "z"}
    for kae in ({"bytes": 11}, {"sha256": "b"}, {"nakami_yubiwa": "y"}):
        eq(cg.kuraberu(MARU, dict(MARU, **kae))[0], "不一致",
           f"{list(kae)[0]} が違うのに不一致にしていない")


def test_地図_zipが開けないときに0件と書いていないか():
    """**0件は「中が空だと向こうが言った」。** 開けなかったのは None。

    混ぜると、**こちらが開けなかったことが「空だった」に見える**（6節）。
    """
    import tempfile, os as _os, zipfile as _z
    import chizu_get as cg
    with tempfile.TemporaryDirectory() as d:
        kara = _os.path.join(d, "kara.zip")
        with _z.ZipFile(kara, "w"):
            pass
        n, yubi, riyuu = cg.nakami(kara)
        eq(n, 0, "中が空の zip を0件と読めていない")
        eq(riyuu, None, "開けたのに理由を書いている")
        eq(yubi is not None, True, "空でも一覧の指紋は出るはず")

        aru = _os.path.join(d, "aru.zip")
        with _z.ZipFile(aru, "w") as z:
            z.writestr("a.xml", "x" * 10)
            z.writestr("b.xml", "y" * 20)
        n2, yubi2, _ = cg.nakami(aru)
        eq(n2, 2, "中のファイル数を数えられていない")
        eq(yubi2 != yubi, True, "中身が違うのに一覧の指紋が同じ")

        kowareta = _os.path.join(d, "kowareta.zip")
        open(kowareta, "wb").write("これは zip ではない".encode("utf-8"))
        n3, yubi3, riyuu3 = cg.nakami(kowareta)
        eq(n3, None, "開けなかったのに件数を返している。**0件に化ける**")
        eq(yubi3, None, "開けなかったのに指紋を返している")
        eq(bool(riyuu3), True, "開けなかった理由を残していない")


def test_地図_1組の一致を全部に広げていないか():
    """**1組一致しただけで、全市区町村・全年度が同一とは一般化しない**
    （統括・2026-09-21）。書く側の文にその戒めが入っていること。
    """
    import chizu_get as cg
    kumi = [{"code": "27102", "nendo": 2025, "name": "大阪市都島区",
             "hantei": "一致", "onaji": ["大きさ"], "chigau": [], "mienai": [],
             "a": {"bytes": 1, "sha256": "a" * 64, "nakami_kensuu": 1,
                   "nakami_yubiwa": "z" * 64, "dataset_id": "A"},
             "b": {"bytes": 1, "sha256": "a" * 64, "nakami_kensuu": 1,
                   "nakami_yubiwa": "z" * 64, "dataset_id": "B"}}]
    import tempfile, os as _os
    with tempfile.TemporaryDirectory() as d:
        lines = cg.kaku([], kumi, 2, 0,
                        report=_os.path.join(d, "g.md"),
                        daicho=_os.path.join(d, "g.json"))
    bun = "\n".join(lines)
    if "一般化しない" not in bun:
        raise AssertionError("1組の結果を広げない、という戒めが記録に無い")
    if "まだ取っていない組" not in bun:
        raise AssertionError(
            "取っていない組を数えていない。**0にすると「無い」に見える**")


def test_地図_規約とrobotsを別の欄にしているか():
    """**片方で他方を代用しない**（正本9節）。

    規約が「取ってよい」でも、robots が拒んでいたら取りに行かない。
    逆に robots が許していても、規約が禁じていたら取りに行かない。
    """
    import chizu_get as cg
    eq(cg.YAKUSOKU["kekka"] in cg.KEKKA, True,
       f"規約の結果が4語のどれでもない（{cg.YAKUSOKU['kekka']}）")
    eq("robots" not in cg.YAKUSOKU, True,
       "規約の欄に robots を混ぜている。**別の欄にする**")
    src = open(os.path.join(HERE, "chizu_get.py"), encoding="utf-8").read()
    if "check_robots" not in src:
        raise AssertionError("規約だけ見て robots を見ていない")
    if 'YAKUSOKU["kekka"] != "取ってよい"' not in src:
        raise AssertionError("robots だけ見て規約の欄を見ていない")


def test_地図_個人を識別する突合を禁止と書いているか():
    """規約の禁止の線を、**逐語で**持っていること（統括・2026-09-21）。

    「取得したコンテンツについて、他の情報と照合する等して
    特定の個人を識別する行為」は禁止。**法人は当たらない。個人は結ばない。**
    """
    import chizu_get as cg
    bun = "／".join(cg.YAKUSOKU["kinshi"])
    for kotoba in ("特定の個人を識別", "照合"):
        if kotoba not in bun:
            raise AssertionError(f"禁止の線に「{kotoba}」が無い")
    if "妨害" not in bun:
        raise AssertionError("サーバ・ネットワークの妨害の線が無い")


def test_地図_出典の8つが記録に入るか():
    """規約は出典の表示を求めている。**8つが台帳に残ること。**

    データセット名／市区町村／年度／元URL／取得日／
    取得元データセットID／ファイル名／SHA-256
    """
    import chizu_get as cg
    rec = {"dataset": "ある目録", "code": "27102", "name": "大阪市都島区",
           "nendo": 2025, "url": "https://example.invalid/x.zip",
           "totta_hi": "2026-09-21", "dataset_id": "A" * 36,
           "filename": "27102-1203-2025.zip", "sha256": "b" * 64,
           "status": 200}
    for k in ("dataset", "code", "nendo", "url", "totta_hi",
              "dataset_id", "filename", "sha256"):
        if rec.get(k) is None:
            raise AssertionError(f"出典に要る {k} が無い")
    import tempfile, os as _os
    with tempfile.TemporaryDirectory() as d:
        lines = cg.kaku([rec], [], 0, 0,
                        report=_os.path.join(d, "g.md"),
                        daicho=_os.path.join(d, "g.json"))
    bun = "\n".join(lines)
    for atai in (rec["dataset"], rec["filename"], rec["dataset_id"],
                 rec["sha256"], rec["url"], rec["totta_hi"], "2025"):
        if atai not in bun:
            raise AssertionError(f"出典の欄に {atai[:24]} が出ていない")
    hitotsu = cg.shutten(rec)
    for atai in (rec["dataset"], rec["url"], rec["totta_hi"]):
        if atai not in hitotsu:
            raise AssertionError("出典の1行に足りない欄がある")


def test_地図_検査が本物の台帳に書いていないか():
    """**記録の在りかを `def` のときに固めない。呼ばれたときに見る。**
    既定値を定義時に束ねると、**検査は通り続けるのに、見ているものが違う。**

    2026-09-21 に2度踏んだ。1度目は `def yomu(michi=RECON)` が既定値を
    定義時に束ねていて、**検査が差し替えたつもりの置き場を素通りして
    本物を読んでいた。** 2度目はこの段——`kaku()` が置き場を受け取らず、
    **検査を走らせるたびに本物の台帳へ作り物を書いていた。**

    読む側と書く側で向きは逆だが、**穴は同じ。**
    """
    import inspect
    import chizu_get as cg
    sig = inspect.signature(cg.kaku)
    for na in ("report", "daicho"):
        if na not in sig.parameters:
            raise AssertionError(f"kaku() が {na} を受け取らない。差し替えられない")
        eq(sig.parameters[na].default, None,
           f"{na} の既定値を定義時に束ねている。**あとで差し替えられない**")
    src = inspect.getsource(cg.kaku)
    for na, teisu in (("report", "REPORT"), ("daicho", "DAICHO")):
        if f"{na} = {na} or {teisu}" not in src:
            raise AssertionError(f"{na} を遅く束ねていない")


def test_町丁目_住所が無い行を読めた行に混ぜていないか():
    """**原典が書かなかった行と、こちらが読めなかった行と、当たらなかった行。**

    2026-09-21 に見つけた。`town_gap.py` の説明文には
    「空になる理由は2つある。**混ぜない**」と書いてあったのに、
    **その下のコードが混ぜていた。**

    `addrlib.normalize` は住所が空でも例外を投げない。だから空の行が
    `try` を素通りして「住所が読めた行」に数えられ、
    **「住所そのものが読めなかった行: 0」**と書かれていた。
    実際は 464 行が空だった。**0件は、その道を1回も通っていないときにも出る。**
    """
    import town_gap as tg
    recs = [
        {"pref": "兵庫県", "city": "尼崎市", "address": "尼崎市潮江一丁目1-1"},
        {"pref": "兵庫県", "city": "尼崎市", "address": ""},        # 原典に無い
        {"pref": "兵庫県", "city": "尼崎市"},                        # 欄そのものが無い
        {"pref": "兵庫県", "city": "尼崎市", "address": "   "},      # 空白だけ
    ]
    total, empty, by_city, unreadable, nashi = tg.measure(recs)
    eq(nashi, 3, "原典に住所が無い行を数えていない。**読めた行に混ざる**")
    eq(total, 1, "住所が無い行を「読めた行」に数えている")
    eq(total + unreadable + nashi, len(recs), "どこかの行が落ちている")

    # **記録の文でも3つが分かれていること**
    lines = tg.main.__doc__ or ""
    src = open(os.path.join(HERE, "town_gap.py"), encoding="utf-8").read()
    if "原典に住所が書かれていなかった行" not in src:
        raise AssertionError("記録に、原典が書かなかった行の欄が無い")
    if "住所は在るが**読めなかった**行" not in src:
        raise AssertionError("記録に、こちらが読めなかった行の欄が無い")


def test_履歴を書き換える手が実行される所に無いか():
    """**正本が「採らない」と書いた手を、実行した**（2026-09-21）。

    正本9節には 2026-09-17 の時点で「同じ public リポジトリの中で履歴を
    書き換える手は採らない」と書いてあり、作り直しの順番まで在った。
    **参謀はどちらも読まずに走った。**

    以前ここでは**正本にその文が書いてあるか**を見ていた。
    だが書いてあっても読まなければ同じで、**実際に起きたのはそれだった。**
    見るものを、文章から**走るもの**へ移す——
    `filter-repo` や `force-push` が、**実行されるファイルに入っていないか。**

    決まりそのもの（先に読む・再測定を発見と書かない）は正本に残す。
    **文章が在るかは見ない。**言い回しを直せるようにしておく。
    """
    import re as _re
    ABUNAI = _re.compile(r"filter[-_]repo|force[-\s]push|push\s+--force|push\s+-f\b|rebase\s+--root")
    warui = []
    for fp in subete_no_py() + sorted(workflow_files()):
        if os.path.basename(fp) == "test_privacy.py":
            continue                      # 検査自身は、危ない語を**探す側**
        with open(fp, encoding="utf-8") as f:
            for i, ln in enumerate(f, 1):
                if ln.lstrip().startswith("#"):
                    continue              # 覚書は走らない
                if ABUNAI.search(ln):
                    warui.append(f"{os.path.relpath(fp, HERE)}:{i}")
    if warui:
        raise AssertionError(
            "履歴を書き換える手が、実行されるファイルに入っている： "
            + " / ".join(warui[:5])
            + "。**正本9節は採らないと決めている。**"
            "消したいものが在るなら、公開用を履歴ゼロで作り直す側を通す")

def test_停電_1社止めても残りが消えていないか():
    """**取得元の「だめ」を、題材の「だめ」にしない**（正本9節）。

    2026-09-21、九州電力送配電が規約で止まった。
    **止めたのはその1社の経路で、停電の記録そのものではない。**
    止めた相手を飛ばしたあと、**残りが0件になっていないか**を見る。
    ここが0になると、1社の規約が題材全体を落としたことになる。
    """
    import tempfile, pathlib as _pl
    import teiden_get as tg
    import teiden_recon as tr

    # 止まっている相手と、止まっていない相手を1つずつ置いた作り物の記録
    tomatteru = next(iter(tr.YAKUSOKU))
    hon = "\n".join([
        "### 記録らしいリンク",
        "",
        f"- 止まっている社    https://{tomatteru}/x",
        "- 止まっていない社    https://example.invalid/y",
        "",
    ])
    with tempfile.TemporaryDirectory() as d:
        michi = _pl.Path(d) / "recon.md"
        michi.write_text(hon, encoding="utf-8")
        nokori = tg.yomu(michi)
        tometa = tg.tometa(michi)

    eq(len(tometa), 1, "止めた相手を1社として数えていない")
    if not nokori:
        raise AssertionError(
            "1社止めたら行き先が0件になった。"
            "**その取得元が止まっただけで、題材が止まったのではない**（正本9節）")
    eq(len(nokori), 1, "止まっていない相手が残っていない")


def test_県公報_公開側に1件も残っていないか():
    """**公開側から県公報が外れているか**を、設定と実物の両方で見る。

    2026-09-22 に外した（統括判断 2026-09-21・正本9節「公開側に置いてよいかは、姉妹が読んでいるかでは決まらない」）。
    本文921本のうち714本に「氏名」の語が在り、人の名の形をした語が94種類。
    法人と確かめられたのは48種類、46種類は未測定。測り終わるまで公開しない。

    外す前に、金庫と公開側の 1,599 本すべてを blob の指紋で突き合わせた
    （欠落0・余分0・不一致0）。**「金庫に写した」と「金庫に全部在る」は
    別のこと**なので、消す前に数えた。

    確かめる順番は、設定より実物が強い（正本・09-21 の再測定表）——
    ① 許可リストに入っていないか ② 見張りが止める形か ③ **いま追跡が0件か**
    """
    import io as _io, re, subprocess
    michi = os.path.join(HERE, ".github", "workflows", "shutten-recon.yml")
    if not os.path.exists(michi):
        raise AssertionError("shutten-recon.yml が無い。名前を変えたなら検査も直すこと")
    hon = _io.open(michi, encoding="utf-8").read()

    # ① 公開側の許可リスト（for p in … の並び）に data/koho が混ざっていないか
    m = re.search(r"for p in (.+?); do", hon, re.S)
    eq(bool(m), True, "公開側の許可リストが見つからない")
    kyoka = m.group(1).replace("\\\n", " ").split()
    majitta = [x for x in kyoka if x.startswith("data/koho")]
    if majitta:
        raise AssertionError(
            "公開側の許可リストに県公報が戻っている: " + "、".join(majitta))

    # ② 見張りが data/koho ごと止める形か。`.md` だけを止める形に戻っていないか
    if not re.search(r"\^\(data/\([a-z|]*koho[a-z|]*\)/", hon):
        raise AssertionError(
            "公開側の commit を見張る式が data/koho を止めていない。"
            "**1本でも混ざれば公開される**")

    # ③ 置き場そのものが金庫につながっているか（写しではなく）
    m2 = re.search(r"for d in ([a-z ]+); do", hon)
    eq(bool(m2), True, "金庫につなぐ段が見つからない")
    if "koho" not in m2.group(1).split():
        raise AssertionError(
            "data/koho が金庫につながっていない。"
            "**公開側にも金庫にも目録が無いと、次の回は「1号も取っていない」"
            "ところから始まり、兵庫県への行き来が増える**（3.1 ではなく 3.4）")

    # ④ いま実際に1件も追跡していないか。**設定は消し忘れるが、追跡は嘘をつかない**
    try:
        out = subprocess.run(["git", "ls-files", "data/koho"], cwd=HERE,
                             capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return            # git が無いところでは ①②③ までで止める
    nokori = [x for x in out.splitlines() if x.strip()]
    if nokori:
        raise AssertionError(
            "公開リポジトリが県公報をまだ %d 件追跡している。例: %s"
            % (len(nokori), "、".join(nokori[:3])))


# ---------------------------------------------------------------- 取りこぼしを「見えなくなった」にしない（2026-09-24）

def test_取得がそろわなかった観測を見えなくなった根拠にしないか():
    """**「その日の取得結果に無かった」だけでは、見えなくなったとしない。**

    2026-09-24、堺市で「消えて戻った」33鍵が、全部こちらの取りこぼしだった。
    2階層目の上限で年度のページを取らなかった日に、そのページの届出が
    「その日に無かった」と数えられ、公開ページに「見つかっていません」と出ていた。

    見るのは、merge.listed_wo_kimeru（いまも載っているかを決める1か所）と、
    parse.py が書く台帳の読み方（merge.kanzen_na_hi）。

    2026-09-25、消失判定用の時点を**完全観測の日だけ**で進めるように直した
    （共通指示書4）。`listed_wo_kimeru` は「最後に見た日」1つではなく、
    **見えた日の集合**（days_seen。取得がそろっていたかに関係ない）と、
    **観測元・取得方式つきの完全観測の日**（kanzen_days）を受け取り、
    `(listed, kieta_kakunin, kakunin_saigo)` の3つを返す形に変わった。

    **捕まえないもの**：取得がそろったかの判定そのもの（下の2本が、取得の段と取り出しの段で見る）。
    """
    import json as _json
    import tempfile
    import merge as mg
    L = mg.listed_wo_kimeru
    U, T = "u", "html"    # 観測元・取得方式（同じ収集先なら、ふつう変わらない）
    # ① そろった2つの観測のあいだで見えなくなった → 確認できなくなった（見えなくなった候補）
    eq(L({"2026-09-20"}, "2026-09-21", [("2026-09-20", U, T), ("2026-09-21", U, T)]),
       (False, "2026-09-21", "2026-09-20"),
       "そろった観測で見えなくなったのに、確認できなくなったとしていない")
    # ② あとの観測がそろっていない → 未判定。**見えなくなったとしない**
    eq(L({"2026-09-20"}, "2026-09-21", [("2026-09-20", U, T)]), (None, None, "2026-09-20"),
       "そろっていない観測に無かっただけで、見えなくなったとしている")
    # ③ そろっていない日のあとに、また見えた → 載っている。**見えなくなった・また出た、にしない**
    eq(L({"2026-09-20", "2026-09-22"}, "2026-09-22", [("2026-09-20", U, T)]),
       (True, None, "2026-09-20"),
       "そろっていない日をはさんで、また見えたものを、載っていないとしている")
    # ④ そろっていない日をはさんで、そのあとのそろった観測で見えない → その日で確認できなくなった
    eq(L({"2026-09-20"}, "2026-09-23", [("2026-09-20", U, T), ("2026-09-23", U, T)]),
       (False, "2026-09-23", "2026-09-20"),
       "確認できなかった日を、そろった観測の日にしていない")
    # ⑤ 「消えた」と言えるはずの回のあとに、そろっていない回でもまた見えた → 未判定に戻す
    #    （**消えたと言ったあとで、また見えたら、その「消えた」は言わない**。正本の決まり）
    eq(L({"2026-09-20", "2026-09-24"}, "2026-09-25",
        [("2026-09-20", U, T), ("2026-09-23", U, T)]),
       (None, None, "2026-09-20"),
       "そろった観測で消えたと決めたあと、また見えたのに、消えたままにしている")
    # ⑥ kakunin_saigo のあとの最初の完全観測が、観測元・取得方式が違う → 比べない（未判定）
    #    （観測元がちがう回を比べると、中身と関係なく全部が入れ替わって見える）
    eq(L({"2026-09-20"}, "2026-09-25",
        [("2026-09-20", U, T), ("2026-09-23", "v", T)]),
       (None, None, "2026-09-20"),
       "観測元が変わった回と比べて、消えたとしている")
    # ⑦ 完全観測で一度も見えていない → kakunin_saigo が無いので、常に未判定
    eq(L({"2026-09-21"}, "2026-09-25", [("2026-09-20", U, T)]), (None, None, None),
       "完全観測で一度も見えていないのに、消えたと言える形にしている")
    # ⑧ 台帳が無い・読めない → どの日も、そろったと言わない
    with tempfile.TemporaryDirectory() as tmp:
        michi = os.path.join(tmp, "kansoku-kanzen.json")
        eq(mg.kanzen_na_hi(michi), {}, "台帳が無いのに、そろった日があることにしている")
        with open(michi, "w", encoding="utf-8") as f:
            _json.dump({"_setsumei": "x", "a": {"2026-09-20": {"kanzen": True, "moto": "u", "houshiki": "html"},
                                                "2026-09-21": {"kanzen": False},
                                                "2026-09-22": {"kanzen": None}}}, f)
        eq(mg.kanzen_na_hi(michi), {"a": [("2026-09-20", "u", "html")]},
           "そろっていない日・確かめていない日を、そろった日に入れている")


def test_直前の完全観測とだけ比べているか():
    """**遠くの完全観測と比べない。** kakunin_saigo のあとの**最初の**完全観測だけを見る。

    共通指示書4の「そのあとの最初の完全観測の日 C」を字義どおり守っているかを見る——
    途中に合わない観測元・取得方式の日があっても、**それより先の完全観測まで探しに行かない**
    （探しに行くと、たまたま条件の合う遠い日と比べてしまい、比べる相手を自分で選ぶ形になる）。
    """
    import merge as mg
    L = mg.listed_wo_kimeru
    U, T = "u", "html"
    # kakunin_saigo=09-20 の次の完全観測（09-22）は観測元が違う。**その先の09-25（同じ観測元）
    # まで探しに行かない**——探せば「消えた」になってしまうが、09-22 で止まって未判定のまま
    eq(L({"2026-09-20"}, "2026-09-26",
        [("2026-09-20", U, T), ("2026-09-22", "べつの観測元", T), ("2026-09-25", U, T)]),
       (None, None, "2026-09-20"),
       "途中の観測元違いを飛ばして、もっと先の完全観測と比べている")


def test_完全性を分からないから真に補っていないか():
    """**「分からない」を「はい」に埋めない。** 共通指示書2・spec/kanzen.md 3。

    ① recon.kanzen_hantei() は、呼ぶ側が「解析できた」を渡さないかぎり、
       ページが完璧にそろっていても **True と言い切らない**（parse.py が決めるまで）。
       壊して鳴ることも確かめる——`kaiseki=はい` を渡すと True に**変わる**こと。
    ② 200 で 0 行（前は1件以上あった）を、それだけで完全観測にしない
       （`parse.kaiseki_no_shirushi`。kanzen.zero_gyou の配線側）。
    ③ 店名か届出日の列が見つからず表を丸ごと飛ばした日は、件数がいくつでも「分からない」。
    ④ 前の完全観測から鍵の半分以上が一度に消えたら「分からない」（kanzen.kyugen の配線側）。
    """
    import json as _json
    import tempfile
    import recon as rc
    import parse as ps

    # ① kaiseki を渡さない限り True にならない。渡すと True になる（壊して鳴ることの確認）
    with tempfile.TemporaryDirectory() as tmp:
        d = os.path.join(tmp, "nise")
        os.makedirs(d)
        page = '<html><body><table><tr><th>届出日</th><th>店舗</th></tr><tr><td>a</td><td>b</td></tr></table></body></html>'
        with open(os.path.join(d, "2026-09-25.html"), "w", encoding="utf-8") as f:
            f.write(page)
        with open(os.path.join(d, "2026-09-25.shirushi.json"), "w", encoding="utf-8") as f:
            _json.dump({"shirushi": {m: "はい" for m in (
                "入口に届いた", "必要本文を受け取った", "辿る対象の失敗0",
                "上限未到達", "最終URLが承認範囲内", "private保存成功")},
                "houshiki": "html", "moto": "https://x.example/"}, f, ensure_ascii=False)
        src = {"id": "nise", "url": "https://x.example/"}
        k = rc.kanzen_hantei(src, "2026-09-25", tmp)
        if k["kanzen"] is True:
            raise AssertionError(
                "「解析できた」を渡していないのに True。分からないをはいに補っている")
        k2 = rc.kanzen_hantei(src, "2026-09-25", tmp, kaiseki=rc.kanzen.HAI)
        eq(k2["kanzen"], True, "「解析できた」を渡しても True にならない。壊れていても鳴らない検査")

    # ② 200 で 0 行（前は5件）を、それだけで完全観測にしない
    eq(ps.kaiseki_no_shirushi(5, 0, {"a", "b"}, set(), False), rc.kanzen.WAKARANAI,
       "前は5件あったのに今回0件を、根拠なく完全観測にしている")
    # 前も今回も0件なら、そのまま「はい」でよい（kanzen.zero_gyou の既定）
    eq(ps.kaiseki_no_shirushi(0, 0, set(), set(), False), rc.kanzen.HAI,
       "前後とも0件なのに完全観測にしていない")
    # ③ 表を飛ばした日は、件数が十分でも「分からない」
    eq(ps.kaiseki_no_shirushi(0, 40, set(), set(range(40)), True), rc.kanzen.WAKARANAI,
       "店名か届出日の列が見つからず表を飛ばしたのに、完全観測にしている")
    # ④ 鍵の半分以上が一度に消えたら「分からない」
    eq(ps.kaiseki_no_shirushi(10, 4, set(range(10)), set(range(4)), False), rc.kanzen.WAKARANAI,
       "鍵の半分以上が一度に消えたのに、完全観測にしている")
    # それ以外（半分未満の減り）は「はい」
    eq(ps.kaiseki_no_shirushi(10, 6, set(range(10)), set(range(6)), False), rc.kanzen.HAI,
       "半分未満の減りなのに、完全観測にしていない")


def _nise_saito(nensu, dame=()):
    """架空の相手（**外には出ない**）。入口 → 名称変更の目次 → 年度のページ。
    本文の外に「このページも読まれています」の欄があり、別の置き場のページを指している。
    返り値は (入口の URL, {URL: HTML の bytes})。dame に入れた年度は None（取りに行くと 404）"""
    base = "https://mise.example/todokede/"

    def waku(naka, soto=""):
        return ("<html><body><div id=\"main\"><!-- ▼メインコンテンツここから▼ -->"
                "<img alt=\"本文ここから\">" + naka + "<img alt=\"本文ここまで\">"
                "<!-- ▲メインコンテンツここまで▲ --></div>" + soto + "</body></html>").encode("utf-8")
    osusume = ("<div class=\"losubnavi lorecommend\"><h2>このページも読まれています</h2><ul>"
               "<li><a href=\"/chukibo/ichiran.html\">中規模小売店舗の届出状況</a></li></ul></div>")
    pages = {base + "index.html": waku(
        "<h1>大規模小売店舗の届出状況</h1><ul><li><a href=\"meisho/index.html\">"
        "名称・代表者等の変更の届出（法第6条第1項関係）について</a></li></ul>", osusume)}
    nen = list(range(8, 8 - nensu, -1))
    pages[base + "meisho/index.html"] = waku("<ul>" + "".join(
        f"<li><a href=\"r{y}/index.html\">令和{y}年度 名称・代表者等の変更の届出"
        "（法第6条第1項関係）について</a></li>" for y in nen) + "</ul>", osusume)
    for y in nen:
        pages[base + f"meisho/r{y}/index.html"] = None if y in dame else waku(
            "<table><tr><th>届出日</th><th>店舗</th></tr>"
            f"<tr><td>令和{y}年4月1日</td><td>架空店{y}</td></tr>"
            f"<tr><td>令和{y}年5月1日</td><td>架空店{y}b</td></tr></table>")
    pages["https://mise.example/chukibo/ichiran.html"] = waku(
        "<table><tr><th>a</th><th>b</th></tr><tr><td>1</td><td>2</td></tr>"
        "<tr><td>3</td><td>4</td></tr></table>")
    return base + "index.html", pages


def _recon_wo_nise_de_hashiraseru(nensu, dame=()):
    """**本物の recon.main を、架空の相手で1回走らせる。**外には出ない
    （fetch・robots・sleep を差し替える）。返り値は (その日の判定, 取りに行った URL, 記録の文)

    2026-09-25、recon.kanzen_hantei() が「解析できた」を含む7つの印
    （共通指示書2）を見るようになった。「解析できた」は parse.py だけが知っているので、
    ここで見たい**取得（ページを辿れたか）の完全性**だけを確かめるため、
    `kaiseki=はい` を明示して渡す（このテストの主題ではないので、固定して外す）。
    同じ理由で、KINKO_PRIVATE も「1」に固定する（private保存成功の印を揺らさない）。
    """
    import contextlib
    import io
    import json as _json
    import tempfile
    import time as _time
    import urllib.error
    import recon as rc
    url, pages = _nise_saito(nensu, dame)
    tori = []

    def nise_fetch(u):
        tori.append(u)
        if pages.get(u) is None:
            raise urllib.error.HTTPError(u, 404, "Not Found", {}, None)
        return 200, "text/html; charset=utf-8", pages[u]
    moto = (rc.HERE, rc.fetch, rc.check_robots, _time.sleep, sys.argv[:])
    moto_env = {k: os.environ.get(k) for k in ("RUN_DATE", "GITHUB_STEP_SUMMARY", "KINKO_PRIVATE")}
    with tempfile.TemporaryDirectory() as tmp:
        with open(os.path.join(tmp, "sources.json"), "w", encoding="utf-8") as f:
            _json.dump({"sources": [{"id": "nise", "name": "架空", "area": "test", "url": url}]}, f)
        try:
            rc.HERE, rc.fetch = tmp, nise_fetch
            rc.check_robots = lambda u: (True, "許可")
            _time.sleep = lambda s: None
            sys.argv = ["recon.py"]
            os.environ["RUN_DATE"] = "2026-09-25"
            os.environ["KINKO_PRIVATE"] = "1"
            os.environ.pop("GITHUB_STEP_SUMMARY", None)
            # カードの門（common/kado.py）は**通す偽物**に差し替える。架空の置き場
            # には torimoto-card.json が無いので、素のままだと「カードが無い」で
            # 全部止まる。ここで見たいのは取得の完全性の判定であって、門そのもの
            # の挙動は tests/test_kado.py が確かめている。
            with contextlib.redirect_stdout(io.StringIO()), toosu_kado_mon(rc):
                rc.main()
            k = rc.kanzen_hantei({"id": "nise", "url": url}, "2026-09-25",
                                 os.path.join(tmp, "data", "raw"), kaiseki=rc.kanzen.HAI)
            with open(os.path.join(tmp, "data", "recon-report.md"), encoding="utf-8") as f:
                kiroku = f.read()
        finally:
            rc.HERE, rc.fetch, rc.check_robots, _time.sleep, sys.argv = moto
            for kk, v in moto_env.items():
                if v is None:
                    os.environ.pop(kk, None)
                else:
                    os.environ[kk] = v
    return k, tori, kiroku


def test_上限で切った日と取れなかった日を取得がそろったと名乗らないか():
    """**取得の段が、自分の取得をそろったと言えるときだけ、そう言う。**

    2026-09-24、堺市。名称変更の目次に年度が6本あり、2階層目の上限（4本）で
    2本を**黙って**切っていた。取得の記録にも、切ったことは1行も出ていなかった。

    **本物の recon.main を架空の相手で走らせて**、保存したものから決めた判定を見る。

        ① 年度3本（上限の内側）を全部取れた   → そろった
        ② 年度6本。上限で2本切った            → そろっていない。記録にも出る
        ③ 年度3本のうち1本が 404              → そろっていない
        ④ 本文の外の欄（このページも読まれています）からは、取りに行かない

    **捕まえないもの**：上限の数そのものが妥当か（相手への負荷の判断）。
    """
    k, tori, kiroku = _recon_wo_nise_de_hashiraseru(3)
    if not k or k["kanzen"] is not True:
        raise AssertionError(f"年度3本を全部取れたのに、そろったと言わない: {k and k['riyuu']}")
    k, tori, kiroku = _recon_wo_nise_de_hashiraseru(6)
    if not k or k["kanzen"] is not False:
        raise AssertionError("上限で年度を切ったのに、取得がそろったと言っている")
    eq(len(k["tarinai"]), 2, "上限で切った年度の数が、保存が無いものの数と合わない")
    if "取得の完全性: そろっていない" not in kiroku:
        raise AssertionError("上限で切ったことが、取得の記録に出ていない（黙って切っている）")
    k, tori, kiroku = _recon_wo_nise_de_hashiraseru(3, dame=(7,))
    if not k or k["kanzen"] is not False:
        raise AssertionError("年度のページが取れなかったのに、取得がそろったと言っている")
    for nensu in (3, 6):
        _k, tori, _kiroku = _recon_wo_nise_de_hashiraseru(nensu)
        if any("/chukibo/" in u for u in tori):
            raise AssertionError(
                "本文の外の欄（このページも読まれています）から、別の置き場のページへ取りに行っている")


def test_本文の外の欄から迷い込んだページを取り出しに使わないか():
    """2026-09-24、中規模の置き場に、大規模の年度ページが紛れ込んでいた。

    本文の外の「このページも読まれています」の欄から辿って保存したページを、
    取り出しの段がそのまま読み、大規模の届出12件が中規模の名前で出ていた。

    **本物の parse.main を、仮の置き場で走らせる。**置き場には、入口と年度のページのほかに、
    欄から迷い込んで保存したページを1枚まぜる（前の取得の段が保存した形）。

        ① 取り出しに、迷い込んだページを使わない
        ② 入口と、辿るべきだったページは使う
        ③ 台帳に「取得がそろった」が書かれる

    **捕まえないもの**：表の読み取りそのもの（読み取りは差し替えて、どのファイルを読んだかだけを見る）。
    """
    import json as _json
    import tempfile
    import parse as ps
    import recon as rc
    url, pages = _nise_saito(3)
    day = "2026-09-25"
    moto = (ps.HERE, ps.RAW, ps.OUT, ps.KANZEN_DAICHO, ps.EXTRACTORS,
            ps.parse_file, ps.write_unknown_report, os.environ.get("GITHUB_STEP_SUMMARY"))
    with tempfile.TemporaryDirectory() as tmp:
        d = os.path.join(tmp, "data", "raw", "nise")
        os.makedirs(d)
        for u, body in pages.items():
            name = f"{day}.html" if u == url else f"{day}--{rc.slug_of(u)}.html"
            with open(os.path.join(d, name), "wb") as f:
                f.write(body)
        # 取得段の印（共通指示書2）。ここは recon.main() を走らせていないので、
        # 実物と同じ形で自分で置く——**取れた前提**を置かないと、この印が無いままになり
        # （＝分からない）、台帳の kanzen が「解析できた」だけでは True にならない
        with open(os.path.join(d, f"{day}.shirushi.json"), "w", encoding="utf-8") as f:
            _json.dump({"shirushi": {m: "はい" for m in (
                "入口に届いた", "必要本文を受け取った", "辿る対象の失敗0",
                "上限未到達", "最終URLが承認範囲内", "private保存成功")},
                "houshiki": "html", "moto": url}, f, ensure_ascii=False)
        with open(os.path.join(tmp, "sources.json"), "w", encoding="utf-8") as f:
            _json.dump({"sources": [{"id": "nise", "name": "架空", "url": url}]}, f)
        yonda = []

        def nise_parse_file(source, path):
            yonda.append(os.path.basename(path))
            return [{"key": os.path.basename(path), "kind": "テスト"}]
        try:
            ps.HERE, ps.RAW, ps.OUT = tmp, os.path.join(tmp, "data", "raw"), os.path.join(tmp, "data", "parsed")
            ps.KANZEN_DAICHO = os.path.join(tmp, "data", "ref", "kansoku-kanzen.json")
            ps.EXTRACTORS = {"nise": {"base": url, "how": "heading"}}
            ps.parse_file = nise_parse_file
            ps.write_unknown_report = lambda path: 0
            os.environ.pop("GITHUB_STEP_SUMMARY", None)
            import contextlib
            import io
            with contextlib.redirect_stdout(io.StringIO()):
                ps.main()
            with open(ps.KANZEN_DAICHO, encoding="utf-8") as f:
                daicho = _json.load(f)
        finally:
            (ps.HERE, ps.RAW, ps.OUT, ps.KANZEN_DAICHO, ps.EXTRACTORS,
             ps.parse_file, ps.write_unknown_report, gh) = moto
            if gh is not None:
                os.environ["GITHUB_STEP_SUMMARY"] = gh
    if any("chukibo" in n for n in yonda):
        raise AssertionError("本文の外の欄から迷い込んで保存したページを、取り出しに使っている")
    eq(sorted(n for n in yonda if "meisho-r" in n).__len__(), 3,
       "辿るべきだった年度のページを、取り出しに使っていない")
    if f"{day}.html" not in yonda:
        raise AssertionError("入口ページを取り出しに使っていない")
    eq((daicho.get("nise") or {}).get(day, {}).get("kanzen"), True,
       "取得がそろった日を、台帳にそろったと書いていない")


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
