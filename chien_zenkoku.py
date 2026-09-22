#!/usr/bin/env python3
"""遅延証明書を**全国に広げる**ための、**会社の一覧を作文しないで作る**段。

ここは**探すだけ。** 読み取りも、遅延証明書の在りかも、まだ見ない。

## なぜこの段が要るか

いまの `chien_recon.py` は、大阪・兵庫の10社を**手で並べて**いる。
10社なら目で確かめられるが、**全国で同じことをすると作文になる。**
記憶から書いたドメインは、当たっているかどうかを誰も確かめられない。
当たっていなければ**関係のない誰かのサーバーを叩く。**

    ❌ 全国200社のドメインを思い出して並べる
    ✅ 役所が出している一覧を引いて、**向こうが書いたリンク**を使う

「URL を作文しない」（3.4）の、**一覧版**。

## どこから取るか

国土交通省の「鉄道関連リンク集」。**2026-09-20 に検索で見つけた。**
このページの「鉄軌道事業者」の項から**別紙**に飛ぶ形になっている。

**種は1つだけ置く。その先は辿る。**
種が 404 になったら、**黙って0本にせず、そう書いて止まる**（9節）。

## 拾い方

**二段に分ける。混ぜると関係ないところまで叩く。**

    種のページ    → 「事業者」「別紙」と書いてある **省内のリンク**だけ辿る
    別紙のページ  → **外のホスト**へのリンクを、事業者の候補として拾う

種のページから直に外のリンクを拾うと、他省庁や広報のリンクまで
候補に入る。そこを `chien_recon.py` に渡すと、**遅延証明書と関係のない
相手を叩く。** 別紙は事業者を並べるためのページなので、そこだけ見る。

**市営地下鉄は `.lg.jp`。** 役所のドメインだからといって落とせない
（神戸市営地下鉄で踏んだ。2026-09-20）。落とすのは**種と同じ省の中**だけ。

**捕まえないもの**：拾ったものが本当に鉄道事業者か。
判断は次の段（`chien_recon.py`）と、人が実物を1回見るまで保留する。
"""
import argparse
import html
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

# **種は1つ。** 2026-09-20 に検索で見つけた、国土交通省の鉄道関連リンク集。
# ここに事業者のドメインを並べない（それをしないためにこの段がある）
TANE = "https://www.mlit.go.jp/tetudo/tetudo_fr1_000042.html"

# 種のページから辿るリンクの文字。**別紙に事業者が並んでいる**
TADORU = re.compile(r"事業者|別紙")

INBOX = os.path.join(HERE, "inbox", "chien-zenkoku")
REPORT = os.path.join(HERE, "data", "ref", "chien-zenkoku.md")
TIMEOUT = 40

LINK = re.compile(r'<a\s[^>]*href\s*=\s*["\']([^"\']+)["\'][^>]*>(.*?)</a>',
                  re.I | re.S)

# 事業者ではないと分かっているもの。**役所のドメインでは落とさない**
# （市営地下鉄が `.lg.jp` にいる）。落とすのは交流サイトと配信だけ
YOSO = re.compile(
    r"(^|\.)(twitter|x|facebook|instagram|youtube|line|t)\.(com|me|jp)$"
    r"|(^|\.)(google|apple|adobe)\.(com|co\.jp)$")


def moji(s):
    """リンクの文字。**空白は1つに潰す**（記録の表を1行に収めるため）。

    2026-09-19、遅延証明書の1段目で踏んだ。改行が残ると表の1行が10行になり、
    読む側が別の行を食べた。**読む側を器用にせず、書く側を直す。**
    """
    t = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    return re.sub(r"\s+", " ", t).strip()


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


def onaji_yakusho(url, tane=TANE):
    """種と同じ役所の中か。**組織のところで見る。**

    2026-09-20、ここを「ホストまるごと」で見ていて踏んだ。
    事業者の一覧は**地方運輸局**にある（`wwwtb.mlit.go.jp`）のに、
    種が `www.mlit.go.jp` なので**別の役所と判定して、辿らなかった。**
    いちばん欲しいページを、いちばん最初に落としていた。

    `go.jp` は「組織.go.jp」の形なので、**後ろ3つ**で見る。
    """
    def shiri(u):
        h = urllib.parse.urlsplit(u).netloc.lower().split(":")[0]
        kire = h.split(".")
        if h.endswith(".go.jp") and len(kire) >= 3:
            return ".".join(kire[-3:])          # wwwtb.mlit.go.jp → mlit.go.jp
        return h
    return shiri(url) == shiri(tane)


def betsushi(base, raw, ctype):
    """種のページから、**別紙（事業者が並ぶページ）**へのリンクを拾う。

    **省の外には出ない。** ここで外に出ると、辿る先が事業者ではなく
    他省庁のページになる。
    """
    honbun, _m = decode_html(raw, ctype)
    mita, de = set(), []
    for u, t in LINK.findall(honbun):
        t = moji(t)
        saki = urllib.parse.urljoin(base, u)
        if not saki.startswith(("http://", "https://")):
            continue
        if not onaji_yakusho(saki):
            continue
        if not (TADORU.search(t) or TADORU.search(urllib.parse.unquote(saki))):
            continue
        if saki in mita:
            continue
        mita.add(saki)
        de.append((t, saki))
    return de


def jigyousha(base, raw, ctype):
    """別紙のページから、**外のホスト**へのリンクを事業者の候補として拾う。

    **同じホストは1回だけ。** 会社によってはトップと路線図で2本張ってある。
    行き先は**そのホストのトップ**に丸める——次の段はトップから辿るので、
    深いページを渡すと辿り方が変わってしまう。
    """
    honbun, _m = decode_html(raw, ctype)
    mita, de = {}, []
    for u, t in LINK.findall(honbun):
        t = moji(t)
        saki = urllib.parse.urljoin(base, u)
        p = urllib.parse.urlsplit(saki)
        if p.scheme not in ("http", "https") or not p.netloc:
            continue
        if onaji_yakusho(saki) or YOSO.search(p.netloc.lower()):
            continue
        host = p.netloc.lower()
        if host in mita:
            # 文字のあるほうを残す（画像リンクだと空になる）
            if not mita[host][0] and t:
                mita[host] = (t, mita[host][1])
            continue
        mita[host] = (t, f"{p.scheme}://{p.netloc}/")
    for host, (t, top) in mita.items():
        de.append((t, host, top))
    return sorted(de, key=lambda x: x[1])


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--limit", type=int, default=3,
                    help="辿る別紙の数。既定は3。まとめて叩かない")
    args = ap.parse_args()

    ok, why = check_robots(TANE)
    if ok is False:
        print("robots.txt が拒否している。取りに行かない")
        return 1
    if ok is None:
        print(f"robots.txt が返らない（{why}）。この回は中止")
        return 1

    os.makedirs(INBOX, exist_ok=True)

    def shimau(url, raw):
        na = re.sub(r"[^0-9A-Za-z]+", "-",
                    urllib.parse.urlsplit(url).path or "top")[:60]
        with open(os.path.join(INBOX, f"{na or 'top'}.html"), "wb") as f:
            f.write(raw)

    # ---- 種 ----
    try:
        status, ctype, raw = get(TANE)
    except Konde:
        print("相手が混んでいる。この回は中止（押し込まない）")
        return 1
    except urllib.error.HTTPError as e:
        # **黙って0本にしない。** 種が動いたのなら、そう分かる形で止まる
        print(f"種のページが HTTP {e.code}。**在りかが変わった疑い。**"
              " 一覧を作らずに止まる")
        return 1
    except Exception as e:                                       # noqa: BLE001
        print(f"出られなかった（{type(e).__name__}: {e}）。"
              "**相手ではなくこちらの話かもしれない**")
        return 1

    shimau(TANE, raw)
    betsu = betsushi(TANE, raw, ctype)
    print(f"○ 種  {status} {len(raw):,}バイト  別紙らしいリンク {len(betsu)}本")
    for t, u in betsu[:5]:
        print(f"    {t[:24]} → {u}")

    # ---- 別紙 ----
    kouho, yometa, dame, yomenai = [], [], [], []
    for i, (t, u) in enumerate(betsu[:args.limit]):
        time.sleep(WAIT)
        try:
            st, ct, rw = get(u)
        except Konde:
            print(f"△ 別紙「{t[:20]}」 相手が混んでいる。飛ばす")
            dame.append((t, u, "混んでいる"))
            continue
        except urllib.error.HTTPError as e:
            print(f"× 別紙「{t[:20]}」 HTTP {e.code}")
            dame.append((t, u, f"HTTP {e.code}"))
            continue
        except Exception as e:                                   # noqa: BLE001
            print(f"× 別紙「{t[:20]}」 出られなかった（{type(e).__name__}）")
            dame.append((t, u, type(e).__name__))
            continue
        shimau(u, rw)
        # **HTML でないものを 0本 と数えない。**
        # 役所の一覧は PDF や Excel のことがある。リンクの式は HTML 用なので、
        # PDF に当てると必ず 0 になる——**「載っていない」ではなく「読んでいない」**。
        # 「0件は、その道を1回も通っていないときにも出る」（9節）
        if "html" not in (ct or "").lower() and not rw.lstrip()[:1] == b"<":
            katachi = (ct or "不明").split(";")[0]
            print(f"△ 別紙「{t[:20]}」 {katachi} だった。**ここでは読まない**")
            yomenai.append((t, u, katachi))
            continue
        de = jigyousha(u, rw, ct)
        yometa.append((t, u, len(de)))
        kouho += de
        print(f"○ 別紙「{t[:20]}」  {st} {len(rw):,}バイト  候補 {len(de)}本")

    # ホストで重ねる（別紙が地方ごとに分かれていると同じ社が何度も出る）
    matome = {}
    for t, host, top in kouho:
        if host not in matome or (not matome[host][0] and t):
            matome[host] = (t, top)
    kouho = sorted((t, h, top) for h, (t, top) in matome.items())

    lines = [
        "# 遅延証明書を全国に広げるための、事業者の一覧を探した記録", "",
        "**このファイルは `chien_zenkoku.py` が書く。** 手で直さない。",
        "**次の段（`chien_recon.py`）は、ここに並ぶトップから辿る。**", "",
        "ここは**一覧を作っただけ**で、遅延証明書はまだ1件も探していない。",
        "**ドメインを作文していない。** 国土交通省の鉄道関連リンク集から、",
        "向こうが書いたリンクを拾った。", "",
        f"種： {TANE}", "",
        "| | 数 |", "|---|---:|",
        f"| 別紙らしいリンク | {len(betsu):,} |",
        f"| 読めた別紙 | {len(yometa):,} |",
        f"| 相手が返さなかった別紙 | {len(dame):,} |",
        f"| **HTML でなかった別紙（読んでいない）** | {len(yomenai):,} |",
        f"| **事業者の候補（ホストで重ねたあと）** | {len(kouho):,} |", "",
    ]
    if yometa:
        lines += ["## 読んだ別紙", "", "| リンクの文字 | 行き先 | 候補 |",
                  "|---|---|---:|"]
        lines += [f"| {t} | {u} | {n} |" for t, u, n in yometa]
        lines.append("")
    if dame:
        lines += ["## 相手が返さなかった別紙", "",
                  "| リンクの文字 | 行き先 | 理由 |", "|---|---|---|"]
        lines += [f"| {t} | {u} | {w} |" for t, u, w in dame]
        lines.append("")
    if yomenai:
        lines += ["## HTML でなかった別紙", "",
                  "**「事業者が0本」ではない。読んでいない。**",
                  "PDF や Excel はリンクの式が当たらないので、",
                  "**人が1回開いて、どう読むか決めてから**足す。", "",
                  "| リンクの文字 | 行き先 | 形式 |", "|---|---|---|"]
        lines += [f"| {t} | {u} | {w} |" for t, u, w in yomenai]
        lines.append("")
    if kouho:
        lines += ["## 事業者の候補", "",
                  "**鉄道事業者だと確かめてはいない。** リンクが在っただけ。",
                  "次の段が遅延証明書を探しにいって、無ければ無いと記録する。", "",
                  "| リンクの文字 | ホスト | トップ |", "|---|---|---|"]
        lines += [f"| {t} | {h} | {top} |" for t, h, top in kouho]
        lines.append("")
    lines += [
        "## 次に見ること", "",
        "`inbox/chien-zenkoku/*.html` を**人が1つ開く。**",
        "**別紙が事業者の一覧になっているか**を実物で見てから、",
        "次の段を全国ぶん走らせる。", "",
        "**同じ相手に1日2回行かない**（3.4）。市営地下鉄は自治体と",
        "同じホストのことがある（神戸市営地下鉄で踏んだ）。",
        "毎朝の巡回と重なる相手は、検査が止める。", ""]

    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\n事業者の候補 {len(kouho)}本 → {REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
