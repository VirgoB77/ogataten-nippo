#!/usr/bin/env python3
"""見つけた遅延証明書のページを、**バイトのまま取ってくる。**

1段目（`chien_recon.py`）が**向こうのサイトから拾ったリンク**を、
`data/ref/chien-recon.md` に記録した。**ここはその記録から読む。**
**統括の記憶からは読まない。** 記録に無いものは取りに行かない。

2026-09-19 の1段目で分かったこと——

    JR西日本  http://delay.trafficinfo.westjr.co.jp/   **別ドメイン。しかも http**
    南海      https://www.traffic.nankai.co.jp/delay   **別ドメイン**

**ホストが変われば robots も変わる。** 1段目でトップの robots を見たからといって、
**その先のホストを見たことにはならない。** ここで見直す。

そして **http を https に書き換えない。** 相手がそう書いたものをそのまま辿る。
書き換えるのは「向こうが言っていないこと」をこちらで決めること（3.5）。

**捕まえないもの**：中身が本当に遅延証明書か。何日分あるか。
**実物を人が1回見てから**読み取りを書く。
"""
import argparse
import collections
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

RECORD = os.path.join(HERE, "data", "ref", "chien-recon.md")
INBOX = os.path.join(HERE, "inbox", "chien")
REPORT = os.path.join(HERE, "data", "ref", "chien-get.md")
TIMEOUT = 40

# 記録の表の行。**1行に収まっているものだけ**を読む。
#
# 2026-09-19、ここを `re.S`（改行もまたぐ）で書いて踏んだ。
# 上にある件数の表の空セル `| | 会社数 |` から一致が始まり、
# **JR西日本の行をまるごと食べていた**（会社の欄が空文字になって落ちた）。
#
# **またがせない。** またぐ必要があるのは書く側が改行を残したせいなので、
# そちらを直した（`chien_recon.moji`）。**読む側を器用にしない。**
GYOU = re.compile(
    r"^\|\s*([^|\n]+?)\s*\|\s*([^|\n]*?)\s*\|\s*(https?://[^\s|]+)\s*\|\s*$",
    re.M)


def yomu(michi=RECORD):
    """1段目の記録から、会社と行き先を読む。**こちらで足さない。**

    同じ行き先は1回だけ。**クエリだけ違うものは同じとみなす**——
    1段目で阪急が `?link=hamburger` 付きと素の2本になった。
    **同じページを2回取りに行かない**（3.4）。
    """
    if not os.path.exists(michi):
        return []
    honbun = open(michi, encoding="utf-8").read()
    mita, de = set(), []
    for na, _moji, url in GYOU.findall(honbun):
        na = re.sub(r"\s+", " ", na).strip()
        if na in ("会社", "") or re.fullmatch(r"-+", na):
            continue
        p = urllib.parse.urlparse(url)
        kagi = (p.scheme, p.netloc, p.path.rstrip("/"))
        if kagi in mita:
            continue
        mita.add(kagi)
        de.append((na, url))
    return de


def ikisaki(michi=RECORD):
    """**この回で出て行く先。** 見張りがここを呼ぶ（2026-09-20）。

    「同じ相手に1日2回行かないか」の見張りは、はじめ**ソースに書いてある
    URL を目で拾って**いた。それだと2つとも外れる。

    * ここはソースに URL を1つも書いていない（記録から読む）→ **相手が0に見える**
    * 記録を丸ごと読むと、「**トップに無かった会社**」まで行き先に数える
      —— 神戸市営地下鉄がこれで、**毎朝の巡回で行く神戸市と同じホスト**だった

    どちらも「見張りが、本番と違う道で数えていた」から起きる。
    **本番と同じ `yomu()` を通す。** ここが増えれば見張りも増える。
    """
    return [u for _na, u in yomu(michi)]


def get(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,*/*",
        "Accept-Language": "ja",
    })
    try:
        deta = urllib.request.urlopen(req, timeout=TIMEOUT)
    except urllib.error.HTTPError as e:
        if is_busy(e):
            raise Konde(f"相手が混んでいると言っている（HTTP {e.code}）") from e
        raise
    with deta as r:
        return r.status, r.headers.get("Content-Type", ""), r.geturl(), r.read()


def yasui(url):
    p = urllib.parse.urlparse(url)
    return re.sub(r"[^0-9A-Za-z]+", "-", p.netloc + p.path).strip("-")[:60]


# 下見で数える形。**読み取りではない。** 何が在るかを数えるだけ
HIDUKE = [
    ("YYYY年M月D日", re.compile(r"20\d\d\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日")),
    ("M月D日", re.compile(r"(?<!\d)\d{1,2}\s*月\s*\d{1,2}\s*日")),
    ("YYYY-MM-DD", re.compile(r"20\d\d[-/]\d{1,2}[-/]\d{1,2}")),
]
FUN = re.compile(r"\d{1,3}\s*分")
HYO = re.compile(r"<table[\s>]", re.I)


def shitami(raw):
    """**何が在るかを数えるだけ。読み取らない。**

    「何日分残っているか」は、このサイトの設計でいちばん効く数字。
    **実物を見ないと決められない**ので、まず形だけ数える。

    返すのは（日付の書き方ごとの数, いちばん古い/新しい, 表の数, 「◯分」の数）。
    **日付を組み立てない。** 見つけた文字列をそのまま並べる。

    **捕まえないもの**：その日付が遅延の日付か。ページの更新日かもしれない。
    **人が実物を1回見るまで、決めない。**
    """
    honbun, _moji = decode_html(raw, "")
    kazu, mitsuketa = {}, []
    for na, shiki in HIDUKE:
        de = shiki.findall(honbun)
        if de:
            kazu[na] = len(de)
            mitsuketa += [re.sub(r"\s+", "", x) for x in de]
    return {
        "hiduke": kazu,
        "rei": sorted(set(mitsuketa))[:3],
        "hyo": len(HYO.findall(honbun)),
        "fun": len(FUN.findall(honbun)),
        "moji": len(honbun),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--limit", type=int, default=99,
                    help="取りに行く数。既定は記録にある全部")
    args = ap.parse_args()

    saki = yomu()
    if not saki:
        print(f"{RECORD} に行き先が無い。先に chien_recon.py を走らせる")
        return 1

    os.makedirs(INBOX, exist_ok=True)
    totta, dame, derarenai, konde, robots_dame = [], [], [], [], []
    mokuhyo = saki[:args.limit]

    for i, (na, url) in enumerate(mokuhyo):
        if i:
            time.sleep(WAIT)
        # **ホストごとに robots を見直す。** 1段目はトップのホストしか見ていない
        ok, why = check_robots(url)
        if ok is False:
            print(f"× {na} robots.txt が拒否している（{url}）。取りに行かない")
            robots_dame.append((na, url))
            continue
        if ok is None:
            print(f"△ {na} robots.txt が返らない（{why}）。この社は飛ばす")
            konde.append((na, url))
            continue
        try:
            status, ctype, saishu, raw = get(url)
        except Konde:
            print(f"△ {na} 相手が混んでいる。この社は飛ばす")
            konde.append((na, url))
            continue
        except urllib.error.HTTPError as e:
            print(f"× {na} 相手が HTTP {e.code} と答えた")
            dame.append((na, url, f"HTTP {e.code}"))
            continue
        except Exception as e:                                   # noqa: BLE001
            print(f"× {na} 出られなかった（{type(e).__name__}: {e}）")
            derarenai.append((na, url))
            continue

        michi = os.path.join(INBOX, f"{yasui(url)}.bin")
        with open(michi, "wb") as f:
            f.write(raw)
        tobasare = "" if saishu.rstrip("/") == url.rstrip("/") else f" → {saishu}"
        totta.append((na, url, status, ctype, len(raw), saishu, shitami(raw)))
        print(f"○ {na}  {status} {ctype} {len(raw):,}バイト{tobasare}")

    mita = len(totta) + len(dame) + len(derarenai) + len(konde) + len(robots_dame)
    minna_dame = mita > 0 and len(derarenai) == mita

    lines = ["# 遅延証明書のページを取ってきた記録", ""]
    if minna_dame:
        lines += ["> ⚠️ **この回は1社にも接続できていない。**",
                  f"> {mita}社すべてが「こちらが出られなかった」。",
                  "> **相手の話ではなく、走らせた場所の話**の可能性が高い。", ""]
    lines += [
        "**このファイルは `chien_get.py` が書く。** 手で直さない。", "",
        "**行き先は1段目の記録（`chien-recon.md`）から読んだ。**",
        "統括の記憶からは読んでいない。記録に無いものは取りに行かない。", "",
        "**まだ1件も読み取っていない。** 中身は成果物（artifact）にある。", "",
        "| | 会社数 |", "|---|---:|",
        f"| **取れた** | {len(totta):,} |",
        f"| robots が拒否 | {len(robots_dame):,} |",
        f"| 相手が「だめ」と答えた | {len(dame):,} |",
        f"| **こちらが出られなかった** | {len(derarenai):,} |",
        f"| 混んでいたので飛ばした | {len(konde):,} |",
        f"| 記録にあった行き先 | {len(saki):,} |", "",
    ]
    if totta:
        lines += ["## 取れたもの", "",
                  "| 会社 | 形式 | 大きさ | 行き先 |", "|---|---|---:|---|"]
        for na, url, _s, ctype, n, saishu, _m in totta:
            k = (ctype or "").split(";")[0] or "（不明）"
            tobi = "" if saishu.rstrip("/") == url.rstrip("/") else "<br>↳ " + saishu
            lines.append(f"| {na} | `{k}` | {n:,} | {url}{tobi} |")
        lines.append("")
    if robots_dame:
        lines += ["## robots が拒否した", "",
                  "**取りに行かない**（3.4）。回り込まない。", ""]
        for na, url in robots_dame:
            lines.append(f"- {na}（{url}）")
        lines.append("")
    if totta:
        lines += ["## 下見（**数えただけ。読み取っていない**）", "",
                  "**何日分残っているか**が、このサイトでいちばん効く数字。",
                  "実物を見ないと決められないので、まず形だけ数えた。", "",
                  "| 会社 | 日付の書き方 | 見つけた日付の例 | 表 | 「◯分」 | 文字数 |",
                  "|---|---|---|---:|---:|---:|"]
        for na, _u, _s, _c, _n, _f, m in totta:
            kaki = "・".join(f"{k} {v}" for k, v in m["hiduke"].items()) or "**無い**"
            rei = " ".join(m["rei"]) or "—"
            lines.append(f"| {na} | {kaki} | {rei} | {m['hyo']} | "
                         f"{m['fun']} | {m['moji']:,} |")
        lines += ["",
                  "**この日付が遅延の日付とは限らない。** ページの更新日かもしれない。",
                  "**人が実物を1回見るまで、決めない。**", "",
                  "日付が「無い」のは、**中身が JavaScript で入る**か、",
                  "**別のページに飛ばしている**可能性がある（中身が小さい社に多い）。", ""]

    lines += ["## 次に見ること", "",
              "`inbox/chien/*.bin` を**人が1つ開く。**",
              "**何日分残っているか**、形式（HTMLの表／PDF／画像／JSON）、",
              "**遅れた分数の書き方**を実物で見てから、読み取りを書く。", ""]

    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("\n".join(lines[:4] if minna_dame else lines[5:14]))
    print(f"→ {REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
