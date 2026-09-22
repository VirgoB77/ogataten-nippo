#!/usr/bin/env python3
"""施設のショップ一覧が**何から作られているか**を、1施設だけ確かめる段。

## なぜこれが要るか

統括の見立て（2026-09-21）——

> SC GATE は全国6,000超のSCについて、各SC Web のショップ一覧・フロアガイドを
> 毎月確認して出退店情報を更新すると公式に説明している。
> **したがって施設 Web からテナント状態を継続把握する方法自体には実運用例がある。**
> ただし**同社の取得方法・許諾関係は不明**なので、**鯨屋の取得可否とは別問題。**

**「他所がやっている」は、こちらが取ってよい理由にならない**（ルール⑥）。
確かめるのは**形だけ**——HTML なのか、公開された構造化データなのか、画像なのか。

## 順番。**規約が先。robots が次。形は最後**

統括の指示どおりに段を切る。**この段だけ、1回見る段より関所が1つ多い。**

    ① 規約が「取ってよい」  **人が読んで決めた結果**。未確認なら、ここで止まる
    ② robots.txt が許可     **この段が毎回見る**（関所の記録を信じない。日が違う）
    ③ 形を測る              **1回だけ。** 店の名前は持ち帰らない

**規約で止まった施設には、二度と行かない**（統括の指示）。
`yakusoku.kekka == "取ってはいけない"` は、この段の候補に**入らない。**

## 分け方は5つ

    静的HTML               落とした後の文字にショップらしい形が残っている
    公開JSON・API          **ページに書かれている** JSON の在りかから作られている
    CMS等の構造化データ    `ld+json` や `__NEXT_DATA__` のような形が在る
    画像                   文字が無く、`img` が並んでいる
    その他                 どれにも当たらない。**「無い」ではない**

## **探しに行かない。作文しない**

**ページに literal で書かれている在りかだけ**を見る。

    ❌ `/api/shops` を組み立てて叩く          **非公開APIの探索**
    ❌ `?page=2` を足して回る                  **大量取得**
    ❌ 401・403 を別の入口で回り込む           **制限回避**
    ✅ ページの中に書いてある `.json` を**1本だけ**開く

**1レスポンスまで**（統括の指示）。**2本目は開かない。**

## 構造だけ持ち帰る。**値は1つも入れない**

    入る    いちばん外側の形、キーの名前、配列の長さ、深さ
    入らない **値。** 店の名前・区画・時間

キーの名前に店名らしい形が混ざっていたら、**そのキーは伏せる。**
**辞書のキーに店名を使う作りが在りうる**ので、形だけ見て素通しにしない。
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
from floor_kanmon import KOUHO  # noqa: E402  **施設の一覧は関所が正本**
from tenant_recon import MISE, SCRIPT, shitami  # noqa: E402  **形の測り方は1か所**

KIROKU = HERE / "data" / "ref" / "shisetsu-kouzou.md"
JSON_SAKI = HERE / "data" / "ref" / "shisetsu-kouzou.json"
INBOX = HERE / "inbox" / "shisetsu-kouzou"

DOKOKARA = ("静的HTML", "公開JSON・API", "CMS等の構造化データ", "画像", "その他")

LDJSON = re.compile(
    r'<script[^>]*type\s*=\s*["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.I | re.S)
# **ページに書かれている JSON の在りか。** 組み立てない
JSONURL = re.compile(r'["\'](/[^"\'\s>]*\.json(?:\?[^"\'\s>]*)?)["\']', re.I)
IMG = re.compile(r"<img\b", re.I)
# CMS などの印。**有無だけ。中身は見ない**
SHIRUSHI = ("__NEXT_DATA__", "__NUXT__", "window.__INITIAL_STATE__",
            "/wp-json/", "wp-content", "Drupal", "Shopify", "microcms")
# **1レスポンスまで**（統括の指示）
MADE = 1


def moji(s):
    t = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    return re.sub(r"\s+", " ", t).strip()


def ikisaki(limit: int = 1):
    """**この回で出て行く先。** 見張りがここを呼ぶ。

    **規約が「取ってよい」の施設だけ。** それ以外はここに出ない
    ——出ないということは、**取りに行かない**ということ。
    """
    return [k["chizu"] for k in erabu()][:max(limit, 0)]


def erabu(shisetsu_id: str = ""):
    """候補。**規約が「取ってよい」の施設だけ。**

    **「取ってはいけない」は入れない**（統括の指示・二度と行かない）。
    **「未確認」も「規約未確定」も入れない**——人が決めるまで行かない。
    """
    de = []
    for k in KOUHO:
        if shisetsu_id and k["id"] != shisetsu_id:
            continue
        if (k.get("yakusoku") or {}).get("kekka") != "取ってよい":
            continue
        de.append(k)
    return de


def get(url, accept="text/html,application/xhtml+xml"):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": accept, "Accept-Language": "ja"})
    try:
        deta = urllib.request.urlopen(req, timeout=TIMEOUT)
    except urllib.error.HTTPError as e:
        if is_busy(e):
            raise Konde(f"相手が混んでいると言っている（HTTP {e.code}）") from e
        raise
    with deta as r:
        return r.status, r.headers.get("Content-Type", ""), r.read()


def kouzou(base, raw, ctype):
    """1枚から、**何から作られていそうか**の材料だけを集める。

    **店の名前は1つも返さない。** 数と、形の名前と、在りかだけ。
    """
    honbun, _m = decode_html(raw, ctype)
    mieru = SCRIPT.sub(" ", honbun)

    kata = []
    for naka in LDJSON.findall(honbun):
        try:
            d = json.loads(naka)
        except (ValueError, TypeError):
            kata.append("（読めなかった）")
            continue
        for x in (d if isinstance(d, list) else [d]):
            if isinstance(x, dict):
                kata.append(str(x.get("@type") or "（@type なし）")[:30])

    shirushi = sorted({s for s in SHIRUSHI if s in honbun})

    # **ページに書いてある在りかだけ。** 同じホストのものに限る
    jibun = urllib.parse.urlsplit(base).netloc
    mita, saki = set(), []
    for michi in JSONURL.findall(honbun):
        u = urllib.parse.urljoin(base, michi)
        if urllib.parse.urlsplit(u).netloc != jibun or u in mita:
            continue
        mita.add(u)
        saki.append(u)

    return {"ldjson_kazu": len(kata), "ldjson_kata": kata[:8],
            "shirushi": shirushi, "json_saki": saki[:5],
            "img_kazu": len(IMG.findall(honbun)),
            "shitami": shitami(base, raw, ctype)}


def dokokara(k):
    """5つに分ける。**「その他」を「無い」と読まない。**

    **強い証拠から順に見る。** 公開された構造化データが在れば、
    HTML に同じものが出ていても、**出どころはそちら**のことが多い。
    """
    s = k["shitami"]
    if k["json_saki"]:
        return "公開JSON・API", "ページに JSON の在りかが書かれている"
    if k["ldjson_kazu"] or k["shirushi"]:
        naka = "、".join(k["ldjson_kata"] or k["shirushi"])
        return "CMS等の構造化データ", f"構造化データの形が在る（{naka}）"
    if s["zenbu_moji"] and s["mieru_moji"] / s["zenbu_moji"] < 0.15:
        return "その他", ("JS を落とすと文字がほとんど残らない。"
                          "**画面は JS が描いている。** 出どころは**未確認**")
    if s["mise_katachi"] >= 10 or (s["kotei_url"] or {}).get("kazu", 0) >= 10:
        return "静的HTML", "落とした後の文字に、店ごとの形が残っている"
    if k["img_kazu"] >= 20 and s["mise_katachi"] < 3:
        return "画像", "文字に店の形が無く、画像が並んでいる"
    return "その他", "どれにも当たらなかった。**「無い」ではない**"


def kagi_wo_fuseru(na):
    """キーの名前に店名らしい形があれば伏せる。**形だけ見て素通しにしない。**"""
    na = str(na)[:24]
    return "（店名らしきキー）" if MISE.search(na) else na


def katachi_dake(x, fukasa=0):
    """**構造だけ**を返す。**値は1つも入れない。**

    入るのは、いちばん外側の形・キーの名前・配列の長さ・深さまで。
    """
    if isinstance(x, dict):
        return {"形": "辞書", "キーの数": len(x),
                "キーの名前": [kagi_wo_fuseru(k) for k in list(x)[:20]],
                "中": katachi_dake(next(iter(x.values())), fukasa + 1)
                if x and fukasa < 2 else None}
    if isinstance(x, list):
        return {"形": "配列", "長さ": len(x),
                "中": katachi_dake(x[0], fukasa + 1) if x and fukasa < 2 else None}
    return {"形": type(x).__name__}


def hitotsu(k, hiduke):
    d = {"id": k["id"], "mei": k["mei"], "unei": k.get("unei", ""),
         "url": k["chizu"], "michi": k.get("michi", "関所の一覧"), "hi": hiduke,
         "yakusoku": (k.get("yakusoku") or {}).get("kekka", "未確認")}

    ok, why = check_robots(k["chizu"])
    d["robots"] = {True: "許可", False: "拒否", None: "分からない"}[ok]
    if ok is not True:
        d["kekka"] = "見送り"
        d["riyuu"] = f"robots が{d['robots']}：{why}"
        return d

    time.sleep(WAIT)
    try:
        _s, ctype, raw = get(k["chizu"])
    except Konde as e:
        d["kekka"], d["riyuu"] = "見送り", f"{e}。この回は開かない"
        return d
    except urllib.error.HTTPError as e:
        # **401・403 を回り込まない**（3.4）。別の入口を探さない
        d["kekka"] = "見送り"
        d["riyuu"] = (f"相手が HTTP {e.code} と答えた。"
                      "**回り込まない。別の入口も探さない**")
        return d
    except Exception as e:                                       # noqa: BLE001
        d["kekka"], d["riyuu"] = "届かなかった", f"{type(e).__name__}: {e}"
        return d

    saki = INBOX / hiduke
    saki.mkdir(parents=True, exist_ok=True)
    (saki / f"{k['id']}.html").write_bytes(raw)

    ka = kouzou(k["chizu"], raw, ctype)
    d["kouzou"] = ka
    d["dokokara"], d["dokokara_riyuu"] = dokokara(ka)
    d["kekka"] = "見た"

    # **1レスポンスまで。** ページに書いてある在りかを1本だけ
    d["json"] = None
    for u in ka["json_saki"][:MADE]:
        time.sleep(WAIT)
        ok2, why2 = check_robots(u)
        if ok2 is not True:
            d["json"] = {"url": u, "kekka": "見送り",
                         "riyuu": f"robots が{'拒否' if ok2 is False else '分からない'}：{why2}"}
            break
        try:
            _s2, ct2, raw2 = get(u, accept="application/json")
        except urllib.error.HTTPError as e:
            d["json"] = {"url": u, "kekka": "見送り",
                         "riyuu": f"相手が HTTP {e.code} と答えた。**回り込まない**"}
            break
        except Exception as e:                                   # noqa: BLE001
            d["json"] = {"url": u, "kekka": "届かなかった",
                         "riyuu": f"{type(e).__name__}: {e}"}
            break
        (saki / f"{k['id']}-1.json").write_bytes(raw2)
        try:
            naka = json.loads(raw2.decode("utf-8", "replace"))
        except (ValueError, TypeError):
            d["json"] = {"url": u, "kekka": "見た",
                         "riyuu": "JSON として読めなかった", "ctype": ct2}
            break
        d["json"] = {"url": u, "kekka": "見た", "ctype": ct2,
                     "bytes": len(raw2), "katachi": katachi_dake(naka)}
        break
    return d


def houkoku(kekka, hiduke):
    a = [].append
    a("# 施設のショップ一覧が、何から作られているか")
    a("")
    a(f"{hiduke} に走らせた。**店の名前は1つも入っていない。**")
    a("入るのは**数と、形の名前と、在りか**だけ。")
    a("")
    a("**関所は3つ。** 規約が「取ってよい」→ robots が許可 → そこで初めて形を見る。")
    a("**規約で止まった施設には行かない**（統括の指示・二度と行かない）。")
    a("")
    a("**「他所がやっている」は、こちらが取ってよい理由にならない。**")
    a("SC GATE が毎月見ていることと、**鯨屋の取得可否は別問題**（統括）。")
    a("")
    if not kekka:
        a("**候補が0件だった。**")
        a("")
        a("**「無い」ではない。** 規約が「取ってよい」になっている施設が"
          "まだ1つも無いというだけ。")
        a("いまの内訳は関所の記録（`data/ref/floor-get.md`）にある。")
        a("**人が規約を読むまで、この段は1枚も開かない。**")
        a("")
        return "\n".join(a.__self__)

    a("| 施設 | 運営 | 規約 | robots | 結果 | **どこから** | 理由 |")
    a("|---|---|---|---|---|---|---|")
    for d in kekka:
        a(f"| {d['mei']} | {d.get('unei') or '—'} | {d['yakusoku']} "
          f"| {d.get('robots','—')} | {d.get('kekka','—')} "
          f"| **{d.get('dokokara') or '—'}** "
          f"| {d.get('dokokara_riyuu') or d.get('riyuu') or ''} |")
    a("")

    for d in kekka:
        ka = d.get("kouzou")
        if not ka:
            continue
        s = ka["shitami"]
        a(f"## {d['mei']}")
        a("")
        a(f"読んだページ：{d['url']}（{d.get('michi') or '関所の一覧'}）")
        a("")
        a("**このページの形**（**中身は入っていない**）")
        a("")
        a(f"- JS を落とす前 {s['zenbu_moji']:,} 文字 → "
          f"落とした後 **{s['mieru_moji']:,} 文字**")
        a(f"- 「◯◯店」の形のリンク {s['mise_katachi']} 本")
        a(f"- 同じ形のリンク {(s['kotei_url'] or {}).get('kazu', 0)} 本")
        a(f"- `img` {ka['img_kazu']} 本")
        a(f"- `ld+json` {ka['ldjson_kazu']} 本"
          + (f"（{'、'.join(ka['ldjson_kata'])}）" if ka["ldjson_kata"] else ""))
        a(f"- 仕組みの印 {'、'.join(ka['shirushi']) if ka['shirushi'] else 'なし'}")
        a(f"- ページに書かれた JSON の在りか **{len(ka['json_saki'])} 本**")
        a("")
        if ka["json_saki"]:
            a("**在りか**（**ページに書いてあったもの。組み立てていない**）")
            a("")
            for u in ka["json_saki"]:
                a(f"  - {u}")
            a("")
        j = d.get("json")
        if j:
            a(f"### 1本だけ開いた：{j['url']}")
            a("")
            a(f"- 結果 {j.get('kekka','—')}"
              + (f"（{j['riyuu']}）" if j.get("riyuu") else ""))
            if j.get("katachi"):
                a(f"- 返ってきた形 {j.get('bytes', 0):,} バイト")
                a("")
                a("```")
                a(json.dumps(j["katachi"], ensure_ascii=False, indent=1))
                a("```")
            a("")
            a("**2本目は開いていない**（1レスポンスまで・統括の指示）。")
            a("**ページ送りもしていない。URL も組み立てていない。**")
            a("")

    a("## この段がやっていないこと")
    a("")
    a("- **店の名前を1つも持ち帰っていない。** 値は構造の中にも入らない")
    a("- **2本目の在りかを開いていない。** ページ送りもしていない")
    a("- **URL を組み立てていない。** 非公開の在りかを探していない")
    a("- **401・403 を回り込んでいない。** 別の入口も探していない")
    a("- **毎日取る許可は、どこにも出ていない。** 1回形を見ただけ")
    a("")
    return "\n".join(a.__self__)


def main(argv=None):
    p = argparse.ArgumentParser(
        description="ショップ一覧が何から作られているかを1施設だけ見る")
    p.add_argument("--id", default="", help="この施設だけ")
    p.add_argument("--limit", type=int, default=1,
                   help="何施設見るか（既定 1。**他施設へ自動的に進まない**）")
    p.add_argument("--url", default="",
                   help="この施設の、別のページを見る（**原典が書いたリンクだけ。"
                        "作文しない**）。`--id` と一緒に使う")
    a = p.parse_args(argv)

    if a.url and not a.id:
        print("--url は --id と一緒に使う。**どの施設の規約で通すかが決まらない**",
              file=sys.stderr)
        return 1

    hiduke = today()
    kouho = erabu(a.id)[:max(a.limit, 0)]
    if a.url:
        # **関所は動かさない。** 見る先が変わるだけ。
        # **規約が「取ってよい」の施設でなければ、そもそも候補に入っていない**
        #
        # **URL は原典が書いたものだけ。** 2026-09-21、ショップガイドの中に
        # 「フロアマップ」の文字で書かれていたリンクを使った。**こちらで組み立てない**
        kouho = [dict(k, chizu=a.url, michi="**原典が書いたリンク**") for k in kouho]
    if not kouho:
        print("候補が0件。**規約が「取ってよい」の施設がまだ無い。**")
        print("**「無い」ではない。** 人が読むまで、この段は1枚も開かない")

    kekka = []
    for i, k in enumerate(kouho):
        if i:
            time.sleep(WAIT)
        d = hitotsu(k, hiduke)
        kekka.append(d)
        print(f"{d.get('kekka','—'):4} {d['mei']}  "
              f"{d.get('dokokara') or d.get('riyuu') or ''}")

    KIROKU.parent.mkdir(parents=True, exist_ok=True)
    KIROKU.write_text(houkoku(kekka, hiduke), encoding="utf-8")
    JSON_SAKI.write_text(
        json.dumps({"hi": hiduke, "kekka": kekka}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print(f"\n{KIROKU} に書いた")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
