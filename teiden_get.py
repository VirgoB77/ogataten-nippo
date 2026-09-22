#!/usr/bin/env python3
"""停電の記録を**毎日ためる**段。**読み取らない。**

## なぜこれが要るか

外の目が10社を調べた（2026-09-21・**こちらは未確認**）。

    履歴が残るのは **7日〜60日**。横断サービスでも **1か月**
    **訂正する前の値を見せている会社は、1社も確認できなかった**

つまり**毎日ためれば、公式には無い形**（訂正の前と後）が手元に残る。

**これが、この事業でいちばん条件の揃った題材。** 軸3本が全部立つ。

    ① 消えるか            **7日で消える**
    ② 買う人がいるか       **未測定**
    ③ 後から組み直せないか  **組み直せない**（訂正前は、その日見た者しか持っていない）

## こちらが持てるのは「**日をまたいだ訂正**」だけ

**同じ相手に1日2回行かない**（3.4）。だから、

    ✅ 「◯日に見た値と、翌日に見た値が違った」
    ❌ 「◯日の午前と午後で違った」   ← **こちらは行っていない**

**見ていないものを「変わらなかった」と書かない**（ルール⑥）。

## **消えた**と**差し替わった**は、別の見張り（9節）

    **消えた**       引けなくなる          → 見れば分かる
    **差し替わった**  同じ場所で中身が変わる  → **消失の見張りには1回も鳴らない**

なので**指紋を取って、前と比べる。** 長さだけ見ない——**同じ長さで中身が変わる**。

## ⚠️ **毎日変わるページ**は、指紋では訂正を見つけられない

「最終更新 ◯時◯分」のような表示があると、**中身が同じでも指紋が毎日変わる。**
そうなったら、**そのページでは指紋が効かない**と分かる。**それも記録に書く。**

**0件でも「無い」ではない**のと同じで、**毎日鳴るのも「毎日変わった」ではない。**

## **1段目が走った日は、この段は走らない**

1段目（`teiden_recon.py`）は**押すだけ**、この段は**毎日**。
同じ日に両方走ると、**同じ相手に1日2回行く**（3.4）。

**相手の数で数える。手順書の本数ではない。**
なので**1段目の記録の日付を見て、今日ならこの段は止まる。**

**黙って飛ばさない。** 止まったことを、そう書いて終わる（9節）。

## 保存の状態と、公開の状態を**別に持つ**（9節）

**分けていないと、問題が起きたときに「消すか、出し続けるか」しか選べない。**
この段が触るのは**保存の状態だけ。** 公開は**まだ何も決めていない。**

## 出すもの

    inbox/teiden/<日付>/…     生のバイト（`.gitignore`。公開側に1バイトも入れない）
    data/ref/teiden-ledger.json  **指紋の台帳**（URL・見た日・指紋・保存の状態）
    data/ref/teiden-get.md       人が読む記録

**生のバイトは、そのまま置く。読み取りは後で何度でもやり直せる**（取得は取り返せない）。
"""
from __future__ import annotations

import argparse
import hashlib
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
    Konde, TIMEOUT, UA, WAIT, check_robots, is_busy,
)
from common.runday import today  # noqa: E402
from teiden_recon import yakusoku_no_kekka  # noqa: E402  **規約の結果は1か所**

RECON = HERE / "data" / "ref" / "teiden-recon.md"
DAICHO = HERE / "data" / "ref" / "teiden-ledger.json"
KIROKU = HERE / "data" / "ref" / "teiden-get.md"
INBOX = HERE / "inbox" / "teiden"

# 1段目の記録の中の、リンクの行。`      - 文字  URL` の形
GYOU = re.compile(r"^\s*-\s+(.*?)\s{2,}(https?://\S+)\s*$", re.M)


def yomu(michi: Path = None):
    """1段目の記録から、**記録らしいリンク**だけを読む。**こちらで足さない。**

    速報のリンクも同じ形で並んでいるので、**「記録らしいリンク」の見出しの下**だけ見る。
    **クエリだけ違うものは同じ**とみなす（同じページに2回行かない・3.4）。

    **既定を `def` のときに固めない。** 固めると、見張りが記録を差し替えても
    **本物の記録を読み続ける**（2026-09-21、実際にそうなっていた。
    差し替えたつもりの検査が、ずっと本番のファイルを見ていた）。
    """
    michi = michi or RECON
    if not michi.exists():
        return []
    mita, de = set(), []
    tsukau = False
    for gyou in michi.read_text(encoding="utf-8").splitlines():
        if "記録らしいリンク" in gyou:
            tsukau = True
            continue
        if "速報らしいリンク" in gyou or gyou.startswith("###"):
            tsukau = False
        if not tsukau:
            continue
        m = GYOU.match(gyou)
        if not m:
            continue
        moji, url = m.group(1).strip(), m.group(2)
        p = urllib.parse.urlparse(url)
        kagi = (p.scheme, p.netloc, p.path.rstrip("/"))
        if kagi in mita:
            continue
        mita.add(kagi)
        de.append((moji, url))
    # **規約で止まった相手には行かない**（統括・2026-09-21・九電）。
    # **robots が許可でも通さない。** 関所が別（正本9節）。
    #
    # **落としたことは黙らない。** 下の `tometa()` が同じ道で数える
    return [(m, u) for m, u in de
            if yakusoku_no_kekka(u)["kekka"] != "取ってはいけない"]


def tometa(michi: Path = None):
    """**規約で止めた相手。** 0本になった理由を、記録に書くために要る。

    **「行き先0本」と「規約で止まった」は別**（9節）。
    前者は探し方の話、後者は**許可を取るまで変わらない。**
    """
    michi = michi or RECON
    if not michi.exists():
        return []
    de = []
    tsukau = False
    for gyou in michi.read_text(encoding="utf-8").splitlines():
        if "記録らしいリンク" in gyou:
            tsukau = True
            continue
        if "速報らしいリンク" in gyou or gyou.startswith("###"):
            tsukau = False
        if not tsukau:
            continue
        m = GYOU.match(gyou)
        if not m:
            continue
        ya = yakusoku_no_kekka(m.group(2))
        if ya["kekka"] == "取ってはいけない":
            de.append({"url": m.group(2), **ya})
    return de


def ikisaki(michi: Path = None):
    """**この回で出て行く先。** 見張りがここを呼ぶ。

    `chien_get.py` と同じ約束——**URL の一覧を返す。**
    見張りは「同じ相手に1日2回行かないか」をここで数えるので、
    **本番と同じ `yomu()` を通す。** ここが増えれば見張りも増える。

    2026-09-21、ここを (文字, URL) の組で返していて、**見張りが落ちた。**
    **約束が1つなら、合わせる。**
    """
    michi = michi or RECON
    return [u for _moji, u in yomu(michi)]


HIDUKE = re.compile(r"\*\*(\d{4}-\d{2}-\d{2})\*\* に `teiden_recon\.py` が走った")


def ichidanme_no_hi(michi: Path = None):
    """1段目が最後に走った日。**記録そのものから読む。**

    別に台帳を作らない。**同じ事実を2か所に置くと、片方が古くなる。**
    """
    michi = michi or RECON
    if not michi.exists():
        return ""
    m = HIDUKE.search(michi.read_text(encoding="utf-8"))
    return m.group(1) if m else ""


def yubiwa(raw: bytes) -> str:
    """指紋。**長さだけ見ない**——同じ長さで中身が変わることがある。"""
    return hashlib.sha256(raw).hexdigest()


def daicho_yomu():
    if DAICHO.exists():
        return json.loads(DAICHO.read_text(encoding="utf-8"))
    return {}


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
        return r.status, r.read()


def kurabe(mae: list, ima: str) -> str:
    """前に見たときと、今日の指紋を比べる。**分かるのはここまで。**

    **どう変わったかは、ここでは言わない。** 生のバイトが両方あるので、後で見る。
    """
    if not mae:
        return "はじめて見た"
    zen = [x for x in mae if x.get("yubiwa")]
    if not zen:
        return "前は取れていなかった"
    if zen[-1]["yubiwa"] == ima:
        return "同じ"
    return "**差し替わった**"


def hitotsu(moji: str, url: str, hiduke: str, daicho: dict):
    """1つ取る。**robots を先に見る。確かめられなければ行かない**（3.4）。"""
    ato = daicho.setdefault(url, {"moji": moji, "mita": []})
    d = {"mita_hi": hiduke, "yubiwa": None, "bytes": None,
         # **保存の状態と公開の状態は別**（9節）。この段は保存しか触らない
         "hozon": None, "koukai": "出していない", "naze": ""}
    ok, naze = check_robots(url)
    if not ok:
        d["hozon"] = "取れなかった"
        d["naze"] = f"robots（{naze}）。**取りに行かない**"
        ato["mita"].append(d)
        return d, "robots で行かなかった"
    time.sleep(WAIT)
    try:
        st, raw = get(url)
    except Konde:
        raise  # **混んでいると言われたら、その回は止める**
    except Exception as e:
        d["hozon"] = "取れなかった"
        d["naze"] = type(e).__name__
        ato["mita"].append(d)
        return d, "取れなかった"
    if st != 200:
        d["hozon"] = "取れなかった"
        d["naze"] = f"HTTP {st}"
        ato["mita"].append(d)
        return d, f"HTTP {st}"

    y = yubiwa(raw)
    doudatta = kurabe(ato["mita"], y)
    d["yubiwa"] = y
    d["bytes"] = len(raw)
    d["hozon"] = "取った"
    ato["mita"].append(d)

    saki = INBOX / hiduke
    saki.mkdir(parents=True, exist_ok=True)
    p = urllib.parse.urlparse(url)
    na = re.sub(r"[^a-z0-9.]+", "_", (p.netloc + p.path).lower())[:80] + ".html"
    (saki / na).write_bytes(raw)
    return d, doudatta


def houkoku(kekka, hiduke, daicho) -> str:
    L = []
    a = L.append
    a("# 停電の記録を毎日ためた記録")
    a("")
    a(f"**{hiduke}** に `teiden_get.py` が走った。**読み取っていない。**")
    a("**生のバイトは `inbox/`（`.gitignore`）。公開側には1バイトも入れていない。**")
    a("")
    a(f"    行き先   {len(kekka)} 本（1段目の記録から読んだ。**こちらで足していない**）")
    a("")
    tome = tometa()
    if tome:
        a("## 規約で止まっている相手")
        a("")
        a("**行き先が減っているのは、探し方の話ではない。**")
        a("**robots が許可でも、規約が断っていれば通さない**（関所が別・正本9節）。")
        a("")
        for x in tome:
            a(f"**{x.get('mei') or x['url']}**"
              f"（{x.get('mita_hi') or '日付なし'}）")
            a("")
            a(f"    robots  {x.get('robots') or '—'}  ← **こちらは通っている**")
            a(f"    規約    **{x['kekka']}**")
            if x.get("url"):
                a(f"    在りか  {x['url']}")
            a("")
            a(f"> {x.get('riyuu') or '理由が書かれていない'}")
            a("")
        a("**この経路が使えないとは書かない。** 止めたのは**この相手だけ**。")
        a("**許可を取るか、別条件の取得手段が確認できれば変わる。**")
        a("")
    a("## 今日どうだったか")
    a("")
    for moji, url, d, doudatta in kekka:
        a(f"### {moji or url}")
        a("")
        a(f"    行き先   {url}")
        a(f"    保存     {d['hozon']}")
        a(f"    公開     {d['koukai']}  ← **まだ何も決めていない**")
        if d["naze"]:
            a(f"    わけ     {d['naze']}")
        if d["yubiwa"]:
            a(f"    指紋     {d['yubiwa'][:16]}…  （{d['bytes']} バイト）")
        a(f"    前と     **{doudatta}**")
        mita = daicho.get(url, {}).get("mita", [])
        if len(mita) >= 2:
            a(f"    見た回数  {len(mita)} 回（{mita[0]['mita_hi']} 〜 {mita[-1]['mita_hi']}）")
        a("")
    a("---")
    a("")
    a("## 読むときの線")
    a("")
    a("**「差し替わった」は、区間でしか言えない。**")
    a("前に見た日と今日のあいだ、のどこかで変わった。**毎日1回しか見ていない。**")
    a("")
    a("**毎日「差し替わった」が出るページは、指紋が効かない。**")
    a("「最終更新 ◯時◯分」のような表示があると、**中身が同じでも指紋が変わる。**")
    a("**毎日鳴るのは「毎日変わった」ではない。** そのページは別の手が要る。")
    a("")
    a("**どう変わったかは、ここには書かない。** 生のバイトが両方あるので、後で見る。")
    a("**取得は取り返せない。読み取りは取り返せる。**")
    return "\n".join(L) + "\n"


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=0, help="行き先の数（0=全部）")
    a = p.parse_args(argv)

    saki = yomu()
    if not saki:
        # **0本として緑で終わらない**（9節）
        print("行き先が1本も読めなかった。**「無い」ではなく「読めなかった」**",
              file=sys.stderr)
        print(f"  1段目の記録: {RECON}", file=sys.stderr)
        print("  先に `teiden_recon.py --fukasa 2` を走らせて、"
              "**記録らしいリンク**を見つける。", file=sys.stderr)
        return 2

    hiduke = today()
    ichi = ichidanme_no_hi()
    if ichi and ichi == hiduke:
        # **同じ相手に1日2回行かない**（3.4）。**黙って飛ばさない**
        print(f"1段目が今日（{hiduke}）走っている。**同じ相手に1日2回行かないので、"
              "この回は止める**", file=sys.stderr)
        return 3

    daicho = daicho_yomu()
    kekka = []
    for moji, url in (saki[: a.limit] if a.limit else saki):
        d, doudatta = hitotsu(moji, url, hiduke, daicho)
        kekka.append((moji, url, d, doudatta))

    DAICHO.write_text(json.dumps(daicho, ensure_ascii=False, indent=1),
                      encoding="utf-8")
    KIROKU.write_text(houkoku(kekka, hiduke, daicho), encoding="utf-8")
    kawatta = sum(1 for *_x, d in kekka if "差し替わった" in d)
    print(f"行き先 {len(kekka)} / 差し替わった {kawatta}")
    print(f"  {KIROKU}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
