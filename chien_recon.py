#!/usr/bin/env python3
"""遅延証明書のページを**探して、返ってきたものをバイトのまま保存する。**

ここは**見に行くだけ。** 読み取りは書かない（9節「見本は実物から取る」）。

2026-09-19、中島さんの案。5つのルール全部に○が付いた唯一の題材——

    ① 時間がたつほど価値が増える  各社が数十日で落とす。**誰も過去を持っていない**
    ② 消える理由が事務的          掲載期間が過ぎるだけ
    ③ 判断を書かない              「◯月◯日に◯分遅れた」だけ
    ④ 煽らない                    煽りようがない
    ⑤ 推測しない                  推測する箇所が無い

**そして個人が1人も出てこない**（3.1 の問題がゼロ）。

**URL を作文しない。** 遅延証明書のページの在りかは知らないので、
**各社のトップから、リンクの文字で辿る**（`recon.py` と同じ形）。
トップページだけは公知のドメインを置くが、**その先は辿って見つける。**

**出どころが民間**なのが、既存4サイトと違うところ。
役所は公表する義務があるが、**鉄道会社には無い。**
robots を守るのは同じで、**嫌がられたら止める**（3.4）。

**捕まえないもの**：見つけたページが本当に遅延証明書か。
**実物を人が1回見てから**読み取りを書く。
"""
import argparse
import collections
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

INBOX = os.path.join(HERE, "inbox", "chien")
REPORT = os.path.join(HERE, "data", "ref", "chien-recon.md")
TIMEOUT = 40

# **トップページだけを置く。その先は辿る。**
#
# ここに遅延証明書の URL を直接書くと、**在りかを作文した**ことになる。
# 会社の公式ドメインは公知なので置くが、**当たっているかは実行して確かめる**。
#
# **この一覧は大阪・兵庫の全社ではない。** 見た社と見ていない社を数える（6節）。
KAISHA = [
    ("JR西日本", "https://www.westjr.co.jp/"),
    ("阪急電鉄", "https://www.hankyu.co.jp/"),
    ("阪神電気鉄道", "https://www.hanshin.co.jp/"),
    ("京阪電気鉄道", "https://www.keihan.co.jp/"),
    ("近畿日本鉄道", "https://www.kintetsu.co.jp/"),
    ("南海電気鉄道", "https://www.nankai.co.jp/"),
    ("大阪メトロ", "https://www.osakametro.co.jp/"),
    ("神戸市営地下鉄", "https://www.city.kobe.lg.jp/"),
    ("山陽電気鉄道", "https://www.sanyo-railway.co.jp/"),
    ("神戸電鉄", "https://www.shintetsu.co.jp/"),
]

# 全国ぶんの一覧は `chien_zenkoku.py` が作る。**手で並べない。**
ZENKOKU = os.path.join(HERE, "data", "ref", "chien-zenkoku.md")
# 一覧の表の行。**またがせない**（2026-09-19、`re.S` で隣の行を食べた）
ZEN_GYOU = re.compile(
    r"^\|\s*([^|\n]*?)\s*\|\s*([^|\n]+?)\s*\|\s*(https?://[^\s|]+)\s*\|\s*$",
    re.M)


def kaisha(michi=ZENKOKU):
    """見に行く会社。**どの一覧を使ったかも返す**（ルール⑥）。

    全国ぶんの一覧があればそれを使い、無ければ手で並べた10社に戻る。
    **どちらを使ったかを黙らない。** 「10社しか見ていない」のと
    「全国を見て10社しか当たらなかった」は、まったく違う話になる。

    **捕まえないもの**：一覧に並ぶホストが本当に鉄道事業者か。
    そこは探しに行ってから分かる。
    """
    if os.path.exists(michi):
        honbun = open(michi, encoding="utf-8").read()
        de, mita = [], set()
        for na, host, top in ZEN_GYOU.findall(honbun):
            host = host.strip()
            if host in ("ホスト", "") or re.fullmatch(r"-+", host):
                continue
            if host in mita:
                continue
            mita.add(host)
            de.append((re.sub(r"\s+", " ", na).strip() or host, top))
        if de:
            return de, f"全国の一覧（{os.path.relpath(michi, HERE)}）"
    return list(KAISHA), "手で並べた大阪・兵庫の10社"


# 辿る先を選ぶリンクの文字。**「遅延」だけだと遅延情報（いまの運行）を拾う**
SAGASU = re.compile(r"遅延証明")
LINK = re.compile(r'<a\s[^>]*href\s*=\s*["\']([^"\']+)["\'][^>]*>(.*?)</a>',
                  re.I | re.S)


def moji(s):
    """リンクの文字。タグを落として、実体参照を戻し、**空白を1つに潰す。**

    **潰さないと、記録の表が1行に収まらない。**
    2026-09-19、阪急のリンクの文字に改行が9つ入っていて、
    表の1行が10行になった。読む側の式が**区切り線から一致を始めて、
    JR西日本の行をまるごと食べた。**

    **直すのは読む側ではなく、書く側。** 記録は1行1行にする。
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


def sagasu(base, raw, ctype):
    """そのページの中から、遅延証明書らしいリンクを拾う。

    **「遅延」だけで探さない。** 「遅延情報」は**いまの運行**の話で、
    こちらが欲しい「遅延証明書」（過去の記録）とは別物。
    **語が似ているものを混ぜない**（3.5）。
    """
    honbun, _moji = decode_html(raw, ctype)
    de = []
    for u, t in LINK.findall(honbun):
        t = moji(t)
        if SAGASU.search(t) or SAGASU.search(u):
            de.append((urllib.parse.urljoin(base, u), t))
    # 同じ行き先は1回だけ。**順番は保つ**（先に出たほうが本命のことが多い）
    mita, kekka = set(), []
    for u, t in de:
        if u not in mita:
            mita.add(u)
            kekka.append((u, t))
    return kekka


def main():
    # **関所は main の1行目**（開発系、2026-09-19）。
    # 途中に置くと、手前の処理が先に走る。
    # argparse は知らない引数で終了コード2で止まり、**1バイトも取りに行かない。**
    # `--help` もここで終わる（表示して終わるだけで、外には出ない）
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--limit", type=int, default=3,
                    help="見に行く会社の数。既定は3。まとめて叩かない")
    args = ap.parse_args()

    os.makedirs(INBOX, exist_ok=True)
    zenbu, doko = kaisha()
    print(f"一覧は{doko}。{len(zenbu)}社ある")
    mokuhyo = zenbu[:args.limit]
    mitsuketa, nakatta, dame, derarenai, yamete = [], [], [], [], []

    for i, (na, top) in enumerate(mokuhyo):
        if i:
            time.sleep(WAIT)
        ok, why = check_robots(top)
        if ok is False:
            print(f"× {na} robots.txt が拒否している。取りに行かない")
            dame.append((na, "robots で拒否"))
            continue
        if ok is None:
            # **その会社だけ飛ばす。全部を止めない。**
            #
            # 2026-09-19 に気づいた。ここは `break` にしていたので、
            # **1社が混んでいると、残り9社を1回も見なかった。**
            # 自治体を回る `recon.py` は同じ相手を続けて見るので中止が正しいが、
            # **ここは1社ごとに相手が違う。** 混んでいるのはその1社だけ。
            # 「押し込まない」は**その相手に**押し込まないこと（3.4）
            print(f"△ {na} robots.txt が返らない（{why}）。この社は飛ばす")
            yamete.append(na)
            continue
        try:
            status, ctype, raw = get(top)
        except Konde:
            # 同じ理由で、この社だけ飛ばす
            print(f"△ {na} 相手が混んでいる。この社は飛ばす")
            yamete.append(na)
            continue
        except urllib.error.HTTPError as e:
            print(f"× {na} 相手が HTTP {e.code} と答えた")
            dame.append((na, f"HTTP {e.code}"))
            continue
        except Exception as e:                                  # noqa: BLE001
            print(f"× {na} 出られなかった（{type(e).__name__}: {e}）")
            derarenai.append(na)
            continue

        # **トップページもバイトのまま残す。** なぜ見つからなかったかを
        # あとで調べられるようにする（9節）
        yasui = re.sub(r"[^0-9A-Za-z]+", "-", urllib.parse.urlparse(top).netloc)
        with open(os.path.join(INBOX, f"{yasui}-top.html"), "wb") as f:
            f.write(raw)

        rinku = sagasu(top, raw, ctype)
        if rinku:
            mitsuketa.append((na, top, rinku))
            print(f"○ {na}  {status} {len(raw):,}バイト  "
                  f"遅延証明のリンク {len(rinku)}本")
            for u, t in rinku[:3]:
                print(f"    「{t}」 → {u}")
        else:
            nakatta.append((na, top))
            print(f"△ {na}  {status} {len(raw):,}バイト  "
                  "**トップに遅延証明のリンクが無い**（別の入口かもしれない）")

    mita = (len(mitsuketa) + len(nakatta) + len(dame)
            + len(derarenai) + len(yamete))
    # **全部が同じ理由で失敗したら、相手ではなく自分を疑う。**
    #
    # 2026-09-19、統括がこれをやった。**外に出られない環境で走らせて、
    # その結果を記録として commit した。** 記録には「10社とも出られなかった」
    # とだけ書いてあり、**どこから走ったかは書いていない。**
    # main で読んだ人は「鉄道会社に繋がらない」と読む。
    #
    # 「こちらが出られなかった」は**こちらの事実**なので数え方は正しい。
    # だが**全件がそれなら、相手について何も言っていない。** そう書く。
    minna_dame = (mita > 0 and len(derarenai) == mita)

    lines = [
        "# 遅延証明書のページを探した記録", "",]
    if minna_dame:
        lines += [
            "> ⚠️ **この回は1社にも接続できていない。**",
            f"> {mita}社すべてが「こちらが出られなかった」。",
            "> **相手の話ではなく、走らせた場所の話**の可能性が高い。",
            "> ここに書いてある数から、**鉄道会社について何も読み取らないこと。**", ""]
    lines += ["",
        "**このファイルは `chien_recon.py` が書く。** 手で直さない。", "",
        "ここは**探しただけ**で、まだ1件も読み取っていない。",
        "**URL は作文していない。** 各社のトップから、リンクの文字で辿った。", "",
        "| | 会社数 |", "|---|---:|",
        f"| **リンクが見つかった** | {len(mitsuketa):,} |",
        f"| トップに無かった | {len(nakatta):,} |",
        f"| 相手が「だめ」と答えた | {len(dame):,} |",
        f"| **こちらが出られなかった** | {len(derarenai):,} |",
        f"| **混んでいたので飛ばした** | {len(yamete):,} |",
        f"| **まだ見ていない** | {len(zenbu) - mita:,} |",
        f"| この一覧に載せた会社 | {len(zenbu):,} |", "",
        f"**一覧の出どころ：{doko}。**", "",
        "**「全国の全社」とは書かない。** 一覧に載っていない会社がある",
        "（分母を必ず添える・3.2）。", "",
    ]
    if mitsuketa:
        lines += ["## 見つかったリンク", "",
                  "| 会社 | リンクの文字 | 行き先 |", "|---|---|---|"]
        for na, _top, rinku in mitsuketa:
            for u, t in rinku:
                lines.append(f"| {na} | {t} | {u} |")
        lines.append("")
    if nakatta:
        lines += ["## トップに無かった会社", "",
                  "**「遅延証明書を出していない」ではない。**",
                  "トップから1回で辿れなかっただけ。入口が別にあるかもしれない。", ""]
        for na, top in nakatta:
            lines.append(f"- {na}（{top}）")
        lines.append("")
    lines += ["## 次に見ること", "",
              "`inbox/chien/*.html` を**人が1つ開く。**",
              "見つかったリンクの先が**本当に遅延証明書か**、",
              "形式（HTMLの表／PDF／画像）と、**何日分残っているか**を",
              "実物で見てから、読み取りを書く。", "",
              "## 出どころが民間であること", "",
              "既存4サイトは全部、役所が出どころだった。",
              "**鉄道会社には公表する義務が無い。**",
              "robots を守るのは同じで、**嫌がられたら止める**（3.4）。", ""]

    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("\n".join(lines[6:16]))
    print(f"→ {REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
