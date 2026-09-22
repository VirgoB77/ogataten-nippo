#!/usr/bin/env python3
"""保健所の営業許可の一覧を、**目録から探して、バイトのまま保存する。**

ここは**探すだけ。** 読み取りは書かない（9節「見本は実物から取る」）。

**なぜ急ぐか。** 案出しが調べた（2026-09-19）——

> 兵庫県：Excel＋PDF。更新は**毎月20日頃**と明記。過去分は**上書き**
> （ファイル名固定）

**上書きなので、いま始めないと過去は取り返せない。**
「サイトにするのは保留、取得だけ開始」——同じ日に補助金でも同じ答えになった。

**URL を作文しない。** 兵庫県のオープンデータ目録は
`sources.json` に既に在る（`hyogo-opendata-catalog`）ので、
**そこをキーワードで引いて、向こうが書いたリンクを使う。**

そして**対象区域の但し書きを必ず読む**（2026-09-19 の正本）——

> 兵庫県の一覧から、**神戸市・姫路市・尼崎市・明石市・西宮市が除かれている。**
> 保健所も空き家活用支援事業も同じ構造。**「兵庫県のデータ」は兵庫県全部ではない。**

**捕まえないもの**：見つけたものが本当に営業許可の一覧か。
**実物を人が1回見てから**読み取りを書く。
"""
import argparse
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from common.fetch import Konde, UA, WAIT, check_robots, decode_html, is_busy  # noqa: E402
from common.runday import today  # noqa: E402
from tenant_recon import shitami  # noqa: E402  **形の測り方は1か所に置く**

# **既に収集先に在る目録。** ここを引く。新しい URL を作文しない
MOKUROKU = "https://web.pref.hyogo.lg.jp/opendata/index.php"

# 探す語。**「許可」だけだと建築確認も拾う**ので、営業のほうに寄せる
KOTOBA = ["営業許可", "食品衛生", "飲食店営業"]

# **種。目録に無かったので、人が入口を渡す。**
#
# 2026-09-20 に目録を3語で引いて、**3語とも0本**だった。
# 「0本」を「無い」と読まずに調べ直したら、**目録には登録されておらず、
# 食品衛生課のページに直に置かれていた**（2026-09-21）。
# **探し方が当たっていなかっただけ。**（9節「0件は、その道を1回も通っていないときにも出る」）
#
# **URLは検索で出たものをこちらが並べた。公的資料で確かめていない。**
# ドメインを思い出して作文したわけではないが、「確かめた」とは言えないので、
# 記録の側にそう書く（ルール⑥）。
#
# **5市は県の一覧から除かれているので、別々に持つ。**
# 読まずに「兵庫県全部」と名乗ると、人口の多いところがまるごと抜ける。
TANE = (
    {"id": "hyogo-pref", "mei": "兵庫県（神戸・姫路・尼崎・明石・西宮を除く）",
     "url": "https://web.pref.hyogo.lg.jp/kf14/shokuhineigyoushisetsu_list.html"},
    {"id": "kobe-city", "mei": "神戸市",
     "url": "https://www.city.kobe.lg.jp/a99427/kenko/health/hygiene/dataset.html"},
    {"id": "himeji-city", "mei": "姫路市",
     "url": "https://city.himeji.gkan.jp/gkan/dataset/shokuhinn"},
    {"id": "amagasaki-city", "mei": "尼崎市",
     "url": "https://www.city.amagasaki.hyogo.jp/op_data/1000922/1001025.html"},
    {"id": "akashi-city", "mei": "明石市",
     "url": "https://www.city.akashi.lg.jp/soumu/j_kanri_ka/opendata/hokensyo.html"},
    # **玄関ではなく一覧に差し替えた**（2026-09-21）。
    # `/opendata/` は検索フォームで、**拾えたのは利用規約のPDF 1本だけ**だった。
    # 検索で出た形は `ResultList.php`（詳細検索）と `ResultDetail.php?id=N`（1件ごと）。
    # **どの id が食品営業許可施設かは分かっていない。** 開いてから決める
    {"id": "nishinomiya-city", "mei": "西宮市",
     "url": "https://opendata.nishi.or.jp/opendata/ResultList.php"},
)
# **この段は、毎朝の巡回と同じ相手を含む。**
# `www.city.kobe.lg.jp` は大店立地法の巡回でも毎朝行っている。
# 押した日は、その相手にとって**2回目**になる。
#
# **探す段は1回きりなので、ここでは許容している。**
# ただし**毎日走らせる段（ためる段）にするときは、日をずらすか相手を避ける**
# ——`teiden_get.py` が1段目を押した日に自分で止まるのと同じ形にする。
# **これを書かずに毎日の段にすると、約束を破ったことに誰も気づかない。**

# **西宮市は見つかっていない。**「無い」ではなく「まだ見つけていない」。
# 数えるときに0件の側へ入れず、**探していない側**に入れる
MADA = ()

# 対象区域の但し書き。**この語を含む文を拾って記録に残す**（読まずに名乗らないため）
TADASHI = ("除く", "除き", "を除いた")

# **1段だけ辿るときに探す語。** 向こうがリンクの文字に書いているものだけを見る。
# **`id` を総当たりしない**（3.4）。当てずっぽうの番号は、外れた分だけ
# 関係のない誰かのサーバーに当たる
SAGASU = ("食品営業許可", "食品関係営業", "営業許可施設", "食品営業", "飲食店営業")
# 更新のしかたを書いていそうな語。**拾って出すだけ。決めるのは人**
KOUSHIN = ("更新", "毎月", "毎年", "随時", "公開日", "最終更新", "掲載", "頻度")

INBOX = os.path.join(HERE, "inbox", "hokenjo")
REPORT = os.path.join(HERE, "data", "ref", "hokenjo-recon.md")
# **前の回を消さない台帳。** 入口ごとに「最後の1回」を持つ。
#
# 2026-09-21、`--tane-id nishinomiya-city` だけを走らせたら、
# **記録が丸ごと書き直されて、前の回に拾った神戸市26本・明石市35本が消えた。**
# git の履歴には残っていたが、**ためる段が読むのは記録のほう**なので、
# 1入口を回すたびに、ためる段の行き先が消えることになる。
#
# 規約の段で同じ形を踏んで直した（`yakusoku_get.py`）。**同じ直し方をする。**
TANE_JSON = os.path.join(HERE, "data", "ref", "hokenjo-recon.json")
TIMEOUT = 40

LINK = re.compile(r'<a\s[^>]*href\s*=\s*["\']([^"\']+)["\'][^>]*>(.*?)</a>',
                  re.I | re.S)
# 一覧そのもののファイル。**拡張子を1つに決め打ちしない**（2026-09-19）
FILE = re.compile(r"\.(xlsx?|csv|pdf|zip)(\?|$)", re.I)


def moji(s):
    """リンクの文字。**空白は1つに潰す。** 記録の表を1行に収めるため。

    2026-09-19、遅延証明書で踏んだ。改行が残ると表の1行が10行になり、
    読む側が別の行を食べた。**書く側で直す。**
    """
    t = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    return re.sub(r"\s+", " ", t).strip()


def toi(kotoba):
    """目録をキーワードで引く URL。**目録が受ける形をそのまま使う。**

    `sources.json` の `hyogo-opendata-catalog-kw` が既にこの形で入っている
    （`?keyword=大規模小売&displayedresults=100`）。**同じ形を使う。**
    """
    return MOKUROKU + "?" + urllib.parse.urlencode(
        {"keyword": kotoba, "displayedresults": 100})


def get(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ja",
    })
    try:
        deta = urllib.request.urlopen(req, timeout=TIMEOUT)
    except urllib.error.HTTPError as e:
        if is_busy(e):
            raise Konde(f"相手が混んでいると言っている（HTTP {e.code}）") from e
        raise
    with deta as r:
        return r.status, r.headers.get("Content-Type", ""), r.read()


def hirou(base, raw, ctype, kotoba):
    """目録の返事から、**リンクの文字か行き先に探す語が入っているもの**を拾う。

    **ファイルだけに絞らない。** 一覧が「データセットのページ」の先にあることも
    あるので、両方拾って**どちらかを記録に残す**。決めるのは人。
    """
    honbun, _m = decode_html(raw, ctype)
    mita, de = set(), []
    for u, t in LINK.findall(honbun):
        t = moji(t)
        saki = urllib.parse.urljoin(base, u)
        # **問い合わせの語は、こちらが URL に入れたもの。** そこで当てない。
        #
        # 2026-09-20、初回に踏んだ。目録は探した語を query に持つので、
        # **ページ上のすべてのリンク**（並べ替え・本文へスキップ・page top）に
        # 語が入る。結果「当たった3」で、**中身は1つも一覧ではなかった。**
        # 「『返ってきた』は『見つかった』ではない」（9節）そのもの。
        p = urllib.parse.urlsplit(saki)
        michi_moji = urllib.parse.unquote(p.path)
        if kotoba not in t and kotoba not in michi_moji:
            continue
        if saki in mita:
            continue
        mita.add(saki)
        de.append((t, saki, bool(FILE.search(saki))))
    return de


def tadashigaki(raw, ctype):
    """対象区域の但し書きを拾う。**読まずに「兵庫県全部」と名乗らないため。**

    politique：**判断しない。** 「除く」を含む文をそのまま記録に出す。
    どこが除かれているかを決めるのは人（2026-09-19 に2つの題材で同じ形を踏んだ）。
    """
    honbun, _m = decode_html(raw, ctype)
    honbun = moji(re.sub(r"<[^>]+>", " ", honbun))
    de = []
    for bun in re.split(r"[。\n]", honbun):
        bun = bun.strip()
        if 6 < len(bun) < 160 and any(g in bun for g in TADASHI):
            de.append(bun)
    return de[:4]


def moguru(base, raw, ctype):
    """1段だけ辿る先を拾う。**向こうが書いたリンクの文字で選ぶ。**

    **`id` を総当たりしない。** ページに出ている導線だけを使う。
    **2本まで。** それ以上は総当たりに近づく。
    """
    honbun, _m = decode_html(raw, ctype)
    de, mita = [], set()
    for u, naka in LINK.findall(honbun):
        t = moji(naka)
        if not t or FILE.search(u) or not any(g in t for g in SAGASU):
            continue
        saki = urllib.parse.urljoin(base, html.unescape(u))
        if saki in mita or saki == base:
            continue
        mita.add(saki)
        de.append({"text": t[:48], "url": saki})
    return de[:2]


def koushin_no_kaki(raw, ctype):
    """更新のしかた・対象範囲が書いてありそうな文を拾う。**判断しない。**"""
    honbun, _m = decode_html(raw, ctype)
    hontai = moji(re.sub(r"<[^>]+>", " ", honbun))
    de = []
    for bun in re.split(r"[。\n]", hontai):
        bun = bun.strip()
        if 4 < len(bun) < 140 and any(g in bun for g in KOUSHIN):
            de.append(bun)
    return de[:6]


def tane_wo_hiraku(limit=0, fukasa=1, tane_id=""):
    """人が渡した入口を1つずつ開いて、**一覧のファイルへのリンクを拾う。**

    **目録と違って、ここは向こうが書いたページそのもの。**
    ファイル（xlsx/csv/pdf/zip）だけを拾う。**読み取らない。**
    """
    de = []
    tane = [t for t in TANE if not tane_id or t["id"] == tane_id]
    tane = tane[:limit] if limit else tane
    for i, t in enumerate(tane):
        if i:
            time.sleep(WAIT)
        d = {"id": t["id"], "mei": t["mei"], "url": t["url"],
             "mita_hi": today(), "file": [], "tadashi": [], "note": ""}
        ok, why = check_robots(t["url"])
        if ok is not True:
            d["note"] = f"robots が{'拒否' if ok is False else '分からない'}：{why}"
            print(f"× 「{t['mei']}」 {d['note']}")
            de.append(d)
            continue
        time.sleep(WAIT)
        try:
            status, ctype, raw = get(t["url"])
        except Konde as e:
            d["note"] = f"{e}。この相手は飛ばす"
            print(f"△ 「{t['mei']}」 {d['note']}")
            de.append(d)
            continue
        except Exception as e:                                   # noqa: BLE001
            d["note"] = f"開けなかった {type(e).__name__}: {e}"
            print(f"× 「{t['mei']}」 {d['note']}")
            de.append(d)
            continue
        with open(os.path.join(INBOX, f"tane-{t['id']}.html"), "wb") as f:
            f.write(raw)
        honbun, _m = decode_html(raw, ctype)
        mita = set()
        for u, moji_ in LINK.findall(honbun):
            saki = urllib.parse.urljoin(t["url"], u)
            if not FILE.search(saki) or saki in mita:
                continue
            mita.add(saki)
            d["file"].append({"text": moji(moji_)[:48], "url": saki})
        d["tadashi"] = tadashigaki(raw, ctype)
        d["koushin"] = koushin_no_kaki(raw, ctype)
        # **「0本」の理由が分からない記録は、0本と同じくらい役に立たない。**
        # 2026-09-21、ある入口が「ファイル0本・導線0本」で返ってきたが、
        # **検索フォームなのか・JSで描いているのか・語が合っていないのかが分からなかった。**
        # 次に見る人が同じところで止まらないよう、**形を測って一緒に残す**
        d["katachi"] = shitami(t["url"], raw, ctype)
        if fukasa >= 2:
            # **1段だけ辿る。** 向こうが書いた導線を、2本まで
            d["tadotta"] = []
            for saki in moguru(t["url"], raw, ctype):
                time.sleep(WAIT)
                ok2, why2 = check_robots(saki["url"])
                if ok2 is not True:
                    saki["note"] = f"robots が通らなかった：{why2}"
                    d["tadotta"].append(saki)
                    continue
                time.sleep(WAIT)
                try:
                    _s2, ctype2, raw2 = get(saki["url"])
                except Konde as e:
                    saki["note"] = f"{e}。この先は見ない"
                    d["tadotta"].append(saki)
                    continue
                except Exception as e:                           # noqa: BLE001
                    saki["note"] = f"開けなかった {type(e).__name__}: {e}"
                    d["tadotta"].append(saki)
                    continue
                honbun2, _m2 = decode_html(raw2, ctype2)
                mita2, fa = set(), []
                for u2, naka2 in LINK.findall(honbun2):
                    s2 = urllib.parse.urljoin(saki["url"], html.unescape(u2))
                    if not FILE.search(s2) or s2 in mita2:
                        continue
                    mita2.add(s2)
                    fa.append({"text": moji(naka2)[:48], "url": s2})
                saki["file"] = fa
                saki["tadashi"] = tadashigaki(raw2, ctype2)
                saki["koushin"] = koushin_no_kaki(raw2, ctype2)
                saki["note"] = "" if fa else "ファイルへのリンクが0本。**無いとは限らない**"
                yasui2 = re.sub(r"[^0-9A-Za-z]+", "-", t["id"] + "-" +
                                urllib.parse.urlsplit(saki["url"]).path)[:60]
                with open(os.path.join(INBOX, f"tadotta-{yasui2}.html"), "wb") as f:
                    f.write(raw2)
                d["tadotta"].append(saki)
        # **0本は「無い」ではない。** JS で出している／別ページに置いていることがある
        d["note"] = "" if d["file"] else "ファイルへのリンクが0本。**無いとは限らない**"
        print(f"{'○' if d['file'] else '△'} 「{t['mei']}」  {status} "
              f"{len(raw):,}バイト  ファイル {len(d['file'])}本"
              f"  但し書き {len(d['tadashi'])}件")
        de.append(d)
    return de


def daicho_awaseru(kono_kai, michi=None):
    """**前の回を消さない。** 入口ごとに最後の1回を持って、記録を組み直す。

    **この回で見ていない入口も残す**——「見ていない」と「0本だった」は別（9節）。

    2026-09-21、1入口だけ走らせたら**記録が丸ごと書き直されて、
    前の回に拾った行き先が消えた。** ためる段が読むのはそこなので、
    回すたびに行き先が消えることになっていた。**規約の段と同じ直し方をする。**
    """
    michi = michi or TANE_JSON
    dai = {}
    if os.path.exists(michi):
        try:
            with open(michi, encoding="utf-8") as f:
                dai = {d["id"]: d for d in json.load(f).get("tane", [])
                       if isinstance(d, dict) and d.get("id")}
        except (ValueError, KeyError, TypeError, OSError):
            dai = {}                # 壊れていたら作り直す。**黙って0件にしない**
    for d in kono_kai:
        dai[d["id"]] = d
    juban = {t_["id"]: i for i, t_ in enumerate(TANE)}
    return sorted(dai.values(), key=lambda d: juban.get(d["id"], 999))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--limit", type=int, default=len(KOTOBA),
                    help="引くキーワードの数。既定は全部")
    ap.add_argument("--tane-limit", type=int, default=0,
                    help="人が渡した入口を上から何件開くか（0=全部）")
    ap.add_argument("--fukasa", type=int, default=1,
                    help="2 にすると、向こうが書いた導線を**1段だけ**辿る（2本まで）")
    ap.add_argument("--tane-id", default="",
                    help="この入口だけ（例 nishinomiya-city）")
    ap.add_argument("--dake", choices=("mokuroku", "tane"),
                    help="片方だけ走らせる（既定は両方）")
    args = ap.parse_args()

    ok, why = check_robots(MOKUROKU)
    if ok is False:
        print("robots.txt が拒否している。取りに行かない")
        return 1
    if ok is None:
        print(f"robots.txt が返らない（{why}）。この回は中止")
        return 1

    os.makedirs(INBOX, exist_ok=True)
    kekka, karappo, dame, derarenai = [], [], [], []
    for i, kotoba in enumerate([] if args.dake == "tane" else KOTOBA[:args.limit]):
        if i:
            time.sleep(WAIT)
        url = toi(kotoba)
        try:
            status, ctype, raw = get(url)
        except Konde:
            print(f"△ 「{kotoba}」 相手が混んでいる。この語は飛ばす")
            dame.append((kotoba, "混んでいる"))
            continue
        except urllib.error.HTTPError as e:
            print(f"× 「{kotoba}」 相手が HTTP {e.code} と答えた")
            dame.append((kotoba, f"HTTP {e.code}"))
            continue
        except Exception as e:                                   # noqa: BLE001
            print(f"× 「{kotoba}」 出られなかった（{type(e).__name__}: {e}）")
            derarenai.append(kotoba)
            continue

        yasui = re.sub(r"[^0-9A-Za-z]+", "-", urllib.parse.quote(kotoba))[:40]
        with open(os.path.join(INBOX, f"mokuroku-{yasui}.html"), "wb") as f:
            f.write(raw)
        de = hirou(url, raw, ctype, kotoba)
        if de:
            kekka.append((kotoba, de))
            print(f"○ 「{kotoba}」  {status} {len(raw):,}バイト  当たり {len(de)}本")
            for t, u, f_ in de[:3]:
                print(f"    {'[ファイル]' if f_ else '[ページ]'} {t[:28]} → {u}")
        else:
            karappo.append(kotoba)
            print(f"△ 「{kotoba}」  {status} {len(raw):,}バイト  **0本**")

    kono_kai = ([] if args.dake == "mokuroku"
                else tane_wo_hiraku(args.tane_limit, args.fukasa, args.tane_id))

    tane = daicho_awaseru(kono_kai)
    kono_kai_id = {d["id"] for d in kono_kai}

    mita_n = len(kekka) + len(karappo) + len(dame) + len(derarenai)
    minna_dame = mita_n > 0 and len(derarenai) == mita_n

    lines = ["# 保健所の営業許可を探した記録", ""]
    if minna_dame:
        lines += ["> ⚠️ **この回は1回も接続できていない。**",
                  "> **相手の話ではなく、走らせた場所の話**の可能性が高い。", ""]
    lines += [
        "**このファイルは `hokenjo_recon.py` が書く。** 手で直さない。", "",
        "ここは**探しただけ**で、まだ1件も読み取っていない。",
        "**URL は作文していない。** 既に収集先に在る兵庫県のオープンデータ目録を、",
        "キーワードで引いて、向こうが書いたリンクを拾った。", "",
        "**なぜ急ぐか**：兵庫県は**毎月20日頃に上書き**（ファイル名固定）。",
        "いま始めないと、過去は取り返せない。", "",
        "| | 語の数 |", "|---|---:|",
        f"| **当たった** | {len(kekka):,} |",
        f"| 0本だった | {len(karappo):,} |",
        f"| 相手が「だめ」と答えた | {len(dame):,} |",
        f"| **こちらが出られなかった** | {len(derarenai):,} |",
        f"| 引いた語 | {len(KOTOBA):,} |", "",
    ]
    if kekka:
        lines += ["## 当たったもの", "",
                  "| 語 | 種類 | リンクの文字 | 行き先 |", "|---|---|---|---|"]
        for kotoba, de in kekka:
            for t, u, f_ in de:
                lines.append(f"| {kotoba} | {'ファイル' if f_ else 'ページ'} "
                             f"| {t} | {u} |")
        lines.append("")
    lines += ["## 西宮市について（2026-09-21・**まだ開いていない**）", "",
              "**確認済み2施設がどちらも西宮市なので、ここは後で要る。**", "",
              "玄関（`/opendata/`）を開いたら、**拾えたのは利用規約のPDF 1本だけ**だった。",
              "検索で出た形は次のとおり（**検索エンジンの結果。こちらは開いていない**）——", "",
              "    ResultList.php          詳細検索（一覧）",
              "    ResultDetail.php?id=N   データ詳細（1件ごと）",
              "    results.php             検索結果", "",
              "**どの id が食品営業許可施設かは分かっていない。**",
              "検索結果では**更新日が 2026-05-15** と出たが、**こちらは確かめていない。**", "",
              "**「過去版を見つけられなかった」と「過去版が無い」は別。** いまは前者。", "",
              "## 人が渡した入口（種）", "",
              "**目録には無かった。** 2026-09-20 に3語で引いて3語とも0本だったが、",
              "調べ直したら**食品衛生課のページに直に置かれていた**（2026-09-21）。",
              "**「0本」は「無い」ではなく、探し方が当たっていなかった。**", "",
              "**URLは検索で出たものをこちらが並べた。公的資料で確かめていない。**", ""]
    if tane:
        lines += ["**表は入口ごとの「最後の1回」。** この回で見ていない入口も残る。",
                  "**「見ていない」と「0本だった」を、記録の上でも分けるため。**", "",
                  "| 入口 | 見た日 | この回 | ファイル | 但し書き | 覚書 |",
                  "|---|---|---|---:|---:|---|"]
        for d in tane:
            kono = "**見た**" if d["id"] in kono_kai_id else "—"
            lines.append(f"| [{d['mei']}]({d['url']}) | {d.get('mita_hi') or '—'} "
                         f"| {kono} | {len(d['file'])} "
                         f"| {len(d['tadashi'])} | {d['note']} |")
        lines.append("")
        for d in tane:
            if not (d["file"] or d["tadashi"] or d.get("katachi")
                    or d.get("tadotta")):
                continue
            lines += [f"### {d['mei']}", ""]
            for f_ in d["file"]:
                lines.append(f"- [{f_['text']}]({f_['url']})")
            if d["file"]:
                lines.append("")
            for t_ in d["tadashi"]:
                lines.append(f"> {t_}")
            if d["tadashi"]:
                lines.append("")
            ka = d.get("katachi") or {}
            if ka:
                ko = ka.get("kotei_url") or {}
                lines += ["", "**このページの形**（0本だったときに、理由を見るため）", "",
                          f"- JS を落とす前 {ka['zenbu_moji']:,} 文字 → "
                          f"落とした後 **{ka['mieru_moji']:,} 文字**",
                          f"- 同じ形のリンク {ko.get('kazu', 0)} 本"
                          f"（形：`{ko.get('katachi', '—')}`）",
                          f"- リンクの形の種類 {ka.get('link_katachi', 0)}", ""]
            for k_ in d.get("koushin") or []:
                lines.append(f"- 更新のしかた？：{k_}")
            if d.get("koushin"):
                lines.append("")
            for sa in d.get("tadotta") or []:
                lines += [f"**1段だけ辿った** → [{sa['text']}]({sa['url']})", "",
                          "（**向こうがページに書いた導線。`id` の総当たりはしていない**）", ""]
                for f_ in sa.get("file") or []:
                    lines.append(f"  - [{f_['text']}]({f_['url']})")
                if sa.get("file"):
                    lines.append("")
                for t2 in sa.get("tadashi") or []:
                    lines.append(f"  > {t2}")
                if sa.get("tadashi"):
                    lines.append("")
                for k2 in sa.get("koushin") or []:
                    lines.append(f"  - 更新のしかた？：{k2}")
                if sa.get("koushin"):
                    lines.append("")
                if sa.get("note"):
                    lines += [f"  {sa['note']}", ""]
    else:
        lines += ["この回は種を開いていない。", ""]
    lines += ([f"**まだ見つけていない入口**：{'、'.join(MADA)}",
               "（**「無い」ではない。探していないだけ**）", ""] if MADA else
              ["**入口は6つとも見つけた**（県＋5市）。",
               "**ただし「見つけた」は「開いた」ではない。** 開くのはこの段が走ったとき", ""]) + [
              "## ⚠️ 対象区域の但し書きを必ず読む", "",
        "案出しが2つの題材で同じ形を踏んだ（2026-09-19）。", "",
        "    兵庫県の保健所の営業許可     **神戸市・姫路市・尼崎市・明石市・西宮市を除く**",
        "    兵庫県の空き家活用支援事業   同じ構造", "",
        "**政令市・中核市は自分で持っている。**",
        "読まずに「兵庫県全部」と名乗ると、人口の多いところがまるごと抜ける。", "",
        "## 氏名が入っている", "",
        "**営業者氏名の欄がある**（案出しの調査）。個人事業主が多いはず。",
        "金庫に入れる分は問題ないが、**公開するときは 3.1 と 5節を通す。**",
        "**法人だと分かったときだけ出す**（向きを逆にしない）。", "",
        "## 次に見ること", "",
        "`inbox/hokenjo/*.html` を**人が1つ開く。**",
        "**一覧の形式・更新の頻度・対象区域の但し書き**を実物で見てから、",
        "毎月の取得を書く。", ""]

    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    # **台帳は記録と一緒に書く。** ためる段はこちらを読む（人が読む記録ではなく）
    with open(TANE_JSON, "w", encoding="utf-8") as f:
        json.dump({"hi": today(), "tane": tane}, f, ensure_ascii=False, indent=1)
    print("\n".join(lines[8:16]))
    print(f"→ {REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
