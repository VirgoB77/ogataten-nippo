#!/usr/bin/env python3
"""保健所の営業許可の一覧を**ためる**段。**読み取らない。**

返ってきたバイトをそのまま金庫に置いて、**指紋を取って前と比べる**だけ。
何が書いてあるかを読むのは別の段（まだ無い）。

## なぜ急ぐか

2026-09-21 に5候補を3軸で並べた（`docs/keikaku.md`）。
**兵庫県だけが「いま取らないと過去が無い」側に立っていた。**

    兵庫県   許可も届出も**ファイル名が固定の1本**。**上書き型の形をしている**
    神戸市   **2021年5月末の全件**と**月次の新規許可**が公式に残っている

**神戸は急がない。兵庫県が急ぐ。**
ただし「毎月20日頃に上書き」は**案出しの調査（2026-09-19）で、こちらは実測していない。**
**この段が2回走って初めて、こちらの実測になる。**

## ⚠️ **営業者氏名の欄がある。** だから金庫が無い回は1バイトも取らない

案出しの調査。個人事業主が多いはず。

**保存の状態と公開の状態を別に持つ**（9節）のは、分けていないと問題が
起きたときに「消すか、出し続けるか」しか選べないから。
**この段が触るのは保存の状態だけ。公開はまだ何も決めていない。**

そして**公開側に落ちる道を、運用の約束ではなくコードで閉じる**（5節）。
`KINKO` が立っていない回は、**取りに行かずに終わる。**
成果物（artifact）に逃がす道も作らない——**90日で消えるうえ、氏名が入っている。**

## 取りに行く前に立っていること

    ① `KINKO=1`            金庫がつながっている。**立っていなければ取らない**
    ② robots.txt が許可     **この段が毎回見る**（探す段の記録を信じない。日が違う）
    ③ 台帳に今日の記録が無い **同じファイルに1日2回行かない**

**②を探す段の結果で代用しない。** robots は日で変わる。

## 行き先は**探す段の台帳**から読む。**こちらで足さない**

`data/ref/hokenjo-recon.json` が正本。**URL を作文しない**（3.4）。
台帳に無い相手には行かない。**「0本」なら、0本のまま終わる。**

2026-09-21、探す段の記録が**入口ごとに残らず上書きされていた。**
1入口だけ回すと、前の回に拾った行き先が消える。**ためる段が読むのはそこ。**
台帳を足して直した。**ここが空なら、まず探す段を回す。**

## 同じホストに、同じ日にもう一度行くことがある

神戸市は**大店立地法の毎朝の巡回と同じホスト**（`www.city.kobe.lg.jp`）。
この段が走る日は、その相手にとって**2回目**になる。

**回数ではなく負荷で見る**（中島さんの指示・2026-09-21）——
「アクセス回数を減らすこと自体を目的化せず、**相手への実負荷を小さくする**」。
この段は**週1回・1ファイルずつ・5秒以上あけて**取る。**総当たりはしない。**

**隠さずに、記録に書く。**

## 条件付きGET。**相手に中身を送らせない回を作る**

2026-09-21 の決定（統括）——**ETag / Last-Modified が使えるなら条件付きGET。
使えなければ従来どおり取る。最終的な変更判定は、従来どおり内容の指紋で行う。**

    こちら  前の回の目印（`If-None-Match` / `If-Modified-Since`）を付けて聞く
    相手    変わっていなければ **HTTP 304**。**中身を送らない**

**304 を「変わっていない」と書かない。** 相手がそう言っただけで、
**こちらは中身を1バイトも持っていない**（9節「処理成功と観測成功と保存成功を
同一視しない」）。記録では**別の欄**に出す。

**相手が目印を返さなければ、条件付きGETは付かない。** 従来どおり取る。

## 入口ごとに、**こちらの見立て**を書いておく

2026-09-21 の決定（統括）——**初回は兵庫県4本＋尼崎2本。
兵庫県は上書き候補、尼崎は挙動未測定として区別する。
2回目以降の実測まで、上書き型とは確定しない。**

    上書き候補         ファイル名が固定。**上書きの形をしている。まだ測っていない**
    挙動未測定         **形からは分からない。** 2回見て初めて分かる
    過去が公式に残る   過去版が別の名前で並んでいる（**実見した**）

**この欄はこちらの見立てであって、相手が言ったことではない**（ルール⑥）。

## 「変わっていない」と「2回見ていない」を分ける

指紋（sha256）を毎回取って、前の指紋と比べる。

    はじめて       前が無い。**「変わっていない」ではない**
    変わっていない 前と同じ指紋
    **変わった**   前と違う指紋。**上書き型かどうかの、こちらの実測はここ**

**長さで代用しない。** 同じ長さで中身が変わる。

## 出すもの

    inbox/hokenjo-get/<日付>/…   生のバイト（**金庫。公開側に1バイトも入れない**）
    data/ref/hokenjo-ledger.json 指紋の台帳（URL・見た日・指紋・大きさ）
    data/ref/hokenjo-get.md      人が読む記録。**中身は1文字も入らない**
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
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

RECON_JSON = HERE / "data" / "ref" / "hokenjo-recon.json"
DAICHO = HERE / "data" / "ref" / "hokenjo-ledger.json"
KIROKU = HERE / "data" / "ref" / "hokenjo-get.md"
INBOX = HERE / "inbox" / "hokenjo-get"

# **金庫が無い回は取らない。** 氏名が入っているため（上の ⚠️）
# **入口ごとの、こちらの見立て。** 相手が言ったことではない（ルール⑥）。
# **2回目以降の実測まで、上書き型とは確定しない**（統括・2026-09-21）
MIKATA = {
    "hyogo-pref": "上書き候補",
    "kobe-city": "過去が公式に残る",
    "amagasaki-city": "挙動未測定",
    "akashi-city": "挙動未測定",
    "himeji-city": "挙動未測定",
    "nishinomiya-city": "挙動未測定",
}

KINKO_NASHI = ("**金庫がつながっていない回は、1バイトも取らない。**"
               "この一覧には**営業者氏名の欄がある**ので、"
               "公開側に落ちる道をコードで閉じてある（5節）")


def yubiwa(b: bytes) -> str:
    """指紋。**長さで代用しない。** 同じ長さで中身が変わる"""
    return hashlib.sha256(b).hexdigest()


def kinko_aruka() -> bool:
    """**金庫がつながっているか。** 立っていなければ、この段は取りに行かない"""
    return os.environ.get("KINKO", "") == "1"


def yomu(michi: Path = None):
    """探す段の台帳から、**行き先だけ**を読む。**こちらで足さない。**

    入口ごとに `file`（一覧そのもののファイル）が並んでいる。
    1段だけ辿った先（`tadotta`）にも `file` があるので、両方見る。

    **同じ URL は1本にまとめる。** クエリだけ違うものは別として扱う
    ——役所のファイルは `?attach=1` のような形で中身が変わることがあるため。
    """
    michi = michi or RECON_JSON
    if not michi.exists():
        return []
    try:
        tane = json.loads(michi.read_text(encoding="utf-8")).get("tane", [])
    except (ValueError, TypeError):
        return []                  # 壊れていたら0本。**黙って進めない**（下で止まる）
    mita, de = set(), []
    for t in tane:
        if not isinstance(t, dict):
            continue
        fa = list(t.get("file") or [])
        for sa in t.get("tadotta") or []:
            fa += list((sa or {}).get("file") or [])
        for f in fa:
            url = (f or {}).get("url") or ""
            if not url.startswith("http") or url in mita:
                continue
            mita.add(url)
            de.append({"tane_id": t.get("id", ""), "tane_mei": t.get("mei", ""),
                       "text": (f.get("text") or "")[:48], "url": url})
    return de


def ikisaki(michi: Path = None):
    """**この回で出て行く先。** 見張りがここを呼ぶ。

    `teiden_get.py` と同じ約束——**URL の一覧を返す。**
    見張りが本番と同じ道を通れるように、**`yomu()` を通す。**
    """
    michi = michi or RECON_JSON
    return [d["url"] for d in yomu(michi)]


def daicho_yomu():
    if DAICHO.exists():
        try:
            return json.loads(DAICHO.read_text(encoding="utf-8"))
        except (ValueError, TypeError):
            pass
    return {"file": {}, "generated_at": ""}


def kyou_mita(dai, url, hiduke) -> bool:
    """**同じファイルに1日2回行かない。** 戻り値ではなく、記録で決める"""
    ki = (dai.get("file", {}).get(url) or {}).get("mita") or []
    return any(r.get("hi") == hiduke for r in ki)


def shirushi(ato):
    """前の回に相手がくれた目印（ETag / Last-Modified）。**無ければ空。**

    **こちらで作らない。** 相手が返したものをそのまま返すのが条件付きGET。
    """
    for r in reversed(ato.get("mita") or []):
        if r.get("etag") or r.get("last_modified"):
            return r.get("etag") or "", r.get("last_modified") or ""
    return "", ""


def get(url, etag="", last_modified=""):
    """1本取る。**目印があれば付ける**（条件付きGET）。

    相手が「変わっていない」と言えば **HTTP 304** が返り、**中身は来ない。**
    そのときは `raw` が `None`。**「変わっていない」と書かない**——
    **こちらは中身を1バイトも持っていない**（9節）。

    相手が目印を返さなければ、次の回も**普通に取る。** それでよい。
    """
    atama = {"User-Agent": UA, "Accept": "*/*", "Accept-Language": "ja"}
    if etag:
        atama["If-None-Match"] = etag
    if last_modified:
        atama["If-Modified-Since"] = last_modified
    req = urllib.request.Request(url, headers=atama)
    try:
        deta = urllib.request.urlopen(req, timeout=TIMEOUT)
    except urllib.error.HTTPError as e:
        if e.code == 304:
            # **相手が「変わっていない」と答えた。** 中身は来ていない
            return 304, "", None, e.headers.get("ETag", ""), e.headers.get(
                "Last-Modified", "")
        if is_busy(e):
            raise Konde(f"相手が混んでいると言っている（HTTP {e.code}）") from e
        raise
    with deta as r:
        return (r.status, r.headers.get("Content-Type", ""), r.read(),
                r.headers.get("ETag", ""), r.headers.get("Last-Modified", ""))


def kurabe(mita, y):
    """前の回と比べる。**「はじめて」を「変わっていない」と書かない。**"""
    mae = [r for r in mita if r.get("yubiwa")]
    if not mae:
        return "はじめて"
    return "変わっていない" if mae[-1]["yubiwa"] == y else "**変わった**"


def hitotsu(f: dict, dai: dict, hiduke: str):
    """1ファイルぶん。**関所が立っていなければ取りに行かない。**"""
    url = f["url"]
    d = {"url": url, "tane_mei": f.get("tane_mei", ""),
         "text": f.get("text", ""), "hi": hiduke,
         "mikata": MIKATA.get(f.get("tane_id", ""), "挙動未測定")}

    if not kinko_aruka():
        d["kekka"], d["riyuu"] = "見送り", KINKO_NASHI
        return d
    if kyou_mita(dai, url, hiduke):
        d["kekka"] = "見送り"
        d["riyuu"] = "今日はもう見た（同じファイルに1日2回行かない）"
        return d

    ok, why = check_robots(url)
    if ok is not True:
        d["kekka"] = "見送り"
        d["riyuu"] = f"robots が{'拒否' if ok is False else '分からない'}：{why}"
        return d

    ato = dai.setdefault("file", {}).setdefault(
        url, {"tane_mei": f.get("tane_mei", ""), "text": f.get("text", ""),
              "mita": []})
    et, lm = shirushi(ato)

    time.sleep(WAIT)
    try:
        status, ctype, raw, et2, lm2 = get(url, et, lm)
    except Konde as e:
        d["kekka"], d["riyuu"] = "見送り", f"{e}。この回は取らない"
        return d
    except Exception as e:                                       # noqa: BLE001
        d["kekka"] = "届かなかった"
        d["riyuu"] = f"{type(e).__name__}: {e}"
        return d

    if raw is None:
        # **相手が「変わっていない」と答えた回。** 中身は来ていない。
        # **こちらの指紋では確かめていない**ので、そう書く（9節）
        ato["mita"].append({"hi": hiduke, "yubiwa": None, "bytes": 0,
                            "status": 304, "ctype": "",
                            "etag": et2 or et, "last_modified": lm2 or lm,
                            "hozon": ""})
        d.update({"kekka": "304", "henka": "相手が「変わっていない」と答えた",
                  "riyuu": "**こちらは中身を1バイトも持っていない**"
                           "（指紋では確かめていない）",
                  "jouken": "効いた"})
        return d

    y = yubiwa(raw)
    saki = INBOX / hiduke
    saki.mkdir(parents=True, exist_ok=True)
    p = urllib.parse.urlsplit(url)
    na = (f.get("tane_id") or "tane") + "-" + os.path.basename(p.path or "file")
    na = "".join(c if c.isalnum() or c in "-._" else "-" for c in na)[:90]
    (saki / na).write_bytes(raw)

    doudatta = kurabe(ato["mita"], y)
    ato["mita"].append({"hi": hiduke, "yubiwa": y, "bytes": len(raw),
                        "status": status, "ctype": ctype, "hozon": na,
                        "etag": et2, "last_modified": lm2})
    d.update({"kekka": "取れた", "yubiwa": y, "bytes": len(raw),
              "henka": doudatta, "hozon": na, "riyuu": "",
              # **次の回に条件付きGETが効くか。** 相手が目印を返したかで決まる
              "jouken": "次は効く" if (et2 or lm2) else "目印が無い（毎回取る）"})
    return d


def houkoku(dai, kekka, hiduke):
    a = [].append
    a("# 保健所の営業許可をためた記録")
    a("")
    a(f"{hiduke} に走らせた。**入るのは指紋と大きさと日付だけ。"
      "一覧の中身は1文字も入らない。**")
    a("")
    a("**⚠️ この一覧には営業者氏名の欄がある**（案出しの調査）。")
    a("生のバイトは**金庫にしか置かない。** 公開側には1バイトも入れない。")
    a("**金庫が無い回は、取りに行かずに終わる**（成果物にも逃がさない）。")
    a("")
    if not kekka:
        a("**この回は行き先が0本だった。**")
        a("")
        a("**「0本」は「無い」ではない。** 探す段の台帳"
          "（`data/ref/hokenjo-recon.json`）が空か、まだ回っていない。")
        a("**まず探す段を回す。**")
        a("")
    else:
        a("| 入口 | 見立て | ファイル | 結果 | 前と比べて | 大きさ "
          "| 指紋（頭） | 条件付きGET | 理由 |")
        a("|---|---|---|---|---|---:|---|---|---|")
        for d in kekka:
            y = (d.get("yubiwa") or "")[:12]
            b = f"{d['bytes']:,}" if d.get("bytes") else "—"
            a(f"| {d.get('tane_mei') or '—'} | {d.get('mikata') or '—'} "
              f"| {d.get('text') or '—'} "
              f"| {d['kekka']} | {d.get('henka') or '—'} | {b} "
              f"| `{y or '—'}` | {d.get('jouken') or '—'} "
              f"| {d.get('riyuu') or ''} |")
        a("")
        toreta = sum(1 for d in kekka if d["kekka"] == "取れた")
        kawatta = sum(1 for d in kekka if d.get("henka") == "**変わった**")
        sanmaru = sum(1 for d in kekka if d["kekka"] == "304")
        a(f"取れた {toreta} / 全 {len(kekka)}。**変わった {kawatta}**"
          f"。相手が「変わっていない」と答えた {sanmaru}")
        a("")
        if sanmaru:
            a("**304 を「変わっていない」と書いていない。**")
            a("相手がそう言っただけで、**こちらは中身を1バイトも持っていない。**")
            a("**処理成功・観測成功・保存成功を同一視しない**（9節）。")
            a("")
        a("**見立ての欄は、こちらの見方であって相手が言ったことではない**"
          "（ルール⑥）。")
        a("**2回目以降の実測まで、上書き型とは確定しない**"
          "（統括・2026-09-21）。")
        a("")

    a("**「変わっていない」と「2回見ていない」は同じ顔で出る。**")
    a("下の表は、ファイルごとに**何回見たか**。1回しか見ていないもので差分は測れない。")
    a("")
    a("| 入口 | ファイル | 見た回数 | はじめて | 最後 | 変わった回数 |")
    a("|---|---|---:|---|---|---:|")
    for url, s in sorted(dai.get("file", {}).items()):
        ki = [r for r in s.get("mita") or [] if r.get("yubiwa")]
        if not ki:
            continue
        n = sum(1 for i, r in enumerate(ki)
                if i and r["yubiwa"] != ki[i - 1]["yubiwa"])
        a(f"| {s.get('tane_mei') or '—'} | {s.get('text') or '—'} | {len(ki)} "
          f"| {ki[0]['hi']} | {ki[-1]['hi']} | {n} |")
    a("")
    a("**上書き型かどうかの、こちらの実測はこの列にある。**")
    a("「毎月20日頃に上書き」は**案出しの調査（2026-09-19）で、こちらは未実測。**")
    a("**2回以上見たファイルが出て、初めてこちらの数になる。**")
    a("")
    a("## 同じホストに、同じ日に行くことがある")
    a("")
    a("神戸市は**大店立地法の毎朝の巡回と同じホスト**。"
      "この段が走る日は、その相手にとって**2回目**になる。")
    a("**回数ではなく負荷で見る**（中島さんの指示・2026-09-21）——"
      "週1回・1ファイルずつ・5秒以上あけて取る。**総当たりはしない。**")
    a("")
    a("## ⚠️ 対象区域の但し書き")
    a("")
    a("兵庫県の一覧は**神戸市・姫路市・尼崎市・明石市・西宮市を除く。**")
    a("**読まずに「兵庫県全部」と名乗らない**（ルール⑥）。")
    a("")
    return "\n".join(a.__self__)


def main(argv=None):
    p = argparse.ArgumentParser(
        description="保健所の営業許可の一覧をためる。読み取らない")
    p.add_argument("--limit", type=int, default=0, help="上から何件（0=全部）")
    p.add_argument("--tane-id", default="",
                   help="この入口だけ（カンマ区切りで複数。例 hyogo-pref,amagasaki-city）")
    a = p.parse_args(argv)

    hiduke = today()
    saki = yomu()
    if a.tane_id:
        # **複数を並べられる。** 初回は兵庫県＋尼崎（統括・2026-09-21）
        hoshii = [x.strip() for x in a.tane_id.split(",") if x.strip()]
        shiranai = [x for x in hoshii if x not in MIKATA]
        if shiranai:
            print(f"知らない入口がある: {', '.join(shiranai)}", file=sys.stderr)
            return 1
        saki = [d for d in saki if d["tane_id"] in hoshii]
    if a.limit:
        saki = saki[:a.limit]

    if not saki:
        print("行き先が0本。**探す段の台帳が空か、まだ回っていない。**")
        print(f"  {RECON_JSON}")

    if not kinko_aruka():
        print("KINKO が立っていない。**この回は1バイトも取らない**"
              "（氏名が入っているため）")

    dai = daicho_yomu()
    kekka = []
    for f in saki:
        d = hitotsu(f, dai, hiduke)
        kekka.append(d)
        print(f"{d['kekka']:6} {d.get('tane_mei','')} {d.get('text','')[:28]}"
              f"  {d.get('henka') or d.get('riyuu') or ''}")

    dai["generated_at"] = hiduke
    DAICHO.parent.mkdir(parents=True, exist_ok=True)
    DAICHO.write_text(json.dumps(dai, ensure_ascii=False, indent=1),
                      encoding="utf-8")
    KIROKU.write_text(houkoku(dai, kekka, hiduke), encoding="utf-8")
    print(f"\n{KIROKU} に書いた")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
