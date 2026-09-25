#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""日ごとに取り出した届出を、1件1行にまとめる。

data/parsed/<id>/<日付>.json は「その日にページに載っていたもの」。
毎日とるので、同じ届出が日の数だけ並ぶ。ここで目印（key）ごとにまとめて、

  first_seen … はじめて見た日
  last_seen  … 最後に見た日
  listed     … いまも載っているか。**3つの値**（listed_wo_kimeru）
                 true   最新の観測日に見えている
                 false  最後に見えた日のあとの、**取得がそろった観測**で見えなかった
                 null   そのあとの観測が、どれも取得がそろっていない（未判定）
  kieta_kakunin … listed が false のとき、見えなかった最初の「そろった観測」の日

を付ける。**「その日の取得結果に無かった」だけでは、消えたとしない。**
取らなかったページの届出も「その日に無かった」に見えるから（2026-09-24、堺市）。
取得がそろっていたかは parse.py が書く台帳（data/ref/kansoku-kanzen.json）で見る。
**なぜ見えなくなったかは確かめていない。**見えなくなったあとも、ここには残る。

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
    "kaizuka-city": ("大阪府", "貝塚市"),   # 抜けていた。所在地欄が空なので area が空になり、名前の無いページ a/.html が26件ぶん出ていた
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
# 郡のある町村を先に見る。「神崎郡市川町」を CITY で読むと最初の「市」で切れて「神崎郡市」になる（監査）
GUN_TOWN = re.compile(r"^(?:大阪府|兵庫県)?([^\s]{1,3}郡[^\s]{1,4}?[町村])")
CITY = re.compile(r"^(?:大阪府|兵庫県)?([^\s]{1,6}?[市町村])")
# 住所の頭に付く都道府県名。収集先で県が決まっているのに別の県から始まる住所は、店舗の所在地ではない
PREF_HEAD = re.compile(r"^(北海道|東京都|京都府|大阪府|[^\s]{2,3}県)")


def place_of(r):
    """(都道府県, 市, 区, 当て推量か) を返す。"""
    pref, city = SOURCE_PLACE.get(r["source"], ("", None))
    addr = (r.get("address") or "").strip()
    ward = ""
    guess = False
    # 県が決まっている収集先なのに、住所が別の県から始まる → 店舗の所在地ではない
    # （兵庫県の表で「イオン山崎SC」の所在が「愛媛県松山市…」になっていた。設置者の住所が混ざった）。
    # 捨てずに address_suspect に退避し、所在地は店名から当てる側に回す（共通仕様9）
    m = PREF_HEAD.match(addr)
    if pref and m and m.group(1) != pref:
        r["address_suspect"] = addr
        r["address"] = ""
        addr = ""
    if r["source"] == "osaka-city":
        ward = (r.get("ward") or "").strip()
        ward = ward + "区" if ward and not ward.endswith("区") else ward
    elif city in ("堺市", "神戸市"):
        m = WARD.match(addr)
        ward = m.group(1) if m else ""
    if city is None:
        c = (r.get("city") or "").strip()
        if not c:
            m = GUN_TOWN.match(addr) or CITY.match(addr)
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


def gun_table(recs):
    """(都道府県, 町村名) → 郡名 の対応表を、手元のデータの住所から作る。

    同じ町が「猪名川町」と「川辺郡猪名川町」の2つの名前に割れて、市区町村ページが
    2枚できていた（監査）。郡は住所に実際に書いてあるものから取る。記憶で書かない。
    太子町は大阪府（南河内郡）と兵庫県（揖保郡）の2つあるので、都道府県ごとに引く。
    """
    seen = defaultdict(Counter)
    for r in recs:
        pref = r.get("pref") or SOURCE_PLACE.get(r.get("source", ""), ("", None))[0]
        for s in (r.get("address") or "", r.get("city") or "", r.get("area") or ""):
            m = GUN_TOWN.match(s)
            if m:
                full = m.group(1)
                gun, town = full[:full.index("郡") + 1], full[full.index("郡") + 1:]
                seen[(pref, town)][gun] += 1
    return {k: c.most_common(1)[0][0] for k, c in seen.items()}


def with_gun(pref, city, table):
    """郡の無い町村名に、データで分かっている郡を付ける。分からなければそのまま。"""
    if city and "郡" not in city and re.fullmatch(r"[^\s]{1,4}[町村]", city):
        g = table.get((pref, city))
        if g:
            return g + city
    return city


# ---------------------------------------------------------------- 収集先をまたいだ重複をまとめる
# 大阪府が事務を移譲した市町（茨木・豊中・岸和田・箕面・枚方・門真・泉南…）の届出は、
# その市のページと大阪府の月次Excelの両方に載る。箕面市のページは2つの入口から届く。
# 同じ届出が2回数えられるので、店名・届出日・条文が同じものを1件にまとめる。
def norm_store(s):
    """店名を寄せる。**法人格の落とし方は `privacy.corp_core` が正本。**

    2026-09-20 まで、ここが法人格の一覧を**自分で持っていた**（`株式会社|㈱` の2語だけ）。
    そのせいで2つ落としていた。

    **① 全角の英数字がそろっていなかった。** `corp_core` が通している NFKC が
    ここには無く、`ｍｅｇａ…` と `mega…` が**別の店**として残っていた。
    同じ届出が2件のまま数えられていた。

    **② `(株)` が `株` になっていた。** 括弧だけ先に落ちて、法人格の語に当たらない。

    **同じ知識を2か所に置くと、片方に足した日に、もう片方が黙る。**
    `corp_core` を先に通してから、店名だけの記号（仮称・中黒・長音）を落とす。
    """
    return re.sub(r"[（）()仮称・･ー－\-]", "", privacy.corp_core(s)).lower()


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
            # **3つの値のまま合わせる。**どこかに見えていれば true。
            # 見えなくなったと言えるのは、どの収集先でも false のときだけ（1つでも未判定なら未判定）
            ls_ = [r.get("listed") for r in snaps]
            base["listed"] = (True if any(v is True for v in ls_)
                              else False if all(v is False for v in ls_) else None)
            kk = [r["kieta_kakunin"] for r in snaps if r.get("kieta_kakunin")]
            base.pop("kieta_kakunin", None)
            if base["listed"] is False and kk:
                base["kieta_kakunin"] = max(kk)
            # kakunin_saigo（完全観測の日のうち、見えた最後の日）も、どの収集先でも同じ意味なので
            # いちばん新しいものを残す（last_seen と同じ寄せ方）
            ks = [r["kakunin_saigo"] for r in snaps if r.get("kakunin_saigo")]
            base.pop("kakunin_saigo", None)
            if ks:
                base["kakunin_saigo"] = max(ks)
            fs = [r["first_seen"] for r in snaps if r.get("first_seen")]
            ls = [r["last_seen"] for r in snaps if r.get("last_seen")]
            base["first_seen"] = min(fs) if fs else None
            base["last_seen"] = max(ls) if ls else None
        base["sources"] = sorted(srcs)
        # 収集先ごとの「見た日」と「読んだファイル」。合流すると土台の last_seen しか
        # 残らず、相手の出典の行に別の収集先のページを見た日が出ていた（3.5）
        base["seen_by"] = {r["source"]: (r.get("last_seen") or r.get("first_seen") or "")
                           for r in g if (r.get("last_seen") or r.get("first_seen"))}
        fb = {r["source"]: r["file"] for r in g if r.get("file")}
        if fb:
            base["file_by"] = fb
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
                    val = tidy_ocr(o[okey])
                    # 「変更した事項」の行は様式の文言や氏名の変更（「設置者の氏名 ○○から△△へ」）が
                    # 混ざりうる。氏名・代表者に触れる行は使わない（privacy を通らない欄なので、入口で止める）
                    if field == "content" and (re.search(r"氏名|代表者", val)
                                              or ADDR_SHAPE.search(val) or ADDR_HYPHEN.search(val)):
                        # 「変更した事項」の次の行は、様式の文言・氏名の変更・住所が来ることがある。
                        # content は privacy を通らない欄なので、入口で止める（3.1）
                        continue
                    r[field] = val
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


# ------------------------------------------------- 取得がそろった観測だけを根拠にする
KANZEN_DAICHO = os.path.join(HERE, "data", "ref", "kansoku-kanzen.json")


def kanzen_na_hi(path=KANZEN_DAICHO):
    """収集先ごとの「取得がそろっていた日」の並び。**(日, 観測元, 取得方式) の3つ組**（parse.py が書く台帳から）。

    **台帳が無ければ空。**どの日も、そろったとは言わない（見えなくなったと名乗らない側に倒す）。
    観測元・取得方式まで持ち帰るのは、消失判定で**同じ観測元・取得方式どうしでしか比べない**ため
    （`listed_wo_kimeru`。観測元が変わった回を、前の回と比べると中身と関係なく全部が入れ替わって見える）。
    """
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
    except (FileNotFoundError, ValueError):
        return {}
    out = {}
    for src, days in d.items():
        if not isinstance(days, dict):
            continue
        out[src] = sorted((day, v.get("moto"), v.get("houshiki"))
                          for day, v in days.items() if isinstance(v, dict) and v.get("kanzen") is True)
    return out


def _saigo_no_kanzen_hi(days_seen, kanzen_days):
    """**完全観測の日のうち、見えた最後の日**（kakunin_saigo）。無ければ None。"""
    cands = [d for d, _, _ in kanzen_days if d in days_seen]
    return max(cands) if cands else None


def listed_wo_kimeru(days_seen, latest, kanzen_days):
    """snapshot の記録が、いまも載っているか。**(listed, kieta_kakunin, kakunin_saigo)** を返す。

    days_seen    この届出が見えた日の集合（**取得がそろっていたかに関係なく、全部**）
    latest       その収集先の、いちばん新しい観測日
    kanzen_days  その収集先の「取得がそろっていた日」の並び。(日, 観測元, 取得方式) の3つ組。昇順

        (True, None, kakunin_saigo)   最新の観測日に見えている
        (False, C, kakunin_saigo)     kakunin_saigo（**完全観測の日のうち、見えた最後の日**）の
                                      あとの最初の完全観測の日 C が、kakunin_saigo の日と
                                      観測元・取得方式が同じで、C より後（完全かどうかに関係なく）
                                      も見えていない
        (None, None, kakunin_saigo か None)  それ以外（未判定）

    **消失判定用の時点は、取得がそろった観測だけで進める**（共通指示書4）。
    2026-09-24、堺市で「消えて戻った」33鍵が、全部こちらの取りこぼしだった
    （2階層目の上限で年度のページを取らなかった日に、そのページの届出が
    「その日に無かった」と数えられていた）。見えた日は、取得がそろっていなくても
    見えたことの証拠になる。**見えなかったことの証拠になるのは、そろった観測だけ。**

    kakunin_saigo が無い（完全観測で一度も見えていない）ときは、常に未判定。
    C の観測元・取得方式が kakunin_saigo と違えば、比べない（未判定のまま）。
    C のあとに（完全でない回でも）また見えたら、「消えた」は言わない——未判定に戻す。
    """
    days_seen = days_seen or set()
    kanzen_days = kanzen_days or []
    kakunin_saigo = _saigo_no_kanzen_hi(days_seen, kanzen_days)
    if latest and latest in days_seen:
        return True, None, kakunin_saigo
    if not kakunin_saigo:
        return None, None, None
    saigo_moto, saigo_hs = next((m, h) for d, m, h in kanzen_days if d == kakunin_saigo)
    ato = [(d, m, h) for d, m, h in kanzen_days if d > kakunin_saigo]
    if not ato:
        return None, None, kakunin_saigo
    c_hi, c_moto, c_hs = ato[0]
    if c_moto != saigo_moto or c_hs != saigo_hs:
        return None, None, kakunin_saigo     # 観測元・取得方式が変わった。比べない
    if any(hi > c_hi for hi in days_seen):
        return None, None, kakunin_saigo     # そろっていない回でも、また見えた。未判定に戻す
    return False, c_hi, kakunin_saigo


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
      1. data/files/fetched.json … Excel・PDF から取り出したもの（file がある）は、
         そのファイルをダウンロードした日。大阪市の一覧はファイル名の日付（2026-06-30）で
         parsed に置くので、first_seen を先に見ると「一覧の日付」を取得日と書いてしまう
      2. last_seen / first_seen … 毎日巡回している収集先。実際に見た日
      3. 公報の台帳 issues.json の when … 兵庫県公報。PDFを取った日
      4. data/files/fetched.json を文書URLの末尾で引く … 部会の議案など
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

        def when_for(sid):
            """収集先 sid の取得日。

            引けるのは「その収集先の台帳に載っている日」だけにする。合流した記録では、
            相手の文書や相手のページを見た日が分からないことがあり、そこで土台の
            last_seen（別の収集先のページを見た日）を使うと、公報や部会の行に
            関係のない日付が出る（審査で見つかった。部会の取得日が4通りに割れていた）。
            分からないときは空にして「取得日の記録なし」と書く（3.5。黙って埋めない）。
            """
            fn = (r.get("file_by") or {}).get(sid) or (r.get("file") if sid == src else "")
            if fn:
                w = file_when.get(f"{sid}/{fn}", "") or ""
                if w:
                    return w
            for u in docs:                       # その収集先の台帳で引けた文書だけ
                base = os.path.basename(u.split("?")[0])
                w = file_when.get(f"{sid}/{base}", "") or ""
                if w:
                    return w
                if sid == "hyogo-koho":
                    w = koho_when.get(u, "") or ""
                    if w:
                        return w
            if sid not in DOC_SOURCES:           # 毎日巡回している収集先。実際に見た日
                seen = (r.get("seen_by") or {}).get(sid)
                if seen:
                    return seen
                if sid == src:
                    return r.get("last_seen") or r.get("first_seen") or ""
            return ""

        when = when_for(src)
        r["fetched_on"] = when
        srcs = r.get("sources") or []
        if len(srcs) > 1:
            r["fetched_by"] = {sid: (when if sid == src else when_for(sid)) for sid in srcs}
        else:
            r.pop("fetched_by", None)
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

# 設置者の欄に住所の形（「…1丁目2番3号」）の値が来ているもの。列ずれの疑い。
# 個人として伏せるのは同じだが、黙って「個人」にせず記録に残す（5節「個人に化けてはいけないもの」）
ADDR_SHAPE = re.compile(r"[0-9０-９一二三四五六七八九十]+\s*(番地|番|号|丁目)")
# ハイフンで書いた地番（「大阪市西区新町1-27-9」「加古川市野口町174-1」）。
# 「番地」などの語が無いので ADDR_SHAPE では拾えない。数字とハイフンの並びだけでは
# 日付や受理番号と見分けられないので、市区町村の名前が手前にあるときだけ住所と見る。
# 監査で、この形の地番が OCR の文と知らない列をすり抜けていた
ADDR_HYPHEN = re.compile(
    r"[^\s　]{1,6}[市区郡町村][^\s　]{0,12}?[0-9０-９]+\s*[-‐−－ー―]\s*[0-9０-９]+")


def squash_ws(s):
    """空白（全角も）を全部落とす。値どうしを突き合わせるときに使う。"""
    return re.sub(r"[\s　]+", "", str(s or ""))
# 「住所の形」は、都道府県か市区郡町村で始まり、かつ数字＋番地・番・号・丁目を含むもの。
# 数字＋番だけだと「一番館」「二丁目食堂」「一番ヶ瀬」のような屋号・姓まで拾う。
# 「氏名 住所」が1つの欄に入っているものは先頭が住所でないので拾わず、従来どおり「個人」に倒す
ADDR_HEAD = re.compile(r"^(北海道|東京都|京都府|大阪府|[^\s]{2,3}県|[^\s]{1,6}(市|区|郡|町|村))")
ADDR_IN_NAME_DISPLAY = "不詳（届出の一覧では設置者の欄に住所だけが書かれています）"   # 画面用。「個人」とは書かない
# 店名の欄に「店名＋住所」を書いている収集先がある（松原市など）。設置者が個人で
# 所在地を丸めるときは、店名の末尾にくっついた住所も丸める。そうしないと、
# 所在地だけ町丁目にしても店名に地番が残る（3.1）。
# 「雲井通6丁目地区…ビル」のような町名入りの店名を壊さないよう、
# 空白で区切られた末尾が住所の形のときだけ直す
_ADDR_TAIL = re.compile(r"[\s　]+((?:[^\s　]{1,6}[市区郡町村])?[^\s　]*"
                        r"(?:[0-9０-９一二三四五六七八九十]+\s*(?:丁目|番地)|[0-9０-９]+\s*番\s*[0-9０-９])"
                        r"[^\s　]*)(?:[\s　]*(?:ほか|他|外)[0-9０-９]*筆?[^\s　]*)?$")


def round_store_tail(store):
    """店名の末尾にくっついた住所を町丁目まで丸める。住所が無ければそのまま。"""
    m = _ADDR_TAIL.search(store or "")
    if not m:
        return store
    return store[:m.start(1)] + privacy.redact_addr(m.group(1), "individual")


def looks_like_address(raw):
    raw = (raw or "").strip()
    return (bool(raw) and bool(ADDR_HEAD.match(raw))
            and bool(ADDR_SHAPE.search(raw) or ADDR_HYPHEN.search(raw))
            and not privacy.is_corp(raw))


# 記録用に値そのものは残さない。ADDR_HEAD は「山田太郎大阪市…」のように
# 氏名がくっついた値にも先頭から当たってしまい、丸めても氏名が残るため
# （審査で見つかった）。どの行かは 収集先・ファイル・鍵・店舗 で引ける。

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

# 知らない列（extra）の列名が、当事者の「名前そのもの」を指しているかは
# privacy.is_party_column が決める。parse.py と同じ判定を使う（監査で、
# 同じ判定を別々に持っていて落とす記号が違い、「設置者（氏名）」が
# merge 側だけすり抜けていた）
# 文の中に伏せた氏名が混ざっていたときの書き方。どこまでが名前かは決められないので、
# 値ごと伏せる。伏せたことは書く（3.1）
EXTRA_NAME_HIDDEN = "（氏名が入っているため伏せています）"
# 「代表者 架空花子」のように、値の頭に人を指す語があって、そのあとが名前のもの。
# 区切り（空白か：）を必ず求める。これが無いと「代表者変更のため」
# （実物に10件ある）まで名前と読んでしまう。名前の側は空白を含んでよい
# （「架空 花子」。監査で、空白なしの1語しか拾えていなかった）
EXTRA_NAME_HEAD = re.compile(
    r"^(氏名|名義人?|代表者|代表取締役|取締役|届出者|申請者|設置者|所有者)"
    r"(?:\s*[:：]\s*|[\s　]+)(.+)$")


def apply_privacy(recs):
    """氏名と所在地を、共通仕様 3.1 の粒度に落とす。

    返すのは **(丸めた件数, 元から所在地が無かった件数)。**

    2026-09-20 に分けた。**「伏せた」と名乗っていた 823 件のうち 436 件は、
    取ってきた一覧に所在地の欄がそもそも無かった。**
    丸めるものが無いのに「町丁目まで丸めた」と書いていた（ルール⑥）。
    神戸市と兵庫県の縦覧は、一覧のページに所在地の列が無い（実物で確かめた）。

    **「こちらが伏せた」と「向こうが載せていない」は別のこと。**
    読者にとっては、前者は「あるが見せない」、後者は「探しても無い」。
    """
    hidden = nakatta = 0
    for r in recs:
        kinds = {}
        raw_party = {}      # 伏せる前の当事者の値。下の extra の掃除で使う
        for f in PARTY_FIELDS:
            raw = r.get(f)
            if raw is None:
                # 欄そのものが無い。収集先をまたいでまとめたときに運ばれてきた古い印
                # （_kind / _display / _suspect）だけが残っていることがあるので、捨てる。
                # 印だけ残ると、当事者のいない記録に undisclosed や individual が付く
                for k in ("_kind", "_display", "_suspect", "_suspect_value"):   # _suspect_value は古い版の名残
                    r.pop(f + k, None)
                continue
            if r.get(f + "_display") and not (raw or "").strip():
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
            raw_party[f] = raw          # 伏せる前に控える。この下で r[f] は上書きされる
            kind = privacy.party_kind(raw, disclosed=disclosed)
            kinds[f] = kind
            r[f] = privacy.party_for_index(raw)      # 機械用。個人は空文字
            r[f + "_display"] = privacy.redact_name(raw)   # 画面用。個人は「個人」
            r[f + "_kind"] = kind
            r.pop(f + "_suspect", None)
            r.pop(f + "_suspect_value", None)
            if kind == "individual" and looks_like_address(raw):
                # 名前の欄に住所だけが書かれている（大阪府の一覧に実例。法人の本社住所が入っている行がある）。
                # 名前は読めないので、伏せる側（individual・地番は丸める）に倒すのは同じだが、
                # 画面に「個人」と書くと事実と違うので、そう書かずに理由を書く。記録にも残す（5節）。
                # 記録用の値は町丁目まで。地番が残る形（漢数字の番地）なら値は残さない
                r[f + "_suspect"] = "address"
                r[f + "_display"] = ADDR_IN_NAME_DISPLAY

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
        r.pop("address_nakatta", None)
        raw_addr, raw_store = r.get("address"), r.get("store")
        # **元から所在地が無かったのなら、伏せたとは名乗らない。**
        # 丸めるかどうかとは別に決まる（法人でも、載っていなければ空）
        if not (raw_addr or "").strip():
            r["address_nakatta"] = True
            nakatta += 1
        if round_it:
            r["address"] = privacy.redact_addr(r.get("address") or "", "individual")
            if r.get("store"):
                r["store"] = round_store_tail(r["store"])
            if (raw_addr or "").strip():
                r["address_redacted"] = True
            hidden += 1

        # 知らない列（extra）は privacy を通らないまま公開されていた。
        # 表の結合セル（colspan）で他の欄の値がそのまま複製されることがあり、
        # 住所の列が見出しの書き方の違いで address に入らないこともある（3.1）
        extra = r.get("extra")
        if isinstance(extra, dict):
            # 突き合わせる値は「伏せる前」のもの。伏せたあとの値で作ると、個人の氏名は
            # 空文字になっていて一覧に入らず、extra に残った同じ氏名が privacy を
            # 通らないまま公開される（監査で再現された穴）。
            # 丸めたあとに通す。丸める前の値（raw_addr / raw_store）も一覧に入れる。
            # 片方だけだと、1回目と2回目で結果が変わる（丸めた値どうしが2回目に
            # 初めて一致して、そこで初めて消える）
            known = {squash_ws(v) for v in raw_party.values()}
            known |= {squash_ws(r.get(f)) for f in PARTY_FIELDS + ("address", "store")}
            known |= {squash_ws(raw_addr), squash_ws(raw_store)}
            known.discard("")
            # 「―」「なし」は名前の代わりに書かれている文言で、値そのものではない。
            # 複製として消すと、その列があったことまで消える（監査で見つかった）
            known = {v for v in known if not privacy.is_placeholder(v)}
            # 伏せた個人の氏名。extra の文の中に「代表者 ○○」の形で混ざることがある。
            # 2文字の姓は店名や法人名に偶然入りうるので、3文字以上だけを突き合わせる
            hidden_names = {squash_ws(raw_party.get(f)) for f, kind in kinds.items()
                            if kind == "individual"}
            hidden_names = {n for n in hidden_names
                            if len(n) >= 3 and not privacy.is_placeholder(n)}
            for k in list(extra):
                v = str(extra[k] or "").strip()
                if not v:
                    continue
                if squash_ws(v) in known:            # 他の欄の複製。二重に持たない
                    del extra[k]
                elif privacy.is_party_column(k):
                    # 当事者の名前の列。列の対応づけから漏れていただけなので、
                    # 当事者の欄と同じ規則を当てる（法人はそのまま、個人は「個人」）
                    extra[k] = privacy.redact_name(v)
                elif any(n in squash_ws(v) for n in hidden_names):
                    extra[k] = EXTRA_NAME_HIDDEN
                elif EXTRA_NAME_HEAD.match(v):
                    # 「代表者 ○○」。○○ を当事者と同じ規則で出す（法人ならそのまま）
                    m = EXTRA_NAME_HEAD.match(v)
                    extra[k] = f"{m.group(1)} {privacy.redact_name(m.group(2))}"
                elif looks_like_address(v) or (ADDR_SHAPE.search(v) and not privacy.is_corp(v)):
                    extra[k] = privacy.redact_addr(v, "individual")
            # 伏せたり丸めたりした結果、空になった列と、他の欄の複製になった列は持たない。
            # ここでもう一度見ないと、丸めた住所が2回目に初めて他の欄と一致して、
            # そのとき初めて消える（1回目と2回目で結果が変わる）
            for k in list(extra):
                v = str(extra[k] or "").strip()
                if not v or squash_ws(v) in known:
                    del extra[k]
            if not extra:
                r.pop("extra", None)
    return hidden, nakatta


UNKNOWN_MD = os.path.join(HERE, "data", "parse-unknown.md")
SUSPECT_HEAD = "## 個人に化けた疑いのある値（設置者の欄に住所の形）"


def write_suspects(recs):
    """住所の形をした設置者名を data/parse-unknown.md の節に書く（5節）。無ければ節を消す。

    印（_suspect）は記録に付いているので、ここでは記録から拾う。検出は値が入っている
    最初の1回だけだが、印と丸めた値は伏せたあとも残るので、2回目以降も一覧に出る。
    """
    SUSPECTS = sorted({(r.get("source", ""), r.get("file") or "", r.get("key", ""), r.get("store", ""))
                       for r in recs for f in PARTY_FIELDS if r.get(f + "_suspect") == "address"})
    try:
        with open(UNKNOWN_MD, encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        text = "# 読み落としたもの\n"
    # 前回の節を落としてから書き直す
    text = re.sub(re.escape(SUSPECT_HEAD) + r".*?(?=\n## |\Z)", "", text, flags=re.S).rstrip("\n") + "\n"
    if SUSPECTS:
        lines = ["", SUSPECT_HEAD, "",
                 f"{len(SUSPECTS)} 件。個人として伏せてある。値は載せない"
                 "（住所の前に氏名が付いていることがあるため。元の表で確かめる）。", "",
                 "| 収集先 | ファイル | 鍵 | 店舗 |", "|---|---|---|---|"]
        for src, fn, key, store in SUSPECTS:
            lines.append(f"| {src} | {fn} | {key} | {store} |")
        text += "\n".join(lines) + "\n"
    os.makedirs(os.path.dirname(UNKNOWN_MD), exist_ok=True)
    with open(UNKNOWN_MD, "w", encoding="utf-8") as f:
        f.write(text)
    if SUSPECTS:
        print(f"設置者の欄に住所の形の値: {len(SUSPECTS)} 件（data/parse-unknown.md に書いた）")


def main():
    scrubbed = scrub_parsed()
    if scrubbed:
        print(f"日ごとのファイル {scrubbed} 枚から氏名と地番を落とした（共通仕様3.1）")

    by_key = {}
    latest_day = {}                     # 収集先ごとの、いちばん新しい保存日
    days_seen = defaultdict(set)        # 鍵ごとに見えた日の集合（取得がそろっていたかに関係なく、全部）

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
                if day and not cumulative:
                    days_seen[k].add(day)
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

    # いまも載っているか。**取得がそろった観測だけを、見えなくなった根拠にする**（listed_wo_kimeru）。
    # 消失判定用の時点（kakunin_saigo）も、取得がそろった観測だけで進める（共通指示書4）
    kanzen = kanzen_na_hi()
    for rec in by_key.values():
        rec.pop("kieta_kakunin", None)
        rec.pop("kakunin_saigo", None)
        if rec["mode"] == "snapshot":
            rec["listed"], kakunin, saigo = listed_wo_kimeru(
                days_seen.get(rec["key"]), latest_day.get(rec["source"]), kanzen.get(rec["source"], []))
            if kakunin:
                rec["kieta_kakunin"] = kakunin
            if saigo:
                rec["kakunin_saigo"] = saigo
        else:
            rec["listed"] = True

    by_key, merged_away = merge_across_sources(by_key)
    enriched = enrich_from_ocr(by_key, load_ocr())

    # 地域をそろえる（ページで市区町村ごとに束ねるため）
    guns = gun_table(by_key.values())
    for rec in by_key.values():
        pref, city, ward, guess = place_of(rec)
        city = with_gun(pref, city or rec.get("city") or "", guns)
        rec["pref"] = pref
        rec["city"] = city or ""
        rec["ward"] = ward or ""
        rec["area"] = (city or pref) + (ward if city in ("大阪市", "堺市", "神戸市") else "")
        if guess:
            rec["place_guess"] = True


    all_recs = sorted(by_key.values(),
                      key=lambda r: (r.get("notified_on") or "", r["source"], r["store"]), reverse=True)

    hidden, addr_nakatta = apply_privacy(all_recs)
    unstamped = stamp_sources(all_recs)
    if unstamped:
        print(f"注意: source_url か fetched_on を付けられなかったレコード {unstamped} 件")

    with open(OUT_ALL, "w", encoding="utf-8") as f:
        json.dump(all_recs, f, ensure_ascii=False, indent=1)

    # ---- まとめ ----
    lines = [f"# まとめ（{len(all_recs):,} 件）", "",
             f"収集先をまたいで同じ届出だったものを {merged_away} 件まとめた（移譲市町の届出は市のページと大阪府のExcelの両方に載るため）。",
             f"スキャンPDFをOCRで読んだ結果から、所在地・設置者などを {enriched} 件に補った。",
             f"設置者を法人と確かめられなかった {hidden:,} 件は、氏名を「個人」と書き、所在地を町丁目まで丸めた（共通仕様3.1）。",
             f"なお {addr_nakatta:,} 件は、**取ってきた一覧に所在地が入っていなかった**（伏せたのではない）。", ""]
    lines.append("| 収集先 | 件数 | 新設 | 変更 | 廃止 | 承継 | 最新の保存日 | 確認できなくなった | 未判定 |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: |")
    per = defaultdict(list)
    for r in all_recs:
        per[r["source"]].append(r)
    gone_all = []
    for src in sorted(per):
        rs = per[src]
        kinds = Counter(r["kind"] for r in rs)
        gone = [r for r in rs if r["mode"] == "snapshot" and r["listed"] is False]
        mitei = sum(1 for r in rs if r["mode"] == "snapshot" and r["listed"] is None)
        gone_all += gone
        lines.append(f"| {src} | {len(rs)} | {kinds.get('新設',0)} | {kinds.get('変更',0)} | "
                     f"{kinds.get('廃止',0)} | {kinds.get('承継',0)} | {latest_day.get(src,'—')} | {len(gone)} | {mitei} |")
    lines.append("")

    if gone_all:
        # **なぜ見えなくなったかは確かめていない**（縦覧が終わったとは限らない）
        lines.append("## 取得がそろった観測で確認できなくなった届出")
        lines.append("")
        lines.append("| 最後に見た日 | 確認できなかった観測 | 収集先 | 種類 | 店舗 | 届出日 |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for r in sorted(gone_all, key=lambda r: r["last_seen"], reverse=True)[:50]:
            lines.append(f"| {r['last_seen']} | {r.get('kieta_kakunin') or '—'} | {r['source']} | "
                         f"{r['kind']} | {r['store']} | {r['notified_on']} |")
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
    write_suspects(all_recs)

if __name__ == "__main__":
    main()
