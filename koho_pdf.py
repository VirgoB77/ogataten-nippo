"""兵庫県公報の本体PDFから、大規模小売店舗立地法の公告（新設・変更・廃止）を読み取る。

koho.py が目録から拾った公告には（発行日, 公報番号）が付いている。
月別一覧 → 月ページ → 「M月D日第N号」の PDF、とたどれば本体に着く。
本体の公告は決まった形で、店舗名・所在地・設置者・小売業者・店舗面積・
新設（変更・廃止）の日・届出年月日・縦覧場所が書いてある。

置き方の約束：
- PDF そのものは git に残さない（1冊 300KB × 1,400冊 で重すぎる）。
  かわりに **公報の全文** を data/koho/full/<日付>-<号>.txt.gz に残す。
  ここが生データで、姉妹サイトもここを読む（同じ公報を二度取りに行かせない）。
- data/koho/text/<日付>-<号>.txt は、そこから切り出した大店立地法の公告だけ。
  full があれば取りに行かずに作り直せるので、読み取りを直すと過去分にも効く。
- 月ページは一度読んだら data/koho/months/<年-月>.json に控えて、二度取りに行かない
- 1回の実行で読む号数に上限を置く（KOHO_MAX、既定 40）。新しい号から順に。続きは次回
- 取れなかった号は台帳 data/koho/issues.json に理由を残す。404 以外は次回やり直す
- 代表者の氏名など個人の名前は取り出さない（法人名だけ）

出力：data/parsed/hyogo-koho/all.json（過去分を全部含む一覧として merge.py が読む）。
文字ファイルは毎回読み直すので、読み取りを直せば過去の分にも効く。

姉妹サイトへ：全文はここから読める。兵庫県のサーバーには触らないこと。
  https://raw.githubusercontent.com/VirgoB77/ogataten-nippo/main/data/koho/full/<日付>-<号>.txt.gz
  号外は <日付>-g<n>.txt.gz（「号外」が g1、「第2号外」が g2。本体 PDF の名前 20251219g2.pdf と同じ数え方）
  号の一覧は data/koho/issues.json（status が done のものが取得済み）。

使い方: python3 shutten/koho_pdf.py
"""
import glob
import gzip
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import parse as P  # noqa: E402

HOST = "https://web.pref.hyogo.lg.jp"
NOTICES = os.path.join(HERE, "data", "koho", "hyogo-notices.json")   # 大店立地法の公告だけ
ISSUES = os.path.join(HERE, "data", "koho", "hyogo-issues.json")     # 目録に出てくる号を全部
INDEX_DIR = os.path.join(HERE, "data", "raw", "hyogo-koho-index")
MONTHS = os.path.join(HERE, "data", "koho", "months")
FULL = os.path.join(HERE, "data", "koho", "full")    # 公報の全文（gzip）。これが生データ
TEXTS = os.path.join(HERE, "data", "koho", "text")   # そこから切り出した大店立地法の公告だけ
LEDGER = os.path.join(HERE, "data", "koho", "issues.json")
OUT = os.path.join(HERE, "data", "parsed", "hyogo-koho")
REPORT = os.path.join(HERE, "data", "koho", "pdf-report.md")
SOURCE = "hyogo-koho"

from common.fetch import UA, check_robots, is_busy  # 名乗り・robots・混雑判定は common/fetch.py（共通仕様3.4）
WAIT = 5          # 共通仕様 3.4「同時1本・5秒以上」
TIMEOUT = 60
MAX_PDF = 6 * 1024 * 1024
MAX_ISSUES = int(os.environ.get("KOHO_MAX", "40"))
# 追いついたら月2回（共通仕様3.4）。過去分の積み直しの間だけ毎日。未読がこれ以下なら「追いついた」
CATCH_UP = 20                 # 週2回の発行 × 半月ぶん
FETCH_DAYS = (1, 15)          # 追いついたあとに取りに行く日
# 月ページの控えの版。2 は号外（「M月D日号外」「M月D日第N号外」）も読むようになった版。
# 古い版の控えは、1回の実行につき MONTH_REFRESH_MAX 月まで取り直す（相手のサーバーに一気に行かない）
MONTH_CACHE_V = 2
MONTH_REFRESH_MAX = int(os.environ.get("KOHO_MONTH_REFRESH", "40"))
_month_refreshed = 0
# 月ページの見出し。「12月19日第679号」「12月1日号外」「12月3日第2号外」「12月3日号外第2号」。
# 「第2号外」を「第2号」と読み違えないよう、号のあとに「外」が続くものは号外に回す
LABEL = re.compile(r"(\d{1,2})月(\d{1,2})日(?:第(\d+)号(?!外)|(?:第(\d+))?号外(?:第(\d+)号)?)")


def issue_no_of_label(lab):
    """月ページの見出し → (月, 日, 号)。号外は 'g1', 'g2' …。読めなければ None。

    全角の数字と空白は squash で先に直す（呼び出し側で直し忘れても同じに読めるように）。
    """
    m = LABEL.match(squash(lab))
    if not m:
        return None
    no = m.group(3) if m.group(3) else f"g{m.group(4) or m.group(5) or 1}"
    return (int(m.group(1)), int(m.group(2)), no)


def no_label(no):
    """'679' → '第679号'、'g1' → '号外'、'g2' → '第2号外'（人が読む文のため）。"""
    no = str(no)
    if no.startswith("g"):
        n = no[1:]
        return "号外" if n == "1" else f"第{n}号外"
    return f"第{no}号"


def fetch_today(backlog, today, force=False):
    """今日、県のサーバーに取りに行くか。積み直しの間（未読が多い間）は毎日、追いついたら月2回。"""
    if force or backlog > CATCH_UP:
        return True
    return today.day in FETCH_DAYS
FIRST_MONTH = (2007, 1)          # 月別一覧の最初のリンクが指す月
# 保存の仕方が変わったら上げる。台帳の v がこれより古い号は取り直す。
#   1 … 大店立地法の抜粋だけ残していた頃
#   2 … 公報の全文を full/ に残す
TEXT_VERSION = 2

Z2H = str.maketrans("０１２３４５６７８９（）：，、．－―", "0123456789():,,.--")


def z2h(s):
    return (s or "").translate(Z2H)


def squash(s):
    return re.sub(r"[\s　]+", "", z2h(s))


def get(url, limit=MAX_PDF):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*", "Accept-Encoding": "identity"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        data = r.read(limit + 1)
    if len(data) > limit:
        raise ValueError("大きすぎる")
    return data


_month_failed = {}   # この実行で取れなかった月ページ（同じ月を何十回も叩かないため）


# ---------------------------------------------------------------- 月別一覧 → 月ページ
def month_index():
    """月別一覧の保存ページから {'2023-06': '/kk32/koho/202306.html', ...} を作る。

    年の見出しが拾いにくいので、1月から順に並んでいることを頼りに 2007年1月から数える。
    月の名前が並び順と食い違ったら、そこで止めて安全側に倒す。
    """
    files = sorted(glob.glob(os.path.join(INDEX_DIR, "*.html")))
    if not files:
        return {}
    with open(files[-1], encoding="utf-8", errors="replace") as f:
        s = f.read()
    links = re.findall(r'<a[^>]+href="([^"]+)"[^>]*>\s*([0-9０-９]{1,2})月\s*</a>', s)
    out = {}
    y, m = FIRST_MONTH
    for href, mon in links:
        if int(z2h(mon)) != m:
            break                                   # 並びが崩れた。ここまでにする
        out[f"{y:04d}-{m:02d}"] = urllib.parse.urljoin(HOST, href)
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def month_links(ym, url, lines):
    """月ページの「M月D日第N号」「M月D日号外」→ PDF の URL の対応。控えがあればそれを使う。

    控えが古い版（号外を読んでいない）なら、1回の実行で MONTH_REFRESH_MAX 月まで取り直す。
    上限を超えた月は古い控えのまま返す（定期号は引ける。号外は次回以降）。
    """
    global _month_refreshed
    os.makedirs(MONTHS, exist_ok=True)
    cache = os.path.join(MONTHS, f"{ym}.json")
    old = None
    if os.path.exists(cache):
        with open(cache, encoding="utf-8") as f:
            old = json.load(f)
        if old.get("_v") == MONTH_CACHE_V:
            return old
        if _month_refreshed >= MONTH_REFRESH_MAX:
            return old                   # 今回の取り直しの上限。古い控え（定期号だけ）で進む
    if ym in _month_failed:
        return old                       # この実行で一度取れなかった月は、もう叩かない
    try:
        html_ = get(url, limit=2_000_000).decode("utf-8", errors="replace")
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError) as e:
        lines.append(f"  - 月ページが取れなかった {ym} — {type(e).__name__}: {str(e)[:60]}")
        _month_failed[ym] = e
        time.sleep(WAIT)                 # 失敗でも要求は出している。次まで5秒あける
        if is_busy(e):
            raise                        # 混んでいるなら、その回は中止（呼び出し側で止める）
        return old
    time.sleep(WAIT)
    if old is not None:
        _month_refreshed += 1
    out = {"_v": MONTH_CACHE_V}
    for href, label in re.findall(r'<a[^>]+href="([^"]+\.pdf)"[^>]*>(.*?)</a>', html_, re.S | re.I):
        k = issue_no_of_label(re.sub(r"<[^>]+>", "", label))
        if k:
            out[f"{k[0]}-{k[1]}-{k[2]}"] = urllib.parse.urljoin(HOST, href)
    with open(cache, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=0)
    return out


# ---------------------------------------------------------------- PDF → 公告の文字
HEAD = re.compile(r"^\s*大規模小売店舗の(新設|変更|廃止)に関する届出\s*$")
LAW = re.compile(r"大規模小売店舗立地法")
NEXT_TITLE = re.compile(r"^\s{0,8}[^\s\d０-９（(○].{1,60}$")
PAGE_HEAD = re.compile(r"兵\s*庫\s*県\s*公\s*報|^\s*\d{1,3}\s*$|^\s*（\d+）\s*$")


def strip_page_furniture(text):
    """ページの上下に入る「令和５年６月20日 火曜日 兵庫県公報 第423号」とページ番号を落とす。"""
    out = []
    for ln in text.splitlines():
        if PAGE_HEAD.search(ln) and ("公" in ln or ln.strip().isdigit() or "（" in ln):
            continue
        out.append(ln)
    return out


def cut_sections(text):
    """本文から、大店立地法の公告のかたまりを切り出す。[(種類, 行のリスト), ...]"""
    lines = strip_page_furniture(text)
    starts = []
    for i, ln in enumerate(lines):
        m = HEAD.match(ln)
        if not m:
            continue
        nxt = " ".join(lines[i + 1:i + 4])
        if LAW.search(nxt):                         # 目次の行（……11）ではなく本文の見出し
            starts.append((i, m.group(1)))
    sections = []
    for n, (i, kind) in enumerate(starts):
        end = len(lines)
        # 次の公告の見出し：短い題名の行のすぐ後に「法律第…号」の引用が来る
        for j in range(i + 3, len(lines)):
            if NEXT_TITLE.match(lines[j]) and re.search(r"法律第\d+号|条例第\d+号|規則第\d+号", " ".join(lines[j + 1:j + 3])):
                end = j
                break
        if n + 1 < len(starts):
            end = min(end, starts[n + 1][0])
        sections.append((kind, lines[i:end]))
    return sections


# ---------------------------------------------------------------- 公告の文字 → 記録
ARTICLE = re.compile(r"第\s*([0-9０-９]+)\s*条\s*(?:の\s*[0-9０-９]+\s*)?第\s*([0-9０-９]+)\s*項")
DATE_LINE = re.compile(r"^\s*((?:平成|令和|昭和)\s*[0-9０-９元]+\s*年\s*[0-9０-９]+\s*月\s*[0-9０-９]+\s*日)\s*(?:ほか|など|から.*)?\s*$")   # 「令和７年８月１日ほか」も日付の行
ITEM = re.compile(r"^\s*([0-9０-９]{1,2})\s+(\S.*)$")


def value_after(lines, i, label):
    """「名称 ダイソーひめじ岡田店」形式なら同じ行から、無ければ次の空でない行から値を取る。"""
    ln = lines[i]
    m = re.search(rf"{label}\s+(\S.*)$", ln)   # label は「名\s*称」のような空白ゆれ込みの正規表現
    if m:
        return m.group(1).strip()
    for j in range(i + 1, min(i + 4, len(lines))):
        if lines[j].strip():
            return lines[j].strip()
    return ""


CORP = re.compile(r"(株式会社|有限会社|合同会社|合資会社|相互会社|生活協同組合|協同組合|農業協同組合|"
                  r"財団法人|社団法人|医療法人|学校法人|宗教法人|特定目的会社|組合|公社|機構|会館)")
# 「岡山県倉敷市堀南704番地の５」のような住所。列がずれて住所が先に来る公報を見分けるため
ADDRESS_LIKE = re.compile(r"^(?:北海道|東京都|京都府|大阪府|.{2,3}県)|[0-9０-９]+\s*(?:丁目|番地|番|号)")
ITEM_START = re.compile(r"^\s*(?:[0-9０-９]+\s|[(（][0-9０-９]+[)）]|[アイウエオ]\s)")
JUNK_NAME = re.compile(r"^(?:外|ほか)?未定[0-9０-９]*者?$|^所在他$")
# 折り返しの続きが「株式会社」だけの行。住所の続きが同じ行に並ぶことがある
CORP_TAIL = re.compile(r"^(株式会社|有限会社|合同会社|合資会社|相互会社)$")


def pick_name(line):
    """「名称 住所 代表者の氏名」の並びから名称の列を取る。

    ふつうは先頭の列。ただし列がずれて住所が先に来る公報があるので、
    先頭が住所に見えて別の列が法人名に見えるときは、そちらを採る。
    """
    parts = [x.strip() for x in re.split(r"\s{2,}", line.strip()) if x.strip()]
    if not parts:
        return ""
    if len(parts) > 1 and ADDRESS_LIKE.search(parts[0]) and not CORP.search(parts[0]):
        for x in parts[1:]:
            if CORP.search(x):
                return x
    return parts[0]


def name_from(lines, i):
    """lines[i] から名称を取り、次の行に折り返されていればつないで (名称, 次に見る行) を返す。

    長い法人名は列からはみ出して次の行に続く：
        三井住友トラスト・パナソニック    東京都港区…    西 野 敏 哉
        ファイナンス株式会社
    続きの行は「名称の列と同じ字下げ」で「列が1つだけ」なので、それで見分ける。
    """
    name = pick_name(lines[i])
    j = i + 1
    if not name or CORP.search(name):
        return name, j
    indent = len(lines[i]) - len(lines[i].lstrip())
    while j < min(i + 3, len(lines)):
        ln = lines[j]
        if not ln.strip() or ITEM_START.match(ln):
            break
        if abs((len(ln) - len(ln.lstrip())) - indent) > 1:
            break
        parts = [x for x in re.split(r"\s{2,}", ln.strip()) if x]
        # 続きの行に住所の続きが並ぶことがある。そのときは先頭が「株式会社」だけのときに限って拾う
        if len(parts) != 1 and not CORP_TAIL.match(parts[0]):
            break
        name += parts[0]
        j += 1
        if CORP.search(name):
            break
    return name, j


def parse_section(kind, lines, issue):
    text = "\n".join(lines)
    am = ARTICLE.search(z2h(text[:400]))
    article = f"第{int(am.group(1))}条第{int(am.group(2))}項" if am else {"新設": "第5条第1項", "廃止": "第6条第5項"}.get(kind, "")
    # 番号付きの項目に切る
    items = {}
    cur = None
    for ln in lines:
        m = ITEM.match(ln)
        if m and int(z2h(m.group(1))) <= 15 and not re.match(r"^\s*[0-9０-９]+\s*[,，]", ln):
            cur = re.sub(r"\s+", "", z2h(m.group(2)))
            items[cur] = []
        elif cur is not None:
            items[cur].append(ln)

    def item(pat):
        for k, v in items.items():
            if re.search(pat, k):
                return k, v
        return None, []

    rec = {"article": article, "kind": kind, "source": SOURCE,
           "gazette_date": issue["date"], "gazette_no": issue["no"], "docs": [issue["url"]]}
    # 名称・所在地
    k, v = item(r"名称及び所在地")
    for i, ln in enumerate(v):
        if re.search(r"^\s*名\s*称", ln) and "store" not in rec:
            rec["store"] = value_after(v, i, r"名\s*称")
        elif re.search(r"^\s*所\s*在\s*地", ln) and "address" not in rec:
            rec["address"] = re.sub(r"\s+", "", value_after(v, i, r"所\s*在\s*地"))
    # 設置者（法人名だけ。住所・代表者名は取らない）
    k, v = item(r"設置(している|する)者")
    for i, ln in enumerate(v):
        sq = squash(ln)
        if re.match(r"^名称\S", sq) and not re.match(r"^名称(住所|代表者)", sq):
            rec["operator"] = pick_name(re.sub(r"^\s*名\s*称\s+", "", ln))
            break
        if sq == "名称" or re.match(r"^名称(住所|代表者)", sq):
            for j in range(i + 1, min(i + 4, len(v))):
                if v[j].strip() and not re.match(r"^(住所|代表者)", squash(v[j])):
                    rec["operator"], _ = name_from(v, j)
                    break
            break
    # 小売業者（新設）
    k, v = item(r"小売業を行う者")
    names = []
    for i, ln in enumerate(v):
        sq = squash(ln)
        if re.match(r"^名称\S", sq) and not re.match(r"^名称(住所|代表者)", sq):
            names.append(pick_name(re.sub(r"^\s*名\s*称\s+", "", ln)))
        elif re.match(r"^名称(代表者|住所)", sq) or sq == "名称":
            j = i + 1
            while j < len(v):
                s2 = squash(v[j])
                if not s2 or re.match(r"^(住所|代表者)", s2):
                    j += 1
                    continue
                if re.match(r"^[0-9]", s2):
                    break
                nm, j = name_from(v, j)
                if nm:
                    names.append(nm)
            break
    names = [n for n in names if n and not JUNK_NAME.match(n)]
    if names:
        rec["retailer"] = "、".join(dict.fromkeys(names))
    # 日付と面積
    for pat, field in ((r"新設をする日|新設する日", "event_on"), (r"変更年月日|変更をする日", "event_on"),
                       (r"以下となる日|廃止する日|廃止の日", "event_on"), (r"届出年月日", "notified_on")):
        k, v = item(pat)
        for ln in v:
            dm = DATE_LINE.match(ln)
            if dm:
                rec[field] = P.to_iso(squash(dm.group(1)))
                break
    k, v = item(r"店舗面積の合計$|店舗面積の合計（|廃止前の店舗面積")
    for ln in v:
        mm = re.search(r"([0-9０-９,，]+)\s*平方メートル", z2h(ln))
        if mm:
            rec["area_m2"] = int(mm.group(1).replace(",", ""))
            break
    if kind == "変更":
        k, v = item(r"変更事項")
        heads = []
        for ln in v:
            t = re.sub(r"^\s*[(（][0-9０-９]+[)）]\s*", "", ln).strip()    # 「(1) 変更事項名」の番号を外す
            if not t or re.match(r"^[アイウエ]\s", t) or re.search(r"変更[前後]", t) or re.match(r"^[(（]", t):
                continue
            heads.append(re.sub(r"\s+", " ", t))
            break                                   # 事項名だけ。表の中身（住所・代表者の氏名）は取らない
        rec["content"] = heads[0][:80] if heads else ""
    k, v = item(r"縦覧場所及び縦覧期間|縦覧場所")
    pm = re.search(r"(阪神南|阪神北|東播磨|北播磨|中播磨|西播磨|但馬|丹波|淡路)", "\n".join(v))
    if pm:
        rec["region"] = pm.group(1)
    rec["review_from"] = issue["date"]
    if not rec.get("notified_on") or not rec.get("store"):
        return None
    rec["store"] = re.sub(r"\s+", " ", rec["store"]).strip()
    rec["key"] = P.make_key(SOURCE, rec)
    return rec


def parse_text_file(path):
    """data/koho/text の 1 ファイル（1 号ぶん）から記録を返す。"""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    m = re.match(r"(\d{4}-\d{2}-\d{2})-(\d+)\.txt$", os.path.basename(path))
    issue = {"date": m.group(1), "no": m.group(2), "url": ""}
    first = text.split("\n", 1)[0]
    if first.startswith("# "):                     # 1 行目に PDF の URL を書いてある
        issue["url"] = first[2:].strip()
    recs = []
    for kind, lines in cut_sections(text):
        r = parse_section(kind, lines, issue)
        if r:
            recs.append(r)
    return recs


# ---------------------------------------------------------------- 取りに行く
def load_ledger():
    if os.path.exists(LEDGER):
        with open(LEDGER, encoding="utf-8") as f:
            return json.load(f)
    return {}


def stem_of(issue):
    return f"{issue['date']}-{issue['no']}"


def save_full(issue, url, text):
    """公報の全文を残す。これが生データで、姉妹サイトもここを読む。

    絞り込みは出力の段階だけで行う（共通仕様 9）。取得時点で捨てると、
    あとから別の告示が要るようになったときに全部取り直しになる。実際になった。
    """
    os.makedirs(FULL, exist_ok=True)
    with gzip.open(os.path.join(FULL, stem_of(issue) + ".txt.gz"), "wt", encoding="utf-8") as f:
        f.write(f"# {url}\n")
        f.write(text)


def write_sections(issue, url, text):
    """全文から大店立地法の公告だけを切り出して text に置く。戻り値は公告の数。"""
    sections = cut_sections(text)
    os.makedirs(TEXTS, exist_ok=True)
    with open(os.path.join(TEXTS, stem_of(issue) + ".txt"), "w", encoding="utf-8") as f:
        f.write(f"# {url}\n")
        for kind, sec in sections:
            f.write("\n".join(sec).rstrip() + "\n\n")
    return len(sections)


def rebuild_from_full(lines):
    """手元の全文から抜粋を作り直す。取りに行かない。

    読み取りを直したときに、過去の号にもその場で効かせるためのもの。
    """
    n = 0
    for path in sorted(glob.glob(os.path.join(FULL, "*.txt.gz"))):
        stem = os.path.basename(path)[:-len(".txt.gz")]
        d, no = stem.rsplit("-", 1)
        with gzip.open(path, "rt", encoding="utf-8") as f:
            body = f.read()
        first, _, rest = body.partition("\n")
        url = first[2:].strip() if first.startswith("# ") else ""
        write_sections({"date": d, "no": no}, url, rest)
        n += 1
    if n:
        lines.append(f"- 手元の全文 {n} 号から抜粋を作り直した（取りに行っていない）")
    return n


def fetch_issue(issue, url, lines):
    """PDF を落として文字にし、全文を full に、大店立地法の公告を text に残す。"""
    data = get(url)
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name
    try:
        r = subprocess.run(["pdftotext", "-layout", tmp_path, "-"], capture_output=True, timeout=120)
        text = r.stdout.decode("utf-8", errors="replace")
    finally:
        os.remove(tmp_path)
    if not text_ok(r.returncode, text):
        # 文字が取れていないのに done にすると、空の全文が「取得済み」として
        # 姉妹サイトに渡る（監査）。full にも書かない
        raise ValueError("文字なし")
    save_full(issue, url, text)
    return write_sections(issue, url, text)


MIN_TEXT_CHARS = 200   # 公報1号ぶんの文字がこれより少ないことはない


def text_ok(returncode, text):
    """pdftotext が本当に文字を返したか。"""
    return returncode == 0 and len((text or "").strip()) >= MIN_TEXT_CHARS


# 何度取りに行っても同じ結果になる失敗。毎日叩かず、月に1回だけ確かめ直す
# （県が後から載せることはあるので、永久には諦めない）
PERMANENT = ("月ページに号が無い", "月ページが一覧に無い", "文字なし", "大きすぎる")
RECHECK_DAYS = 30


def needs_fetch(key, ledger, today=None):
    """この号を取りに行くか。"""
    e = ledger.get(key)
    if e is None:
        return True
    status = e.get("status", "")
    if status.startswith("done"):
        return e.get("v", 1) < TEXT_VERSION      # 全文を残す前に取った号は取り直す
    if "404" in status:
        return False
    if any(p in status for p in PERMANENT):
        when = e.get("when")
        if not when:
            return True                           # いつ調べたか分からないなら、もう一度だけ
        return (today or date.today()) - date.fromisoformat(when) >= timedelta(days=RECHECK_DAYS)
    return True                                   # 一時的な失敗は次回やり直す


def find_in_neighbor_year(d, no, index, lines):
    """目録の年が1年ずれている号を、前後1年の同じ月日で探す。

    兵庫県の目録は年始の行の年が前年のまま残っていることがあり、1月の号が
    「月ページに号が無い」になっていた（19件中8件がこれ）。号番号は通し番号なので、
    前後1年の同じ月日に同じ号番号があれば、それが本物。見つかれば (本当の日付, URL)。
    """
    y, m, dd = d.split("-")
    for yy in (int(y) + 1, int(y) - 1):
        ym2 = f"{yy:04d}-{m}"
        murl2 = index.get(ym2)
        if not murl2:
            continue
        links2 = month_links(ym2, murl2, lines)
        if links2 and f"{int(m)}-{int(dd)}-{no}" in links2:
            return f"{yy:04d}-{m}-{dd}", links2[f"{int(m)}-{int(dd)}-{no}"]
    return None, None


def save_ledger(ledger):
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    with open(LEDGER, "w", encoding="utf-8") as f:
        json.dump(ledger, f, ensure_ascii=False, indent=0, sort_keys=True)


def main():
    lines = ["# 兵庫県公報の本体から読んだ大店立地法の公告", ""]
    fetched = 0
    if os.path.exists(ISSUES) and shutil.which("pdftotext"):
        # 目録に出てくる号を全部取りに行く。大店立地法の号だけでは、工事完了公告や
        # 都市計画の告示しか載っていない号（821 号ある）が丸ごと抜けるため。
        # 生データは全部保存する（共通仕様 9）。姉妹サイトもこの全文を読む。
        with open(ISSUES, encoding="utf-8") as f:
            index_rows = json.load(f)
        issues = {(r["date"], r["no"]): r.get("topics", {}).get("大店立地法", 0) for r in index_rows}
        dev = sum(1 for r in index_rows if any(t != "大店立地法" for t in r.get("topics", {})))
        ledger = load_ledger()
        index = month_index()
        lines.append(f"- 目録に出てくる号 {len(issues):,} 号（うち開発系の告示がある号 {dev:,}）。"
                     f"月別一覧 {len(index)} か月")
        todo = [k for k in sorted(issues, reverse=True) if needs_fetch(f"{k[0]}#{k[1]}", ledger)]
        again = sum(1 for k in todo if f"{k[0]}#{k[1]}" in ledger)
        lines.append(f"- 未読の号 {len(todo)}（うち全文を残す前に取った取り直し {again} 号）。"
                     f"今回は新しいほうから {MAX_ISSUES} 号まで")
        today = date.today().isoformat()
        # 追いついたら月2回（共通仕様3.4）。過去分の積み直しの間だけ毎日。手で押したときは行く
        if todo and not fetch_today(len(todo), date.today(), bool(os.environ.get("KOHO_ANYDAY"))):
            lines.append(f"- 未読が {len(todo)} 号で追いついている。公報は月2回（{FETCH_DAYS[0]}日・{FETCH_DAYS[1]}日）だけ"
                         "取りに行く（共通仕様3.4）。今日は取りに行かない")
            todo = []
        ok, why = check_robots(HOST + "/")
        if ok is None:
            lines.append(f"- {why}。今回は取りに行かない（共通仕様3.4）")
            todo = []
        elif ok is False:
            lines.append(f"- {why}。取りに行かない（共通仕様3.4）")
            todo = []
        try:
            for (d, no) in todo[:MAX_ISSUES]:
                key = f"{d}#{no}"
                ym = d[:7]
                murl = index.get(ym)
                if not murl:
                    ledger[key] = {"status": "月ページが一覧に無い", "when": today}
                    save_ledger(ledger)
                    continue
                links = month_links(ym, murl, lines)
                if links is None:
                    continue
                if str(no).startswith("g") and links.get("_v") != MONTH_CACHE_V:
                    # 号外は新しい版の控えでないと引けない。台帳には書かず、次回以降に回す
                    continue
                y, m, dd = d.split("-")
                url = links.get(f"{int(m)}-{int(dd)}-{no}")
                issue_date = d
                if not url:
                    # 目録の年が1年ずれていないか、前後1年の同じ月日で探す
                    d2, url2 = find_in_neighbor_year(d, no, index, lines)
                    if url2:
                        url, issue_date = url2, d2
                        lines.append(f"  - {d} {no_label(no)}: 目録の年がずれていた。実際は {d2}")
                if not url:
                    ledger[key] = {"status": "月ページに号が無い", "when": today}
                    save_ledger(ledger)
                    lines.append(f"  - {d} {no_label(no)}: 月ページに見つからない")
                    continue
                try:
                    n = fetch_issue({"date": issue_date, "no": no}, url, lines)
                    ledger[key] = {"status": "done", "url": url, "sections": n,
                                   "v": TEXT_VERSION, "when": today}
                    if issue_date != d:
                        ledger[key]["date_actual"] = issue_date
                    fetched += 1
                    lines.append(f"  - **{issue_date} {no_label(no)}** 大店立地法の公告 {n} 件"
                                 f"（目録では {issues[(d, no)]} 件）")
                except urllib.error.HTTPError as e:
                    ledger[key] = {"status": f"failed: HTTP {e.code}", "url": url, "when": today}
                    lines.append(f"  - {d} {no_label(no)}: HTTP {e.code}")
                    if is_busy(e):
                        save_ledger(ledger)
                        lines.append(f"  - **HTTP {e.code}（混んでいる）。今回はここで中止**（共通仕様3.4）")
                        break
                except (urllib.error.URLError, OSError, ValueError, subprocess.TimeoutExpired) as e:
                    # ValueError は「大きすぎる」「文字なし」。中身を残して恒久扱いにする
                    why = str(e) if isinstance(e, ValueError) else type(e).__name__
                    ledger[key] = {"status": f"failed: {why}", "url": url, "when": today}
                    lines.append(f"  - {d} {no_label(no)}: {why[:50]}")
                save_ledger(ledger)               # 途中で落ちても、ここまでの分は残る
                time.sleep(WAIT)
        except urllib.error.HTTPError as e:
            # 月ページが 429/503。その回は中止
            lines.append(f"  - **月ページが HTTP {e.code}（混んでいる）。今回はここで中止**（共通仕様3.4）")
        save_ledger(ledger)
    else:
        lines.append("- 号の一覧がまだ無いか pdftotext が無いので、取りに行かなかった")

    # 全文が手元にある号は、抜粋を作り直してから読む（読み取りの直しが過去分に効く）
    rebuild_from_full(lines)

    # 手元の文字ファイルを全部読み直す
    recs, seen = [], set()
    for path in sorted(glob.glob(os.path.join(TEXTS, "*.txt"))):
        for r in parse_text_file(path):
            if r["key"] in seen:
                continue
            seen.add(r["key"])
            recs.append(r)
    recs.sort(key=lambda r: (r["notified_on"], r["store"]))
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "all.json"), "w", encoding="utf-8") as f:
        json.dump(recs, f, ensure_ascii=False, indent=1)
    kinds = {}
    for r in recs:
        kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
    lines.insert(1, f"**今回読んだ {fetched} 号 / 手元の文字から {len(recs)} 件**（" + " / ".join(f"{k} {n}" for k, n in sorted(kinds.items())) + "）")
    text = "\n".join(lines)
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write(text)
    print(text)
    gh = os.environ.get("GITHUB_STEP_SUMMARY")
    if gh:
        with open(gh, "a", encoding="utf-8") as f:
            f.write("\n" + text + "\n")


if __name__ == "__main__":
    main()
