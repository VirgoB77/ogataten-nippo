#!/usr/bin/env python3
"""停電の記録を**探す**段。**まだ1件もためない。**

## なぜ急ぐか

外の目が10社を調べた（2026-09-21・**こちらは見ていない**）。
**短いところで7日、長いところで60日**しか残らないと言われた。
横断しているサービスも、残すのは1か月まで。

**今日ためなかった分は、もう作れない。** 大店立地法の届出が数か月残るのとは違う。

## それでも、いきなり取りに行かない

**URLを作文しない**（3.4）。全国10社のドメインを思い出して並べると、
外れていれば**関係のない誰かのサーバーを叩く。**

なので**種を1つだけ人が入れる。** 見つからなければ**黙って0本にせず、止まる**（9節）。

## 入り口は2つ。**どちらから来たかを、記録に書く**

    `--tane`   **役所の一覧ページ**から辿る。**向こうが書いたリンク**を使う
    `--tops`   **会社のトップを、人が直に渡す**

`--tops` は、**こちらが役所のページから辿ったものではない。**
2026-09-21 に使った一覧は、外の目が
**「社名から作文したものではなく、公的資料に実際に記載されているURL」**
と言ったもの。**こちらはその公的資料を見ていない。**

**見ていないので、見ていないと書く。**「測ったのが誰か」を記録に残す。
**robots は `--tane` のときと同じように、1社ずつ先に見る。**

    ① この段        種のページから、会社の候補を拾う。**robots を見る**
    ② 人が見る      実物のページを1回開く。**速報か記録かを目で確かめる**
    ③ 毎朝の巡回    見つけたページを毎日ためる

## 深さは2段まで。**1段目で終わらないように**

2026-09-21 に1段目を走らせた。**記録らしいリンクは、9社中1社しか出なかった。**

**0本は「無い」ではない**（9節）。実際、外の目は各社の履歴ページを引用していて、
**別のホスト**（`teiden-info.◯◯` のような）にあると分かっている。
**会社のトップには、直のリンクが無いだけ。**

    `--fukasa 1`   トップだけ見る（既定）
    `--fukasa 2`   **速報らしいリンクを1段だけ辿って、その先で記録を探す**

**3段目は作らない。** 辿るほど、当たっているか誰も確かめられなくなる。

## **速報**と**記録**を混ぜない

`chien_recon.py` で踏んだのと同じ形。「遅延情報」は**いまの運行**、
「遅延証明書」は**過去の記録**で、語が似ているだけの別物だった。

    **停電情報**     いま停電しているか（**速報**）。他がやっている
    **停電履歴**     いつ、どこで、何軒、何時間（**記録**）。**こちらが欲しいのはこれ**

**語が似ているものを混ぜない**（3.5）。

## 1日1回しか行かないので、**その日のうちに直った分は見えない**

外の目いわく、各社とも速報を優先していて、**軒数や原因をあとから直す。**
そして**直す前の値を見せている会社は、今回1社も確認できなかった**と言われた。

つまり毎日ためれば、**公式には無い形**（直る前と直った後）が手元に残る。

**ただし、こちらが持てるのは「日をまたいだ訂正」だけ。**
**同じ相手に1日2回行かない**（3.4）ので、**その日のうちに直ったものは1つの値にしか見えない。**

    ✅ 「9/20 に見た値と、9/21 に見た値が違った」
    ❌ 「9/20 の午前と午後で違った」   ← **こちらは行っていない**

出すときも、この差を名乗る。**見ていないものを「変わらなかった」と書かない。**

## 足して比べない

外の目が10社の掲載基準を並べた（**こちらは確かめていない**）。
**何分以上を1件と数えるか、高圧を含むかが、会社ごとに違う。**

そのまま縦に足すと、**数え方の違いが「多い／少ない」に見える**（9節）。
**この段は取るだけなので、まだ関係ない。** 足すときに効く。
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common.fetch import (  # noqa: E402
    Konde, TIMEOUT, UA, WAIT, check_robots, decode_html, is_busy,
)
from common.runday import today  # noqa: E402

# 生のバイトは `inbox/`（`.gitignore`）。**公開側には1バイトも入れない**（3.4）
INBOX = HERE / "inbox" / "teiden"
# 記録は「何を見て、何が返って、robots が何と言ったか」だけ。中身は入れない
KIROKU = HERE / "data" / "ref" / "teiden-recon.md"

LINK = re.compile(r'<a\s[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)

# **記録**を指す語。**速報だけを指す語とは分ける**
KIROKU_GO = ("停電履歴", "過去の停電", "停電実績", "復旧済", "過去停電")
SOKUHO_GO = ("停電情報", "停電状況", "現在の停電", "停電マップ")

# **人が規約を読んだ結果。** ホストごとに持つ。
#
# **robots と規約は別の欄**（正本9節）。robots が許可でも、規約が断っていれば通さない。
# **片方で他方を代用しない。**
#
# 語は関所の正本（`floor_kanmon.KEKKA`）と同じものを使う——
# 取ってよい / 未確認 / 規約未確定 / 取ってはいけない。
#
# **ここに無いホストは「未確認」。** 「未確認」を「許可」と読まない。
YAKUSOKU = {
    "www.kyuden.co.jp": {
        "mei": "九州電力送配電",
        "mita_hi": "2026-09-21",
        "kekka": "取ってはいけない",
        "robots": "許可",          # **robots は通っている。それとは別に断られている**
        "url": "https://www.kyuden.co.jp/td/sitepolicy/rule.html",
        "riyuu": "利用規約の「**禁止事項**」で、当社HP掲載データを"
                 "**プログラム等で機械的に取得する行為（スクレイピング等）を"
                 "明示的に禁止**しているため、**鯨屋の継続自動観測にも及ぶ**と判断する"
                 "（統括・2026-09-21）。**robots 許可とは分けて記録する。**"
                 "**九電1社の取得経路を停止する。停電DB自体は却下しない。**"
                 "**事前許可、または公式に別条件で提供される取得手段が"
                 "将来確認できた場合のみ再評価。**",
    },
}


def yakusoku_no_kekka(url):
    """その URL のホストについて、**人が規約を読んだ結果**を返す。

    **ここに無ければ「未確認」。**「未確認」を「許可」と読まない（ルール⑥）。
    """
    import urllib.parse as _up
    host = _up.urlsplit(url).netloc
    return YAKUSOKU.get(host, {"kekka": "未確認", "riyuu": "", "mei": host})


def moji(s: str) -> str:
    t = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    return re.sub(r"\s+", " ", t).strip()


def get(url: str):
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


def host(u: str) -> str:
    return (urllib.parse.urlparse(u).hostname or "").lower()


def onaji_yakusho(a: str, b: str) -> bool:
    """同じ役所のドメインか。`go.jp` は後ろ3つで比べる（`chien_zenkoku.py` と同じ）。"""
    x, y = a.split("."), b.split(".")
    n = 3 if a.endswith(".go.jp") or b.endswith(".go.jp") else 2
    return x[-n:] == y[-n:]


def kouho(tane_url: str, raw: bytes, ctype: str):
    """種のページから、**外のホスト**を会社の候補として拾う。

    **こちらが社名を並べない。** 向こうが書いたリンクだけを使う。
    """
    honbun, _ = decode_html(raw, ctype)
    tane_host = host(tane_url)
    mita, de = set(), []
    for u, t in LINK.findall(honbun):
        saki = urllib.parse.urljoin(tane_url, u)
        if not saki.startswith("http"):
            continue
        h = host(saki)
        if not h or h == tane_host or onaji_yakusho(h, tane_host):
            continue  # 役所の中は候補にしない
        top = f"{urllib.parse.urlparse(saki).scheme}://{h}/"
        if top in mita:
            continue
        mita.add(top)
        de.append({"top": top, "host": h, "moji": moji(t)[:60], "kara": saki})
    return de


def sagasu(base: str, raw: bytes, ctype: str):
    """そのページから、**記録**らしいリンクを拾う。速報は別に数える。"""
    honbun, _ = decode_html(raw, ctype)
    kiroku, sokuho = [], []
    for u, t in LINK.findall(honbun):
        saki = urllib.parse.urljoin(base, u)
        if not saki.startswith("http"):
            continue
        # **探した語を query に持つ目録に当たらないよう、path だけで見る**
        # （2026-09-20、保健所で全リンクが当たった）
        michi = urllib.parse.urlparse(saki).path
        ba = moji(t) + " " + michi
        if any(g in ba for g in KIROKU_GO):
            kiroku.append({"url": saki, "moji": moji(t)[:60]})
        elif any(g in ba for g in SOKUHO_GO):
            sokuho.append({"url": saki, "moji": moji(t)[:60]})
    return kiroku, sokuho


def moguru(d: dict, hiduke: str, eda: int):
    """**1段だけ深く。** 速報らしいリンクの先で、記録を探す。

    **辿る先は、向こうが書いたリンクだけ。** こちらでURLを組み立てない。
    **記録が既に見つかっている社は辿らない**（もう用が足りている）。
    """
    d["mogutta"] = []
    if d.get("kiroku") or not d.get("sokuho"):
        return d
    for x in d["sokuho"][:eda]:
        time.sleep(WAIT)
        saki = {"url": x["url"], "moji": x["moji"], "robots": None,
                "status": None, "kiroku": [], "naze": ""}
        ok, naze = check_robots(x["url"])
        saki["robots"] = bool(ok)
        if not ok:
            saki["naze"] = f"robots が拒否した（{naze}）。**取りに行かない**"
            d["mogutta"].append(saki)
            continue
        try:
            st, ctype, raw = get(x["url"])
        except Konde:
            raise
        except Exception as e:
            saki["naze"] = f"{type(e).__name__}"
            d["mogutta"].append(saki)
            continue
        saki["status"] = st
        na = re.sub(r"[^a-z0-9.]+", "_",
                    host(x["url"]) + urllib.parse.urlparse(x["url"]).path)[:80] + ".html"
        (INBOX / hiduke).mkdir(parents=True, exist_ok=True)
        (INBOX / hiduke / na).write_bytes(raw)
        saki["kiroku"], _ = sagasu(x["url"], raw, ctype)
        d["mogutta"].append(saki)
    return d


def hitotsu(top: str, hiduke: str):
    """1社ぶん。**robots を先に見る。拒否なら取りに行かない。回り込まない**（3.4）。"""
    d = {"top": top, "robots": None, "status": None, "kiroku": [], "sokuho": [],
         "naze": ""}
    ok, naze = check_robots(top)
    d["robots"] = bool(ok)
    if not ok:
        d["naze"] = f"robots が拒否した（{naze}）。**取りに行かない**"
        return d
    time.sleep(WAIT)
    try:
        st, ctype, raw = get(top)
    except Konde:
        raise  # **混んでいると言われたら、その回は止める**
    except Exception as e:
        d["naze"] = f"{type(e).__name__}"
        return d
    d["status"] = st
    (INBOX / hiduke).mkdir(parents=True, exist_ok=True)
    na = re.sub(r"[^a-z0-9.]+", "_", host(top)) + ".html"
    (INBOX / hiduke / na).write_bytes(raw)
    d["kiroku"], d["sokuho"] = sagasu(top, raw, ctype)
    return d


def houkoku(tane, kouho_ichiran, kekka, hiduke):
    L = []
    a = L.append
    a("# 停電の記録を探した記録")
    a("")
    a(f"**{hiduke}** に `teiden_recon.py` が走った。**まだ1件もためていない。**")
    a("")
    a(f"    どこから      {tane}")
    a(f"    候補（外のホスト） {len(kouho_ichiran)} 件")
    a(f"    開いた         {len(kekka)} 件")
    a("")
    a("**robots が拒否した相手には行っていない。回り込んでもいない。**")
    a("")
    a("## 1社ずつ")
    a("")
    for d in kekka:
        a(f"### {d['top']}")
        a("")
        a(f"    robots   {'よい' if d['robots'] else '**拒否**'}")
        a(f"    返った   {d['status']}")
        if d["naze"]:
            a(f"    わけ     {d['naze']}")
        a(f"    記録らしいリンク  {len(d['kiroku'])} 本")
        for x in d["kiroku"][:5]:
            a(f"      - {x['moji']}  {x['url']}")
        a(f"    速報らしいリンク  {len(d['sokuho'])} 本  ← **こちらが欲しいものではない**")
        for x in d["sokuho"][:5]:
            a(f"      - {x['moji']}  {x['url']}")
        for saki in d.get("mogutta") or []:
            a("")
            a(f"    **↓ 1段もぐった**  {saki['url']}")
            a(f"      robots   {'よい' if saki['robots'] else '**拒否**'}")
            a(f"      返った   {saki['status']}")
            if saki["naze"]:
                a(f"      わけ     {saki['naze']}")
            a(f"      記録らしいリンク  {len(saki['kiroku'])} 本")
            for x in saki["kiroku"][:5]:
                a(f"        - {x['moji']}  {x['url']}")
        a("")
    a("---")
    a("")
    a("**この一覧がどこから来たかは、上に書いたとおり。**")
    a("**人が直に渡した回は、こちらが役所のページから辿ったものではない。**")
    a("")
    a("**0本でも、それは「無い」ではない。** 語が違うだけのことがある。")
    a("**次は人が実物を1回開く。** 速報か記録かは、目で見ないと決まらない。")
    return "\n".join(L) + "\n"


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--tane", help="一般送配電事業者の一覧が載っている公的なページ")
    p.add_argument("--tops", help="会社のトップを直に渡す（改行かカンマ区切り）。"
                                  "**こちらが役所のページから辿ったものではないと記録に書く**")
    p.add_argument("--limit", type=int, default=3, help="開く相手の数（既定3）")
    p.add_argument("--fukasa", type=int, default=1,
                   help="1=トップだけ / 2=速報リンクを1段だけ辿る。**3段目は無い**")
    p.add_argument("--eda", type=int, default=3, help="1社あたり、もぐる本数（既定3）")
    a = p.parse_args(argv)

    if a.tops:
        # **人が直に渡した一覧。** こちらは役所のページから辿っていない
        ichiran = []
        for u in re.split(r"[,\s]+", a.tops):
            u = u.strip()
            if not u.startswith("http"):
                continue
            # **渡されたURLは、そのまま使う。** ドメインだけに丸めない——
            # 人は「ここ」と指している。`hepco.co.jp/network/` を
            # `hepco.co.jp/` に丸めると、**送配電会社の部屋ではなく親会社の玄関**になる
            # （2026-09-21、10社のうち6社がそうなるところだった）
            ichiran.append({"top": u, "host": host(u),
                            "moji": "", "kara": "人が直に渡した（そのまま使う）"})
        if not ichiran:
            print("--tops に http で始まるURLが1つも無い。**0本として進めない**",
                  file=sys.stderr)
            return 6
        hiduke = today()
        # **日ごとの置き場は、ここで作る。** 開く段の中で作っていたので、
        # **1社も開けなかった回に、記録を書こうとして落ちていた**（2026-09-21）
        (INBOX / hiduke).mkdir(parents=True, exist_ok=True)
        kekka = []
        for d in ichiran[: a.limit]:
            time.sleep(WAIT)
            x = hitotsu(d["top"], hiduke)
            if a.fukasa >= 2:
                x = moguru(x, hiduke, a.eda)
            kekka.append(x)
        KIROKU.write_text(
            houkoku("**人が直に渡した一覧。** 外の目が「公的資料に記載されている」と"
                    "言ったもので、**こちらはその公的資料を見ていない**",
                    ichiran, kekka, hiduke), encoding="utf-8")
        (INBOX / hiduke / "_kouho.json").write_text(
            json.dumps(ichiran, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"渡された {len(ichiran)} / 開いた {len(kekka)}")
        print(f"  {KIROKU}")
        return 0

    if not a.tane:
        # **作文しない。** 既定の URL を埋めると、外れたとき誰かのサーバーを叩く
        print("種も一覧も無い。**URLを作文しないので、ここで止まる。**", file=sys.stderr)
        print("", file=sys.stderr)
        print("欲しいのは「一般送配電事業者10社が一覧になっている公的なページ」。", file=sys.stderr)
        print("見つけたら --tane に渡す。**社名から推測したURLは入れない。**", file=sys.stderr)
        return 2

    # **時計を直に見ない。** `RUN_DATE` を渡した回に、渡せていないことに気づけない
    hiduke = today()
    INBOX.mkdir(parents=True, exist_ok=True)

    ok, naze = check_robots(a.tane)
    if not ok:
        print(f"種の robots が拒否した（{naze}）。**取りに行かない**", file=sys.stderr)
        return 3
    st, ctype, raw = get(a.tane)
    if st != 200:
        print(f"種が {st} を返した。**0本として進めない**", file=sys.stderr)
        return 4
    (INBOX / hiduke).mkdir(parents=True, exist_ok=True)
    (INBOX / hiduke / "_tane.html").write_bytes(raw)

    (INBOX / hiduke).mkdir(parents=True, exist_ok=True)
    ichiran = kouho(a.tane, raw, ctype)
    if not ichiran:
        print("種から外のホストが1つも拾えなかった。**「無い」ではなく「拾えなかった」**",
              file=sys.stderr)
        return 5

    kekka = []
    for d in ichiran[: a.limit]:
        time.sleep(WAIT)
        x = hitotsu(d["top"], hiduke)
        if a.fukasa >= 2:
            x = moguru(x, hiduke, a.eda)
        kekka.append(x)

    KIROKU.write_text(houkoku(a.tane, ichiran, kekka, hiduke), encoding="utf-8")
    (INBOX / hiduke / "_kouho.json").write_text(
        json.dumps(ichiran, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"候補 {len(ichiran)} / 開いた {len(kekka)}")
    print(f"  {KIROKU}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
