#!/usr/bin/env python3
"""フロアマップを**ためる**段。**読み取らない。**

返ってきたバイトをそのまま置いて、**指紋を取って前と比べる**だけ。
何の店が入っているかを読むのは別の段（`floor_kumu.py`）。

## 取りに行く前に、2つとも立っていること

    ① robots.txt が許可   **この段が毎回見る**（関所の記録を信じない。日が違う）
    ② `yakusoku.kekka` が「取ってよい」  **人が利用規約を読んで決めた結果**

**②が「未確認」でも「規約未確定」でも「取ってはいけない」でも取りに行かない。**
robots は機械が読めるが、規約は読めない。空のまま進めると、
**誰も読んでいないものを「確かめた」と名乗ることになる**（ルール⑥）。

**「未確認」と「規約未確定」と「取ってはいけない」を、同じ顔にしない。**

    未確認      **読んでいない。** 調べれば動く
    規約未確定  **読んだが、拒否とも許可とも決まらなかった。** 読み直しても動かない
    取ってはいけない **読んで、禁じていると分かった**

2026-09-21、1件目（阪急西宮ガーデンズ）のサイトポリシーが
**「許可無く無断で複製・二次利用などする事はできません」**と書いていた。
**robots は関係ない。** 2026-09-24 にこの施設の欄を「規約未確定」へ戻し、
**取得を止めた**（理由は関所 `floor_kanmon.py` の欄に残してある）。
止めるのはこの段の入口の判定（下の `hitotsu()`）1か所。

## 1日1回。**同じ相手に1日2回行かない**

台帳にその日の記録があれば、その施設は飛ばす（戻り値ではなく、記録で決める）。

## 「変わっていない」と「2回見ていない」を分ける

指紋（sha256）を毎回取って、前の指紋と比べる。

    はじめて       前が無い。**「変わっていない」ではない**
    変わっていない 前と同じ指紋
    **変わった**   前と違う指紋。**ここが2時点目**

**長さで代用しない。** 1文字だけ差し替わったときに、長さは同じまま通る。

## **観測が完全だったか**を、この段が言う（差分の段は推測しない）

2026-09-21、差分検出器を人工データで壊して分かった——
**いちばん怖いのは「途中で切れた回を大量退店と読むこと」。**
一度そう書くと**あとから直せない**（次の回で入店に化けて、履歴が二重に壊れる）。

**差分の段は推測しない。** 取得の層が知っていることを、そのまま渡す。

    todoita     転送が最後まで来たか
    owari       文書の終わりの印（`</html>`）が在るか
    moto_kensuu 原典が自分で「全◯件」と言っているか（**無ければ None**）

**⚠ この印で捕まらないものがある。**
**相手が「完全なつもりで途中までの中身」を200で返す**場合は、
転送も長さも終わりの印も正しい。**そこは差分の段の二の矢が見る**
（消えた店が並びの末尾に固まっているか）。**役割が違う。**

## 保存の状態と、公開の状態を、別の欄に

    hozon    こちらが残せたか（金庫に入った／成果物どまり／入らなかった）
    koukai   **原典でまだ見えるか**（200 で返った／404 で消えた／確かめられなかった）

**保存することと、公開され続けていることは同義ではない。**
こちらに残っていても、向こうから消えていることがある。逆もある。

## 消えたときに、**撤回と決めつけない**

404 になっても、名乗りは「**原典で見つけられなくなった**」まで。
模様替えでURLが変わっただけのことがある。**理由はこの段では分からない。**
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common.fetch import (  # noqa: E402
    Konde, TIMEOUT, UA, WAIT, check_robots, decode_html, is_busy,
)
from common.runday import today  # noqa: E402
from floor_kanmon import (  # noqa: E402  **一覧も語も関所が正本。2か所に書かない**
    KEKKA, KOUHO, UNEI_YAKUSOKU,
)

# 生のバイトは `inbox/`（`.gitignore`）。巡回中はここが金庫への symlink になる
INBOX = HERE / "inbox" / "floor"
# 台帳と記録。**指紋と日付だけ。店の名前は1つも入らない**
DAICHO = HERE / "data" / "ref" / "floor-ledger.json"
KIROKU = HERE / "data" / "ref" / "floor-get.md"


def _ima() -> str:
    """取った時刻。**あとから観測の有効性を確かめるために要る**（統括・2026-09-21）。

    **日付だけでは足りない。** 同じ日に2回走った回を、あとから分けられない。
    """
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec="seconds")


def yubiwa(b: bytes) -> str:
    """指紋。**長さで代用しない。**"""
    return hashlib.sha256(b).hexdigest()


def ikisaki(k: dict = None):
    """見に行くURLの一覧。**URLの一覧を返す**（他の段と同じ約束）。

    `k` を渡せばその施設の分、渡さなければ**全部**。
    **引数なしで呼べる形にしておく。** 「1日に2回以上取りに行かないか」の見張りが、
    どの段に対しても `ikisaki()` と呼んで相手のホストを数える
    （**目でURLを拾うと、説明文に書いたリンクまで行き先に数えてしまう**）。

    いまは1施設1枚。**階ごとに分かれている相手でも、まず1枚だけ。**
    枚数を増やすのは、1枚目で抽出が使えると分かってから（2026-09-21）。
    """
    if k is not None:
        return [k["chizu"]]
    return [x["chizu"] for x in KOUHO]


def daicho_yomu():
    if DAICHO.exists():
        return json.loads(DAICHO.read_text(encoding="utf-8"))
    return {"shisetsu": {}}


def kyou_mita(dai, sid, hiduke):
    """今日すでに見たか。**戻り値ではなく記録で決める**（同じ相手に1日2回行かない）。"""
    for r in dai["shisetsu"].get(sid, {}).get("kiroku", []):
        if r.get("hi") == hiduke:
            return True
    return False


# **原典が自分で「全◯件」と言っている形。** 見つからなければ **None**
KENSUU = re.compile(r"(?:全|計|合計)?\s*([0-9０-９]{1,4})\s*"
                    r"(?:件|店舗|ショップ|SHOPS?|shops?)(?:中|を掲載)?")
# **文書の終わりの印。** 途中で切れていれば、これが無い
OWARI = re.compile(rb"</html\s*>\s*\Z", re.I)
# **ページ送り。** 2枚目が在るなら、**この1枚は全部ではない**
PAGER = re.compile(r"[?&]page=(\d{1,4})")


# **印の作り方の版。** 作り方を変えたら上げる。
# **古い記録を、新しい作り方で読んだつもりにならない**ため（あとから検証できる形）
INSHI_VERSION = "kansei-3"


def hosho(na, kekka, suru, shinai):
    """**1つの印が、何を保証して、何を保証しないか。**

    2026-09-21、統括の指示——
    「`</html>` があるから絶対完全」「Content-Length が一致したから絶対完全」
    のように**1条件だけで断定しない。**

    **印ごとに、言えることと言えないことを並べて残す。**
    """
    return {"na": na, "kekka": kekka, "保証する": suru, "保証しない": shinai}


def kansei_no_shirushi(raw: bytes, atama, kireta: bool,
                       base: str = "", jikoku: str = ""):
    """**観測が完全だったかの印。** 差分の段はこれを受け取る（推測しない）。

    ここで決めるのは3つだけ。**「分からない」を「大丈夫」に倒さない。**

        todoita     転送が最後まで来たか
        owari       文書の終わりの印が在るか
        moto_kensuu 原典が自分で「全◯件」と言っているか（**無ければ None**）

    ## todoita の決め方

    **読み切れずに切れたら、例外が出る**（`IncompleteRead` など）。
    出なかったこと自体が、まず1つの証拠。

    そのうえで、**`Content-Length` が在って中身と合っているか**を見る。
    **圧縮されている回は比べられない**（ヘッダは圧縮後の長さなので）。
    比べられない回は **None**——**「分からない」であって「大丈夫」ではない。**

    ## ⚠ この印で捕まらないもの

    **相手が「完全なつもりで途中までの中身」を200で返す**場合。
    転送は正しく終わり、`Content-Length` も合い、`</html>` も在る。
    **ここは捕まえられない。** そちらは差分の段の二の矢
    （消えた店が並びの末尾に固まっているか）が見る。**役割が違う。**
    """
    atama = atama or {}
    moto_ji = jikoku or _ima()
    kihon = {"parser": INSHI_VERSION, "totta_nichiji": moto_ji,
             "status": None,
             "etag": atama.get("ETag", ""),
             "last_modified": atama.get("Last-Modified", ""),
             "raw_hash": yubiwa(raw) if raw else "",
             "bytes": len(raw) if raw else 0,
             # **この段は読み取らない。** 数えたのは「形の繰り返し」であって、
             # 店の数ではない。**別の欄で持つ**（混ぜると読んだことになる）
             "parsed_count": None,
             "katachi_kazu": None}

    if kireta or raw is None:
        return dict(kihon, todoita=False, owari=False, moto_kensuu=None,
                    wake="読んでいる途中で切れた",
                    hosho=[hosho("読み切れたか", False,
                                 "**途中で切れたことは確か**",
                                 "どこまで届いたかは分からない")])

    todoita, wake = True, ""
    naga = (atama or {}).get("Content-Length") if atama else None
    atsu = (atama or {}).get("Content-Encoding") if atama else None
    if naga is not None and not atsu:
        try:
            if int(naga) != len(raw):
                todoita = False
                wake = f"Content-Length {int(naga):,} と中身 {len(raw):,} が違う"
        except (TypeError, ValueError):
            todoita = None
            wake = "Content-Length が数として読めない（**分からない**）"
    elif naga is None:
        todoita = None
        wake = "Content-Length が無いので比べられない（**分からない**）"
    elif atsu:
        todoita = None
        wake = f"圧縮されている（{atsu}）ので長さを比べられない（**分からない**）"

    owari = bool(OWARI.search(raw))

    # **原典が自分で言っている件数。** 見つからなければ None（**作らない**）
    #
    # **文字コードは決め打ちしない**（正本・`decode_html` を通す）。
    # 決め打ちすると、**読めなかっただけの回が「件数が無い」に化ける。**
    moto, pager = None, None
    try:
        honbun, _m = decode_html(raw, (atama or {}).get("Content-Type", ""))
        # **タグを落としてから探す。**
        # 2026-09-21、`検索結果<span>314</span>件` を取りこぼした。
        # **数字と単位の間にタグが入る**と、タグ込みの本文では当たらない。
        # **そのせいで「原典は314件」を見落とし、32件しか無い回を
        # 「分からない」で止めていた。** たまたま安全側に倒れただけだった
        hira = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", honbun))
        m = KENSUU.search(hira)
        if m:
            moto = int(unicodedata.normalize("NFKC", m.group(1)))
        # **ページ送りが見えたら、この1枚は全部ではない**
        ps = [int(x) for x in PAGER.findall(honbun)]
        pager = max(ps) if ps else None
    except (ValueError, UnicodeError, LookupError):
        moto, pager = None, None

    # **形の繰り返しの数。** 読み取りではない（店名は1つも持ち帰らない）
    katachi = None
    try:
        from tenant_recon import shitami        # **形の測り方は1か所**
        s = shitami(base or "https://example.invalid/",
                    raw, atama.get("Content-Type", ""))
        katachi = (s.get("kotei_url") or {}).get("kazu")
    except Exception:                                            # noqa: BLE001
        katachi = None

    # **印ごとに、言えることと言えないことを並べる**（統括・2026-09-21）
    ha = [
        hosho("転送が最後まで来たか（Content-Length）", todoita,
              "**相手が申告したバイト数と、受け取ったバイト数が同じ**",
              "**相手の申告そのものが途中までだった場合は分からない**／"
              "圧縮されている回は比べていない／ヘッダが無い回も比べていない"),
        hosho("文書の終わりの印（</html>）", owari,
              "**文書の末尾が届いている**",
              "**途中の要素が欠けていても末尾は在りうる**／"
              "JS で後から足す作りでは意味が薄い／HTML 以外では意味を持たない"),
        hosho("原典が言っている件数", moto is not None,
              "**原典の申告と、こちらが数えた数を突き合わせられる**"
              if moto is not None else "—",
              "**言っていなければ None。**言っている数が正しいとも限らない"),
        hosho("指紋（sha256）", bool(raw),
              "**同じバイトかどうかが言える**",
              "**完全かどうかは言えない**（途中までのバイトにも指紋は付く）"),
        hosho("ページ送りが無いか", pager in (None, 1),
              "**2枚目が見えなければ、この1枚で終わっている見込み**",
              "**ページ送りが JS で作られていれば見えない**／"
              "**1枚目に2枚目へのリンクが無い作りもある**"),
    ]
    if pager and pager > 1:
        wake = (wake + "／" if wake else "") + \
            f"**ページ送りが {pager} 枚ぶん見えている。この1枚は全部ではない**"
    return dict(kihon, todoita=todoita, owari=owari, moto_kensuu=moto,
                pager=pager, katachi_kazu=katachi, wake=wake, hosho=ha)


def get(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ja",
    })
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            atama = dict(r.headers)
            try:
                raw = r.read()
            except Exception as e:                               # noqa: BLE001
                # **読んでいる途中で切れた。** ここが捕まえたい形
                sh = kansei_no_shirushi(None, atama, True, base=url)
                sh["status"] = r.status
                return (r.status, b"", f"途中で切れた {type(e).__name__}: {e}", sh)
            sh = kansei_no_shirushi(raw, atama, False, base=url)
            sh["status"] = r.status
            return r.status, raw, "", sh
    except urllib.error.HTTPError as e:
        if is_busy(e):
            raise Konde(f"相手が混んでいると言っている（HTTP {e.code}）") from e
        if e.code in (404, 410):
            # **消えた。理由は分からない。** 模様替えでURLが変わっただけのことがある
            return e.code, b"", "原典で見つけられなくなった", None
        return e.code, b"", f"HTTP {e.code}", None
    except Konde:
        raise
    except Exception as e:
        return 0, b"", f"届かなかった {type(e).__name__}: {e}", None


def hitotsu(k: dict, dai: dict, hiduke: str):
    """1施設ぶん。**関所が2つとも立っていなければ取りに行かない。**"""
    sid = k["id"]
    d = {"id": sid, "mei": k["mei"], "unei": k.get("unei", ""), "hi": hiduke}

    ya = k.get("yakusoku") or {}
    kekka = ya.get("kekka", "未確認")
    if kekka != "取ってよい":
        d["kekka"] = "見送り"
        d["yakusoku"] = kekka
        if kekka == "取ってはいけない":
            # **相手が禁じている。** robots が許可でも通さない。
            # **「未確認」と同じ顔にしない**——こちらは許可を取るまで変わらない
            d["riyuu"] = f"利用規約で**禁じられている**：{ya.get('riyuu') or '（理由が書かれていない）'}"
        elif kekka == "規約未確定":
            # **読んだ。そのうえで決まらなかった。**
            # 「まだ読んでいない」とも「禁じられている」とも書かない（ルール⑥）
            d["riyuu"] = ("**人が読んだが、拒否とも許可とも決まらなかった**（規約未確定）："
                          f"{ya.get('riyuu') or '（理由が書かれていない）'}")
        else:
            d["riyuu"] = "利用規約をまだ人が読んでいない。**人が決めるまで取りに行かない**"
        return d
    if not ya.get("mita_hi"):
        d["kekka"] = "見送り"
        d["riyuu"] = "「取ってよい」と書いてあるのに、**読んだ日が入っていない**。いつの判断か分からない"
        return d
    if kyou_mita(dai, sid, hiduke):
        d["kekka"] = "見送り"
        d["riyuu"] = "今日はもう見た（同じ相手に1日2回行かない）"
        return d

    for url in ikisaki(k):
        ok, why = check_robots(url)
        if ok is not True:
            d["kekka"] = "見送り"
            d["riyuu"] = f"robots が{'拒否' if ok is False else '分からない'}：{why}"
            return d

        time.sleep(WAIT)
        try:
            status, raw, note, shirushi = get(url)
        except Konde as e:
            d["kekka"] = "見送り"
            d["riyuu"] = f"{e}。その回は中止"
            return d

        # **公開の状態。** こちらに残っているかとは別の欄
        if status == 200 and raw:
            d["koukai"] = "原典で見えた"
        elif status in (404, 410):
            d["koukai"] = "原典で見つけられなくなった（**撤回とは限らない**）"
        else:
            d["koukai"] = f"確かめられなかった（{note or status}）"

        # **観測が完全だったかの印。** 差分の段がここを受け取る（推測しない）。
        # **「分からない」を「大丈夫」に倒さない**（3.4・既定は止まる側）
        d["kansei"] = shirushi
        # **1条件で決めない。** どれか1つでも「完全でない／分からない」なら倒す。
        # **ページ送りが見えたら、その1枚では全部ではない**（2026-09-21）
        d["kansoku"] = (bool(shirushi)
                        and shirushi.get("todoita") is True
                        and shirushi.get("owari") is True
                        and shirushi.get("pager") in (None, 1))

        if not raw:
            d["kekka"] = "取れなかった"
            d["hozon"] = "残っていない"
            d["riyuu"] = note or f"HTTP {status}"
            return d

        yu = yubiwa(raw)
        d["moto_url"] = url
        mae = dai["shisetsu"].get(sid, {}).get("kiroku", [])
        # **観測元が変わったら、前の回は比べる相手ではない**（2026-09-21）。
        #
        # 統括の判断で、観測元をショップガイドからフロアのページに替えた。
        # **台帳は施設ごとなので、そのままだと別のページ同士を比べる。**
        # 指紋は当然ちがうので「**変わった**」と出る。**中身は無関係なのに。**
        #
        # **大量退店・全部入店と同じ家族の事故。** 比べる相手が無いときは、
        # **無いと書く**（正本9節「比べる相手が無い回は未判定」）
        onaji = [r for r in mae if (r.get("moto_url") or "") == url]
        maeno = onaji[-1].get("yubiwa") if onaji else None
        if maeno is None:
            d["henka"] = ("はじめて（**観測元が変わった**）"
                          if mae else "はじめて")   # **「変わっていない」ではない**
        elif maeno == yu:
            d["henka"] = "変わっていない"
        else:
            d["henka"] = "**変わった**"      # ここが2時点目

        saki = INBOX / sid
        saki.mkdir(parents=True, exist_ok=True)
        (saki / f"{hiduke}.html").write_bytes(raw)
        d.update({"kekka": "取れた", "yubiwa": yu, "bytes": len(raw),
                  "hozon": "inbox に置いた（金庫がある回は金庫）", "url": url})
    return d


def daicho_kaku(dai, kekka, hiduke):
    for d in kekka:
        if d.get("kekka") != "取れた":
            continue
        s = dai["shisetsu"].setdefault(d["id"], {"mei": d["mei"], "unei": d["unei"],
                                                 "kiroku": []})
        # **観測が完全だったかの印も一緒に残す。**
        # 差分の段が読むのはこちら。**あとから作れない**ので、取った回に書く
        s["kiroku"].append({"hi": hiduke, "moto_url": d.get("moto_url", ""),
                            "yubiwa": d["yubiwa"], "bytes": d["bytes"],
                            "hozon": d["hozon"], "koukai": d["koukai"],
                            "henka": d["henka"],
                            "kansoku": d.get("kansoku"),
                            "kansei": d.get("kansei")})
    dai["generated_at"] = hiduke
    return dai


def houkoku(dai, kekka, hiduke):
    a = [].append
    a("# フロアマップをためた記録")
    a("")
    a(f"{hiduke} に走らせた。**入るのは指紋と日付だけ。店の名前は1つも入らない。**")
    a("")
    a("| 施設 | 運営 | 結果 | **観測** | 前と比べて | 原典 | 理由 |")
    a("|---|---|---|---|---|---|---|")
    for d in kekka:
        ka = d.get("kansei") or {}
        kan = ("—" if d.get("kansoku") is None
               else ("**完全**" if d.get("kansoku")
                     else f"**完全と言えない**（{ka.get('wake') or '印が無い'}）"))
        a(f"| {d['mei']} | {d.get('unei') or '—'} | {d['kekka']} | {kan} "
          f"| {d.get('henka') or '—'} | {d.get('koukai') or '—'} | {d.get('riyuu') or ''} |")
    a("")
    tore = sum(1 for d in kekka if d["kekka"] == "取れた")
    kawa = sum(1 for d in kekka if d.get("henka") == "**変わった**")
    kan_ok = sum(1 for d in kekka if d.get("kansoku"))
    a(f"取れた {tore} / 全 {len(kekka)}。**変わった {kawa}**"
      f"。**観測が完全だと言えた {kan_ok}**")
    a("")
    a("**「取れた」と「完全に取れた」は別**（処理成功と観測成功）。")
    a("**完全だと言えない回の差分は、出さない**（`floor_sabun.py` が止める）。")
    a("**⚠ この印で捕まらないものがある**——相手が「完全なつもりで途中までの")
    a("中身」を200で返す場合。そこは差分の段の二の矢が見る。")
    a("")
    a("**「変わっていない」と「2回見ていない」は同じ顔で出る。**")
    a("下の表は、施設ごとに**何回見たか**。1回しか見ていない施設で差分は測れない。")
    a("")
    a("| 施設 | 見た回数 | はじめて見た日 | 最後に見た日 | 変わった回数 |")
    a("|---|---|---|---|---|")
    for sid, s in sorted(dai["shisetsu"].items()):
        ki = s["kiroku"]
        n = sum(1 for r in ki if r.get("henka") == "**変わった**")
        a(f"| {s['mei']} | {len(ki)} | {ki[0]['hi']} | {ki[-1]['hi']} | {n} |")
    a("")
    import collections
    kazu = collections.Counter((k.get("yakusoku") or {}).get("kekka", "未確認")
                               for k in KOUHO)
    a("**利用規約の読み具合。**「未確認」「規約未確定」「取ってはいけない」を分けて数える")
    a("——**読んでいない**のか、**読んでも決まらなかった**のか、**禁じられている**のかで、")
    a("次にやることが違う。混ぜると「あと何件で頭打ちか」が分からなくなる。")
    a("")
    for na in KEKKA:
        mei = [k["mei"] for k in KOUHO
               if (k.get("yakusoku") or {}).get("kekka", "未確認") == na]
        a(f"- **{na} {kazu[na]}**" + ("：" + "、".join(mei) if mei else ""))
    a("")
    if UNEI_YAKUSOKU:
        a("**運営会社の側の規約**（2026-09-21 に欄を分けた）")
        a("")
        a("**施設の規約の代わりにしない。** 施設が自分で断っていれば、そちらが効く。")
        a("**運営会社が「規約未確定」でも、施設の欄は動かない。** 逆も同じ。")
        a("")
        a("| 運営 | 相手 | 読んだ日 | 結果 | 在りか |")
        a("|---|---|---|---|---|")
        for u in UNEI_YAKUSOKU:
            arika = f"[規約]({u['url']})" if u.get("url") else "—"
            a(f"| {u['unei']} | {u['mei']} | {u.get('mita_hi') or '—'} "
              f"| **{u['kekka']}** | {arika} |")
        a("")
        for u in UNEI_YAKUSOKU:
            a(f"**{u['mei']}**（{u.get('mita_hi') or '日付なし'}）")
            a("")
            a(f"> {u.get('riyuu') or '理由が書かれていない'}")
            a("")

    for k in KOUHO:
        ya = k.get("yakusoku") or {}
        if ya.get("kekka") == "取ってはいけない":
            a(f"**{k['mei']}**（{ya.get('mita_hi') or '日付なし'}・{ya.get('url') or ''}）")
            a("")
            a(f"> {ya.get('riyuu') or '理由が書かれていない'}")
            a("")
    return "\n".join(a.__self__)


def main(argv=None):
    p = argparse.ArgumentParser(description="フロアマップをためる。読み取らない")
    p.add_argument("--limit", type=int, default=0, help="上から何件だけ見るか（0=全部）")
    p.add_argument("--id", help="この施設だけ")
    a = p.parse_args(argv)

    kouho = [k for k in KOUHO if not a.id or k["id"] == a.id]
    if a.id and not kouho:
        print(f"そんな id は無い: {a.id}", file=sys.stderr)
        return 2
    if a.limit:
        kouho = kouho[:a.limit]

    hiduke = today()
    dai = daicho_yomu()
    kekka = []
    for i, k in enumerate(kouho):
        if i:
            time.sleep(WAIT)
        d = hitotsu(k, dai, hiduke)
        print(f"{d['kekka']:　<6} {d['mei']}  {d.get('henka') or d.get('riyuu') or ''}")
        kekka.append(d)

    dai = daicho_kaku(dai, kekka, hiduke)
    DAICHO.parent.mkdir(parents=True, exist_ok=True)
    DAICHO.write_text(json.dumps(dai, ensure_ascii=False, indent=1), encoding="utf-8")
    KIROKU.write_text(houkoku(dai, kekka, hiduke), encoding="utf-8")
    print(f"\n{KIROKU} に書いた")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
