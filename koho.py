"""兵庫県公報の検索用目録（Excel）から、大規模小売店舗立地法の公告を数える。

兵庫県は 2007 年 1 月からの公報の目録を年ごとの Excel で出している。
「公告」シートに 1 行 1 公告で、件名・担当課・発行日・公報番号が載る。
件名に店舗名は無いが、「大規模小売店舗の新設に関する届出」「…変更に関する届出」
「…廃止に関する届出」「市町の意見の概要」の別と、公告日（＝縦覧開始日）、
担当（県庁の都市計画課か、どの県民局か）は分かる。

ここから作るもの：
- data/koho/hyogo-notices.json … 大店立地法の公告 1 件 1 行（日付・種類・担当・公報番号・件名）
- data/koho/hyogo-monthly.json … 年月 × 種類 の件数
- data/koho/hyogo-issues.json  … 目録に出てくる号を全部（日付・号・件名の数・制度の内訳）

3 本目は大店立地法に限らない。目録には「告示」シートもあり、そちらに
工事完了公告・都市計画の決定・土壌汚染の区域指定などが載っている。
19 年ぶんを数えると、大店立地法 2,032 件に対し開発系はその 2.4 倍ある。
姉妹サイト（開発系）がそれを使うので、本体 PDF は全号を取りに行く。
どの号にどの制度が何件あるかは、この 3 本目を見れば PDF を開かずに分かる。

店舗名まで要るときは、公報番号から公報本体の PDF をたどる（それは次の段）。
"""
import glob
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import xlsx  # noqa: E402

SRC = os.path.join(HERE, "data", "files", "hyogo-koho-mokuroku")
OUT = os.path.join(HERE, "data", "koho")
# 目録は 2007 年から。あり得ない年の行は読み違いなので数えない。
# ただし「今日より後」は捨てない。オートフィルの事故で年がずれているだけのことが多く、
# 公報番号でまとめれば正しい発行日に戻せる（main を見ること）。
FIRST_DAY = "2007-01-01"
LAST_DAY = "2100-12-31"

KIND = [
    (r"新設に関する届出", "新設"),
    (r"変更に関する届出", "変更"),
    (r"廃止に関する届出", "廃止"),
    (r"取下げ", "取下げ"),
    (r"市町等?の意見", "市町の意見"),
    (r"県の意見に対して講ずる措置", "措置"),
    (r"県の意見", "県の意見"),
    (r"住民等?の意見", "住民の意見"),
]


# 目録の件名から制度を見分ける。上から順に、最初に当たった 1 つだけを数える。
# 「都市計画法第36条第3項に基づく工事完了公告」は都市計画にも当たるので、順番が効く。
TOPIC = [
    ("大店立地法",             r"大規模小売"),
    ("工事完了公告",           r"工事完了公告"),
    ("都市計画",               r"都市計画"),
    ("瀬戸内法",               r"瀬戸内海環境保全特別措置法"),
    ("土地区画整理・再開発",     r"土地区画整理|市街地再開発"),
    ("土壌汚染",               r"土壌汚染対策法"),
    ("公有財産の売払い",         r"県有(地|財産).{0,14}(売払|売却)"),
    ("環境影響評価",           r"環境影響評価"),
    ("盛土規制法・宅造",        r"宅地造成|特定盛土"),
]


def topic_of(title):
    """件名がどの制度のものか。どれでもなければ空文字。"""
    t = re.sub(r"\s", "", title)
    for name, pat in TOPIC:
        if re.search(pat, t):
            return name
    return ""


def kind_of(title):
    t = re.sub(r"\s", "", title)
    for pat, name in KIND:
        if re.search(pat, t):
            return name
    return "その他"


def to_iso(v):
    """'2007-01-09' / '46007'（Excel の通し番号）/ '2007/1/9' → 'YYYY-MM-DD'"""
    s = str(v or "").strip()
    if not s:
        return ""
    m = re.match(r"^(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})", s)
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    if re.match(r"^\d{4,6}(\.0+)?$", s):
        n = int(float(s))
        if 30000 < n < 60000:                       # 1982〜2064 年
            return (date(1899, 12, 30) + timedelta(days=n)).isoformat()
    return ""


_Z2H = str.maketrans("０１２３４５６７８９", "0123456789")


def norm_issue_no(s):
    """公報番号を揃える。'423' → '423'、'号外' → 'g1'、'第2号外' → 'g2'、'-'（欠番）や空 → ''。

    号外は日ごとに1から振り直される（本体 PDF の名前も 20251219g2.pdf）ので、定期号の
    通し番号とは別の並びにする。姉妹サイトが読むファイル名も <日付>-g<n> になる（共通仕様3.4）。
    """
    s = re.sub(r"\s", "", str(s or "")).translate(_Z2H)
    if s.isdigit():
        return s
    m = re.fullmatch(r"(?:第(\d+))?号外", s)
    if m:
        return f"g{m.group(1) or 1}"
    return ""


def merge_issue_dates(issues):
    """発行日がずれた号をまとめる。

    公報番号は通し番号なので、1 号に発行日は 1 つしかない。目録の一部（23-1-12h.xls の
    告示シートなど）は、Excel のオートフィルの事故で発行日の「年」が 1 行ずつ増えている。
    号番号のほうは正しいので、そちらでまとめ、いちばん多く出てくる日付（同数なら古いほう）を
    本当の発行日として採る。号外（no が g で始まる）は日ごとに番号が振り直されるので、まとめない。
    """
    by_no = defaultdict(list)
    fixed, merged = {}, []
    for it in issues.values():
        if str(it["no"]).startswith("g"):
            fixed[f"{it['date']}#{it['no']}"] = {"date": it["date"], "no": it["no"],
                                                 "titles": it["titles"], "topics": dict(it["topics"])}
        else:
            by_no[it["no"]].append(it)
    for no, group in by_no.items():
        if len(group) > 1:
            best = Counter()
            for it in group:
                best[it["date"]] += it["titles"]
            mx = max(best.values())
            true_date = min(d for d, n in best.items() if n == mx)   # 同数なら古いほう
            merged.append((no, sorted(best), true_date, len(group) - 1))
        else:
            true_date = group[0]["date"]
        topics = Counter()
        titles = 0
        for it in group:
            titles += it["titles"]
            for t, n in it["topics"].items():
                topics[t] += n
        fixed[f"{true_date}#{no}"] = {"date": true_date, "no": no,
                                      "titles": titles, "topics": dict(topics)}
    return fixed, merged


# 件名まで読むシート。ほかのシート（条例・規則・訓令・達・辞令など）は「号の一覧」にだけ使う。
# 辞令や人事の件名には個人の氏名が入るので、件名は読まない（共通仕様3.1）
TITLE_SHEETS = ("告示", "公告")


def sheet_rows(path):
    """1 冊の目録から (発行日, 号, 件名) を全部返す。

    号の一覧は**全シート**から作る。号外は告示も公告も無い号（条例だけ、辞令だけ）が
    多く、シートを絞ると本体PDFを取りに行く先から丸ごと落ちる。共通仕様9節
    「取得の段階で絞らない。絞り込みは出力の段階だけ」。
    件名は告示・公告シートからだけ読む（3.1。ほかのシートの件名には氏名が入る）。
    """
    out, dropped = [], []
    for name, rows in xlsx.read_any(path).items():
        want_title = name in TITLE_SHEETS
        hdr = next((i for i, r in enumerate(rows[:8])
                    if any("件" in str(c) and "名" in str(c) for c in r)), None)
        if hdr is None:
            continue
        head = [re.sub(r"\s", "", str(c or "")) for c in rows[hdr]]
        ci = {h: i for i, h in enumerate(head) if h}
        ti = ci.get("件名")
        di = next((ci[k] for k in ("発行日", "発行年月日") if k in ci), None)
        ni = next((ci[k] for k in ("公報番号", "公報号数", "号数") if k in ci), None)
        if di is None or ni is None or (want_title and ti is None):
            continue
        for r in rows[hdr + 1:]:
            cells = list(r)
            if max(di, ni) >= len(cells):
                continue
            title = ""
            if want_title and ti < len(cells):
                title = re.sub(r"\s+", " ", str(cells[ti] or "")).strip()
            d = to_iso(str(cells[di] or ""))
            no = norm_issue_no(cells[ni])          # 号外は g1, g2 …（落とさない）
            if not d or not no or (want_title and not title):
                continue
            if not (FIRST_DAY <= d <= LAST_DAY):    # 発行日として成り立たない行は数えない
                if want_title:
                    dropped.append((d, no, title))  # 黙って捨てず、呼び出し側に返す
                continue
            out.append((d, no, title))
    return out, dropped


def rows_of(path):
    """1 冊の目録から、大店立地法の公告の行だけ返す。"""
    sheets = xlsx.read_any(path)
    out = []
    for name, rows in sheets.items():
        if "公告" not in name or "企業庁" in name:
            continue
        hdr = next((i for i, r in enumerate(rows[:8])
                    if any("件" in str(c) and "名" in str(c) for c in r)), None)
        if hdr is None:
            continue
        head = [re.sub(r"\s", "", str(c or "")) for c in rows[hdr]]
        ci = {h: i for i, h in enumerate(head) if h}

        def col(cells, *keys):
            for k in keys:
                i = ci.get(k)
                if i is not None and i < len(cells):
                    return str(cells[i] or "").strip()
            return ""

        for r in rows[hdr + 1:]:
            cells = list(r)
            title = col(cells, "件名")
            if "大規模小売" not in title:
                continue
            out.append({
                "date": to_iso(col(cells, "発行日", "発行年月日")),
                "kind": kind_of(title),
                "dept": col(cells, "担当課等", "担当課"),
                "no": norm_issue_no(col(cells, "公報番号", "公報号数", "号数")),
                "title": re.sub(r"\s+", " ", title),
                "sheet": name,
                "file": os.path.basename(path),
            })
    return out


def main():
    files = sorted(glob.glob(os.path.join(SRC, "*.xls")) + glob.glob(os.path.join(SRC, "*.xlsx")))
    notices = []
    lines = ["# 兵庫県公報の目録から数えた大店立地法の公告", ""]
    for p in files:
        try:
            got = rows_of(p)
        except Exception as e:                      # 1 冊読めなくても他は進める
            lines.append(f"- {os.path.basename(p)}: 読めなかった — {type(e).__name__}: {str(e)[:60]}")
            continue
        notices.extend(got)
        years = Counter(g["date"][:4] for g in got if g["date"])
        lines.append(f"- {os.path.basename(p)}: {len(got)} 件（{', '.join(f'{y}年 {n}' for y, n in sorted(years.items()))}）")

    # 大店立地法に限らず、目録に出てくる号を全部ひろう（本体 PDF を全号取るため）
    issues, odd = {}, []
    for p_ in files:
        try:
            got, dropped = sheet_rows(p_)
        except Exception as e:
            lines.append(f"- {os.path.basename(p_)}: 号の一覧が作れなかった — {type(e).__name__}: {str(e)[:60]}")
            continue
        for d, no, title in dropped:
            odd.append(f"{os.path.basename(p_)}: {d} 第{no}号 「{title[:40]}」")
        for d, no, title in got:
            it = issues.setdefault(f"{d}#{no}", {"date": d, "no": no, "titles": 0, "topics": {}})
            it["titles"] += 1
            t = topic_of(title) if title else None
            if t:
                it["topics"][t] = it["topics"].get(t, 0) + 1

    fixed, merged = merge_issue_dates(issues)
    if merged:
        lines.append("")
        lines.append(f"発行日がずれていた号 {len(merged)} 件をまとめた（偽の号 {sum(m[3] for m in merged)} を消した）：")
        for no, ds, true_date, extra in sorted(merged, key=lambda m: -m[3])[:10]:
            lines.append(f"- 第{no}号: {len(ds)}通りの日付（{ds[0]}〜{ds[-1]}）→ {true_date}")
    issues = fixed

    notices.sort(key=lambda g: (g["date"], g["no"], g["kind"]))
    monthly = defaultdict(Counter)
    for g in notices:
        if g["date"]:
            monthly[g["date"][:7]][g["kind"]] += 1
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "hyogo-notices.json"), "w", encoding="utf-8") as f:
        json.dump(notices, f, ensure_ascii=False, indent=0)
    with open(os.path.join(OUT, "hyogo-monthly.json"), "w", encoding="utf-8") as f:
        json.dump({ym: dict(c) for ym, c in sorted(monthly.items())}, f, ensure_ascii=False, indent=0)
    with open(os.path.join(OUT, "hyogo-issues.json"), "w", encoding="utf-8") as f:
        json.dump([issues[k] for k in sorted(issues)], f, ensure_ascii=False, indent=0)

    topics = Counter()
    for it in issues.values():
        for t, n in it["topics"].items():
            topics[t] += n
    dev = sum(n for t, n in topics.items() if t != "大店立地法")
    lines.append("")
    extra = sum(1 for it in issues.values() if str(it["no"]).startswith("g"))
    lines.append(f"## 目録に出てくる号 {len(issues):,} 号（うち号外 {extra:,}。本体 PDF はこれを全部取りに行く）")
    lines.append("")
    lines.append("| 制度 | 件名 | その制度がある号 |")
    lines.append("|---|---:|---:|")
    for t, n in topics.most_common():
        has = sum(1 for it in issues.values() if t in it["topics"])
        lines.append(f"| {t} | {n:,} | {has:,} |")
    lines.append(f"| **開発系の合計（大店立地法を除く）** | **{dev:,}** | |")
    if odd:
        lines.append("")
        lines.append(f"発行日として成り立たない行 {len(odd)} 件は号の一覧に入れていない：")
        for x in odd[:10]:
            lines.append(f"- {x}")
        if len(odd) > 10:
            lines.append(f"- ほか {len(odd) - 10} 件")

    kinds = Counter(g["kind"] for g in notices)
    undated = sum(1 for g in notices if not g["date"])
    lines.insert(1, f"**{len(notices)} 件**（" + " / ".join(f"{k} {n}" for k, n in kinds.most_common()) + f"）。日付の読めないもの {undated} 件")
    text = "\n".join(lines)
    with open(os.path.join(OUT, "report.md"), "w", encoding="utf-8") as f:
        f.write(text)
    print(text)
    gh = os.environ.get("GITHUB_STEP_SUMMARY")
    if gh:
        with open(gh, "a", encoding="utf-8") as f:
            f.write("\n" + text + "\n")


if __name__ == "__main__":
    main()
