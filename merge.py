#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""日ごとに取り出した届出を、1件1行にまとめる。

data/parsed/<id>/<日付>.json は「その日にページに載っていたもの」。
毎日とるので、同じ届出が日の数だけ並ぶ。ここで目印（key）ごとにまとめて、

  first_seen … はじめて見た日
  last_seen  … 最後に見た日
  listed     … 最新の保存日にまだ載っているか

を付ける。listed が false になった瞬間が「縦覧が終わってページから消えた」
ということで、この仕組みの芯になる。消えたあとも、ここには残る。

大阪市・大阪府のExcelは過去分を全部含む累積の一覧なので、消える／消えない
の対象にはしない（mode を cumulative にする）。

出力
  data/all.json    … 全件（1件1行）
  data/summary.md  … 収集先ごとの件数と、消えたものの一覧
"""

import glob
import json
import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import privacy

HERE = os.path.dirname(os.path.abspath(__file__))
PARSED = os.path.join(HERE, "data", "parsed")
OUT_ALL = os.path.join(HERE, "data", "all.json")
OUT_SUM = os.path.join(HERE, "data", "summary.md")

DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CUMULATIVE = {"osaka-city", "osaka-pref", "hyogo-bukai", "hyogo-koho"}   # 過去分を全部含む一覧を出している収集先（部会の議案も過去の届出を含む）


# ---------------------------------------------------------------- 地域をそろえる
# 収集先ごとに、都道府県と市が決まっているものはここで決める。None は住所から読む
SOURCE_PLACE = {
    "osaka-city": ("大阪府", "大阪市"),   "osaka-pref": ("大阪府", None),
    "sakai-city": ("大阪府", "堺市"),     "sakai-chukibo": ("大阪府", "堺市"),
    "hirakata-city": ("大阪府", "枚方市"), "toyonaka-city": ("大阪府", "豊中市"),
    "ibaraki-city": ("大阪府", "茨木市"),  "kadoma-city": ("大阪府", "門真市"),
    "kishiwada-city": ("大阪府", "岸和田市"), "matsubara-city": ("大阪府", "松原市"),
    "sennan-city": ("大阪府", "泉南市"),   "kumatori-town": ("大阪府", "熊取町"),
    "hannan-city": ("大阪府", "阪南市"),   "yao-city": ("大阪府", "八尾市"),
    "yao-chukibo": ("大阪府", "八尾市"),   "minoh-city": ("大阪府", "箕面市"),
    "minoh-2shi2cho": ("大阪府", None),    "kobe-city": ("兵庫県", "神戸市"),
    "hyogo-pref-juran": ("兵庫県", None), "hyogo-bukai": ("兵庫県", None), "hyogo-koho": ("兵庫県", None),
}
# 兵庫県は住所が無いので、店名に入っている地名から当てる（当て推量なので印をつける）
HYOGO_CITIES = ["神戸", "姫路", "尼崎", "明石", "西宮", "洲本", "芦屋", "伊丹", "相生", "豊岡", "加古川",
                "赤穂", "西脇", "宝塚", "三木", "高砂", "川西", "小野", "三田", "加西", "丹波篠山", "養父",
                "丹波", "南あわじ", "朝来", "淡路", "宍粟", "加東", "たつの", "猪名川", "稲美", "播磨",
                "福崎", "太子", "上郡", "佐用", "香美", "新温泉", "多可", "市川", "神河"]
WARD = re.compile(r"^(?:大阪市|堺市|神戸市)?([^\s市区町村]{1,4}区)")
CITY = re.compile(r"^(?:大阪府|兵庫県)?([^\s]{1,6}?[市町村])")


def place_of(r):
    """(都道府県, 市, 区, 当て推量か) を返す。"""
    pref, city = SOURCE_PLACE.get(r["source"], ("", None))
    addr = (r.get("address") or "").strip()
    ward = ""
    guess = False
    if r["source"] == "osaka-city":
        ward = (r.get("ward") or "").strip()
        ward = ward + "区" if ward and not ward.endswith("区") else ward
    elif city in ("堺市", "神戸市"):
        m = WARD.match(addr)
        ward = m.group(1) if m else ""
    if city is None:
        c = (r.get("city") or "").strip()
        if not c:
            m = CITY.match(addr)
            c = m.group(1) if m else ""
        if not c and r["source"] == "hyogo-pref-juran":
            towns = ("猪名川", "稲美", "播磨", "福崎", "太子", "上郡", "佐用", "香美", "新温泉", "多可", "市川", "神河")
            # 2024年の表は「所在」列に「姫路」「朝来」と市名だけ書いてある。これは当て推量ではない
            if addr in HYOGO_CITIES:
                c = addr + ("町" if addr in towns else "市")
            else:
                store = r.get("store") or ""
                for name in HYOGO_CITIES:
                    if name in store:
                        c = name + ("町" if name in towns else "市")
                        guess = True
                        break
        city = c or ""
    return pref, city, ward, guess


# ---------------------------------------------------------------- 収集先をまたいだ重複をまとめる
# 大阪府が事務を移譲した市町（茨木・豊中・岸和田・箕面・枚方・門真・泉南…）の届出は、
# その市のページと大阪府の月次Excelの両方に載る。箕面市のページは2つの入口から届く。
# 同じ届出が2回数えられるので、店名・届出日・条文が同じものを1件にまとめる。
def norm_store(s):
    return re.sub(r"[\s（）()仮称・･ー－\-]|株式会社|㈱", "", s or "").lower()


def filled(r):
    return sum(1 for v in r.values() if v not in ("", None, [], 0, False))


def merge_across_sources(by_key):
    groups = defaultdict(list)
    for r in by_key.values():
        groups[(norm_store(r["store"]), r["notified_on"])].append(r)
    out = {}
    merged_away = 0

    def settle(g):
        """同じ店・同じ届出日の一群を、1件にまとめるか、そのまま置くか。"""
        nonlocal merged_away
        srcs = Counter(r["source"] for r in g)
        # 収集先が1つだけ、または同じ収集先から2件以上出ている（別の届出）ときは触らない
        if len(srcs) == 1 or any(n > 1 for n in srcs.values()):
            for r in g:
                out[r["key"]] = r
            return
        # 項目が多いものを土台にし、空いている項目を他から埋める。土台の選び方は毎日同じになるようにする
        g.sort(key=lambda r: (-filled(r), r["source"], r["key"]))
        base = dict(g[0])
        for other in g[1:]:
            for k, v in other.items():
                if base.get(k) in ("", None, [], 0) and v not in ("", None, [], 0):
                    base[k] = v
        snaps = [r for r in g if r.get("mode") == "snapshot"]
        if snaps:
            base["mode"] = "snapshot"
            base["listed"] = any(r.get("listed") for r in snaps)
            fs = [r["first_seen"] for r in snaps if r.get("first_seen")]
            ls = [r["last_seen"] for r in snaps if r.get("last_seen")]
            base["first_seen"] = min(fs) if fs else None
            base["last_seen"] = max(ls) if ls else None
        base["sources"] = sorted(srcs)
        base["merged_keys"] = sorted(r["key"] for r in g if r["key"] != base["key"])
        out[base["key"]] = base
        merged_away += len(g) - 1

    for g in groups.values():
        # 条文が食い違うものは別の届出（同じ日に6条1項と6条2項を出すことがある）。
        # 条文が空（「変更」としか書いていない市のページ）のものは、相手の条文が1つに決まるときだけ寄せる
        arts = {r.get("article", "") for r in g} - {""}
        if len(arts) <= 1:
            settle(g)
            continue
        by_art = defaultdict(list)
        for r in g:
            by_art[r.get("article", "")].append(r)
        for art, sub in by_art.items():
            if art == "":
                for r in sub:
                    out[r["key"]] = r
            else:
                settle(sub)
    return out, merged_away


# ---------------------------------------------------------------- OCRで読んだものを流し込む
# 兵庫県・神戸市はHTMLの表に届出日・店名・縦覧期間しか無く、所在地や設置者は
# 届出書のPDF（紙をスキャンした画像）の中にある。ocr.py が読んだ結果を、
# 届出に付いているPDFのファイル名で結びつけて、空いている項目だけ埋める。
# OCRは誤読がありうるので、どの項目をOCRから取ったかを from_ocr に残す。
def load_ocr():
    out = {}
    for p in glob.glob(os.path.join(HERE, "data", "ocr", "*.json")):
        out[os.path.splitext(os.path.basename(p))[0]] = load(p)
    return out


def tidy_ocr(v):
    v = re.sub(r"(?<=[0-9０-９])\s+(?=[0-9０-９])", "", v or "")     # 「1 0番地」→「10番地」
    v = re.sub(r"\s*[|｜]\s*.*$", "", v)                            # 表の罫線の読み違いを落とす
    v = re.sub(r"^(?:氏名又は名称|名称|氏名|住所|所在地)\s*[:：]?\s*", "", v)   # 様式の項目名が頭に残ることがある
    return v.strip(" 　:：")


def enrich_from_ocr(by_key, ocr):
    n = 0
    for r in by_key.values():
        table = ocr.get(r["source"])
        if not table or not r.get("docs"):
            continue
        for u in r["docs"]:
            stem = os.path.splitext(os.path.basename(u))[0]
            o = table.get(stem)
            if not o:
                continue
            got = []
            pairs = (("address", "address"), ("operator", "applicant"), ("content", "content"))
            for field, okey in pairs:
                if not r.get(field) and o.get(okey):
                    r[field] = tidy_ocr(o[okey])
                    got.append(field)
            if not r.get("area_m2") and o.get("area"):
                digits = re.sub(r"[^0-9]", "", o["area"])
                if digits and 100 <= int(digits) <= 300000:
                    r["area_m2"] = int(digits)
                    got.append("area_m2")
            if got:
                r["from_ocr"] = sorted(set(r.get("from_ocr", []) + got))
                n += 1
            break
    return n


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ------------------------------------------------- 日ごとのファイルからも落とす
def scrub_parsed():
    """data/parsed の日ごとのファイルからも氏名と地番を落とす。

    data/parsed は「その日にページに載っていたもの」を1日1枚ずつためたもので、
    リポジトリに入れて公開している。ここは行政のページの写しではなく、
    こちらが作った索引なので、氏名で引ける形にしてはいけない（9節）。

    行政の写しそのもの（data/raw の HTML と PDF）はさわらない。
    規則を変えたくなったら、そこから作り直せる。

    何度通しても同じ結果になるようにしてある。
    """
    changed = 0
    for path in sorted(glob.glob(os.path.join(PARSED, "**", "*.json"), recursive=True)):
        try:
            with open(path, encoding="utf-8") as f:
                rows = json.load(f)
        except Exception:
            continue
        if not isinstance(rows, list):
            continue
        before = json.dumps(rows, ensure_ascii=False, sort_keys=True)
        apply_privacy([r for r in rows if isinstance(r, dict)])
        after = json.dumps(rows, ensure_ascii=False, sort_keys=True)
        if before != after:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(rows, f, ensure_ascii=False, indent=1)
            changed += 1
    return changed


# ------------------------------------------------------- 出典と取得日（3.5）
# 共通仕様 3.5「全レコードに source_url と fetched_on」。監査で 4,790 件とも
# 無かった。2,185 ページの出典が「（URL、取得）」と日付が空のまま出ていた。
SOURCES = os.path.join(HERE, "sources.json")
KOHO_LEDGER = os.path.join(HERE, "data", "koho", "issues.json")
FILES_LEDGER = os.path.join(HERE, "data", "files", "fetched.json")
# 一覧ページではなく文書そのものが出どころの収集先。source_url は文書のURL
DOC_SOURCES = {"hyogo-koho", "hyogo-bukai"}


def stamp_sources(recs):
    """各レコードに source_url と fetched_on を付ける。付けられなかった件数を返す。

    fetched_on の決め方（上から順に、最初にあるもの）
      1. last_seen / first_seen … 毎日巡回している収集先。実際に見た日
      2. 公報の台帳 issues.json の when … 兵庫県公報。PDFを取った日
      3. data/files/fetched.json … Excel・PDF をダウンロードした日
    どれも無ければ空にして、テストで落とす（黙って今日の日付にしない）。
    """
    try:
        with open(SOURCES, encoding="utf-8") as f:
            meta = {x["id"]: x for x in json.load(f)["sources"]}
    except Exception:
        meta = {}
    try:
        with open(KOHO_LEDGER, encoding="utf-8") as f:
            koho_when = {v.get("url"): v.get("when") for v in json.load(f).values() if v.get("url")}
    except Exception:
        koho_when = {}
    try:
        with open(FILES_LEDGER, encoding="utf-8") as f:
            file_when = json.load(f)
    except Exception:
        file_when = {}

    missing = 0
    for r in recs:
        src = r.get("source", "")
        docs = r.get("docs") or []
        m = meta.get(src, {})
        if src in DOC_SOURCES and docs:
            r["source_url"] = docs[0]
        else:
            r["source_url"] = m.get("url") or (docs[0] if docs else "")

        when = r.get("last_seen") or r.get("first_seen") or ""
        if not when and docs:
            when = koho_when.get(docs[0], "") or ""
        if not when and r.get("file"):
            when = file_when.get(f"{src}/{r['file']}", "") or ""
        if not when and docs:
            # 文書のURLの末尾がそのまま data/files/<収集先>/ のファイル名（部会の議案など）
            when = file_when.get(f"{src}/{os.path.basename(docs[0].split('?')[0])}", "") or ""
        r["fetched_on"] = when
        if not r["source_url"] or not when:
            missing += 1
    return missing


# ------------------------------------------------------------ 個人情報を落とす
# 共通仕様 3.1。設置者には個人がまざる（届出は建物の持ち主が出すので、
# 地主が個人のことがある）。氏名と地番の両方をそのまま出していた。
# 行政の縦覧は4か月で消えるが、このサイトは消えない。だからここで落とす。
#
# 生データ（data/raw）はさわらない。落とすのは出力の段階だけ（9節）。
# data/all.json は公開しているので、ここも出力として扱う。
PARTY_FIELDS = ("operator", "new_operator", "retailer")

# 設置者の名前が、その収集先の一次情報のどこにも無いことを確かめた収集先。
# ここに入れると party_kind が undisclosed になり、所在地を丸めない（3.1）。
#
# 入れてよいのは「一覧にも、そこからリンクされた資料にも、設置者が
# 書かれていない」と実物で確かめたものだけ。読めていないだけのものを
# 入れると、こちらの取りこぼしがそのまま地番の公開になる。
#
# 確かめ方と結果（2026-09-15 時点）
#   yao-chukibo       表の列は 年度／届出日／店舗名称／所在地（地番）／店舗面積。
#                     ページに PDF へのリンクが 0 本。設置者はどこにも無い
#   ibaraki-city      表の列は 名称／所在地／届出日／市の意見。
#                     ページに PDF へのリンクが 0 本。設置者はどこにも無い
#
# 入れなかったもの（名前はあるが、こちらがまだ読んでいない）
#   kobe-city         届出概要のPDFに「設置者の名称及び住所…」の欄がある
#   hyogo-pref-juran  OCR43本のうち5本に設置者の記載。1本は法人名まで読めている
#   matsubara-city    PDF 37本へのリンクがある（未取得）
#   toyonaka-city     PDF 24本へのリンクがある（未取得）
NO_NAME_ANYWHERE = {"yao-chukibo", "ibaraki-city"}


def apply_privacy(recs):
    """氏名と所在地を、共通仕様 3.1 の粒度に落とす。落とした件数を返す。"""
    hidden = 0
    for r in recs:
        kinds = {}
        for f in PARTY_FIELDS:
            raw = r.get(f)
            if raw is None:
                continue
            if r.get(f + "_display") == "個人" and not (raw or "").strip():
                # 個人だったので名前を消してあり、値も空。もう一度通すと、空の
                # 値を見て画面用の「個人」まで消してしまう。ここだけは止める。
                # 消した名前は戻せないので、規則を変えたくなったら
                # data/raw から作り直す。
                #
                # 「値が空」の条件が要る。消したあとに OCR や収集先の合流で
                # 名前が入り直すことがあり、そのとき止めてしまうと、入った氏名が
                # privacy.py を通らず index 用の欄に残る（監査で再現された穴）。
                # 値があるなら下に落として、毎回判定し直す
                kinds[f] = r.get(f + "_kind", "individual")
                continue

            # それ以外は毎回やり直す。値はあとから埋まることがあるので
            # （収集先をまたいでまとめたとき、OCRで補ったとき）、
            # 一度決めた判定を持ち回ると、法人名が入ったのに individual の
            # ままになる。実際「三菱UFJ信託銀行（株）」が individual に
            # なっていて、法人の地番を丸めていた
            # 一次情報に欄が無いと確かめた収集先だけ undisclosed にできる。
            # 値が入っているときは、欄があったということなので普通に判定する
            disclosed = not (r.get("source") in NO_NAME_ANYWHERE and not (raw or "").strip())
            kind = privacy.party_kind(raw, disclosed=disclosed)
            kinds[f] = kind
            r[f] = privacy.party_for_index(raw)      # 機械用。個人は空文字
            r[f + "_display"] = privacy.redact_name(raw)   # 画面用。個人は「個人」
            r[f + "_kind"] = kind

        # 所在地を丸めるかどうかは「設置者」で決める。小売業者は店舗の
        # 所在地であって住まいではないので、丸める理由がない（3.1）。
        #
        # 設置者は、空でも個人として扱う。読めていないだけかもしれず、
        # こちらの取りこぼしを地番の公開にしないため（3.1・121件の件）。
        # 新設置者は承継のときだけ出てくる欄なので、値があるときだけ見る。
        # 空を個人と数えると、承継でない届出が全部丸まってしまう。
        round_it = kinds.get("operator", "individual") == "individual"
        if (r.get("new_operator") or "").strip():
            round_it = round_it or kinds.get("new_operator") == "individual"
        # 印は毎回つけ直す。収集先をまたいでまとめるときに、丸めた記録の印だけが
        # 法人の記録に移ることがある。前回の印を残すと、法人の地番に
        # 「個人のため丸めた」と書いてしまう
        r.pop("address_redacted", None)
        if round_it:
            r["address"] = privacy.redact_addr(r.get("address") or "", "individual")
            r["address_redacted"] = True
            hidden += 1
    return hidden


def main():
    scrubbed = scrub_parsed()
    if scrubbed:
        print(f"日ごとのファイル {scrubbed} 枚から氏名と地番を落とした（共通仕様3.1）")

    by_key = {}
    latest_day = {}                     # 収集先ごとの、いちばん新しい保存日

    for src_dir in sorted(glob.glob(os.path.join(PARSED, "*"))):
        src = os.path.basename(src_dir)
        files = sorted(glob.glob(os.path.join(src_dir, "*.json")))
        if not files:
            continue
        cumulative = src in CUMULATIVE

        for path in files:
            stem = os.path.splitext(os.path.basename(path))[0]
            day = stem if DAY.match(stem) else None
            if day and not cumulative:
                latest_day[src] = max(latest_day.get(src, ""), day)
            for rec in load(path):
                k = rec["key"]
                cur = by_key.get(k)
                if cur is None:
                    rec = dict(rec)
                    rec["first_seen"] = day
                    rec["last_seen"] = day
                    rec["mode"] = "cumulative" if cumulative else "snapshot"
                    by_key[k] = rec
                else:
                    # あとの日のほうを本体にし、はじめて見た日は残す
                    first = cur.get("first_seen")
                    newer = dict(rec)
                    newer["first_seen"] = min(first, day) if (first and day) else (first or day)
                    newer["last_seen"] = max(cur.get("last_seen") or "", day or "") or None
                    newer["mode"] = cur["mode"]
                    by_key[k] = newer

    # 最新の保存日に載っているか
    for rec in by_key.values():
        if rec["mode"] == "snapshot":
            rec["listed"] = (rec["last_seen"] == latest_day.get(rec["source"]))
        else:
            rec["listed"] = True

    by_key, merged_away = merge_across_sources(by_key)
    enriched = enrich_from_ocr(by_key, load_ocr())

    # 地域をそろえる（ページで市区町村ごとに束ねるため）
    for rec in by_key.values():
        pref, city, ward, guess = place_of(rec)
        rec["pref"] = pref
        rec["city"] = city or rec.get("city") or ""
        rec["ward"] = ward or ""
        rec["area"] = (city or pref) + (ward if city in ("大阪市", "堺市", "神戸市") else "")
        if guess:
            rec["place_guess"] = True


    all_recs = sorted(by_key.values(),
                      key=lambda r: (r.get("notified_on") or "", r["source"], r["store"]), reverse=True)

    hidden = apply_privacy(all_recs)
    unstamped = stamp_sources(all_recs)
    if unstamped:
        print(f"注意: source_url か fetched_on を付けられなかったレコード {unstamped} 件")

    with open(OUT_ALL, "w", encoding="utf-8") as f:
        json.dump(all_recs, f, ensure_ascii=False, indent=1)

    # ---- まとめ ----
    lines = [f"# まとめ（{len(all_recs):,} 件）", "",
             f"収集先をまたいで同じ届出だったものを {merged_away} 件まとめた（移譲市町の届出は市のページと大阪府のExcelの両方に載るため）。",
             f"スキャンPDFをOCRで読んだ結果から、所在地・設置者などを {enriched} 件に補った。",
             f"設置者が個人だった {hidden} 件は、氏名を「個人」にして所在地を町丁目まで丸めた（共通仕様3.1）。", ""]
    lines.append("| 収集先 | 件数 | 新設 | 変更 | 廃止 | 承継 | 最新の保存日 | 消えた |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: |")
    per = defaultdict(list)
    for r in all_recs:
        per[r["source"]].append(r)
    gone_all = []
    for src in sorted(per):
        rs = per[src]
        kinds = Counter(r["kind"] for r in rs)
        gone = [r for r in rs if r["mode"] == "snapshot" and not r["listed"]]
        gone_all += gone
        lines.append(f"| {src} | {len(rs)} | {kinds.get('新設',0)} | {kinds.get('変更',0)} | "
                     f"{kinds.get('廃止',0)} | {kinds.get('承継',0)} | {latest_day.get(src,'—')} | {len(gone)} |")
    lines.append("")

    if gone_all:
        lines.append("## ページから消えた届出（縦覧が終わったもの）")
        lines.append("")
        lines.append("| 最後に見た日 | 収集先 | 種類 | 店舗 | 届出日 |")
        lines.append("| --- | --- | --- | --- | --- |")
        for r in sorted(gone_all, key=lambda r: r["last_seen"], reverse=True)[:50]:
            lines.append(f"| {r['last_seen']} | {r['source']} | {r['kind']} | {r['store']} | {r['notified_on']} |")
        lines.append("")

    # これから起きること
    today = max(latest_day.values()) if latest_day else ""
    future = [r for r in all_recs if (r.get("event_on") or r.get("planned_on") or "") > today]
    if future:
        lines.append(f"## これから起きる予定（{len(future)} 件）")
        lines.append("")
        lines.append("| 予定日 | 種類 | 市区 | 店舗 | 面積㎡ |")
        lines.append("| --- | --- | --- | --- | ---: |")
        for r in sorted(future, key=lambda r: r.get("event_on") or r.get("planned_on"))[:40]:
            place = r.get("city") or r.get("ward") or r.get("address", "")[:8]
            lines.append(f"| {r.get('event_on') or r.get('planned_on')} | {r['kind']} | {place} | {r['store']} | {r.get('area_m2') or ''} |")
        lines.append("")

    with open(OUT_SUM, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("\n".join(lines[:14]))
    print(f"\n→ {OUT_ALL} と {OUT_SUM} に書いた")

    gh = os.environ.get("GITHUB_STEP_SUMMARY")
    if gh:
        with open(gh, "a", encoding="utf-8") as f:
            f.write("\n" + "\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
