#!/usr/bin/env python3
"""停電の**実データページを1社だけ特定する**段。**まだためない。**

## なぜこれが要るか

2026-09-21 に5候補を3軸で並べたら、**停電だけ「③を1度も測っていないのに
先頭に置かれていた」**（`docs/keikaku.md`）。

    失う速さ   7〜60日と**言われている**。**こちらの実測は0**
    設備       ためる段は在る。**通す先が1本しかない**
    その1本    「停電履歴表示期間の延長について」という**お知らせ**。履歴ページ本体ではない

**全国に広げる前に、1社で仮説そのものを確かめる**（統括・2026-09-21）。

## 順番を守る。**robots → 規約 → 中身**

統括の指示どおりに段を切る。

    ① robots      **この段が毎回見る。** 拒否・分からないなら、そこで止まる
    ② 形だけ見る   **1回だけ。** `shitami()` で**形を測る。中身は持ち帰らない**
    ③ 規約の在りか **URL を拾うだけ。取らない**（取るのは `yakusoku_get.py`）
    ④ 中身         発生日時・復旧日時・地域・戸数。**規約が通ってから。この段はやらない**

**③と④の間に人が入る。** 規約の①〜⑤を統括が読み、**取得開始の判断は運営者。**

## **1回見たことを、許されたことにしない**

`tenanto_kanmon.py --ikkai` と同じ線。
**robots が通ったから1回開けた**というだけで、**毎日取ってよいことにはならない。**
関所が別（9節「1回だけ見る」と「毎日取る」）。

## 行き先は**探す段の記録**から読む。**こちらで足さない**

`teiden_get.yomu()` を通す。**URL を作文しない**（3.4）。
記録の「記録らしいリンク」の下に並んでいるものだけを見る。

**1社だけ。** `--limit` の既定は 1。**他社へ自動的に進まない**（統括の指示）。

## **停電の個票を1件も持ち帰らない**

発生日時・地域・戸数は、**規約が通るまで取らない。**
`shitami()` は形しか返さないので、そのまま使う。**自前で本文を切り出さない。**
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
from teiden_recon import KIROKU_GO, SOKUHO_GO  # noqa: E402  **語は1か所**
from tenant_recon import shitami  # noqa: E402  **形の測り方も1か所**
from yakusoku_get import ARIKA  # noqa: E402  **規約の在りかの語も1か所**

KIROKU = HERE / "data" / "ref" / "teiden-ikkai.md"
JSON_SAKI = HERE / "data" / "ref" / "teiden-ikkai.json"
INBOX = HERE / "inbox" / "teiden-ikkai"

LINK = re.compile(r'<a\s[^>]*href\s*=\s*["\']([^"\']+)["\'][^>]*>(.*?)</a>',
                  re.I | re.S)
TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
MIDASHI = re.compile(r"<h([1-3])[^>]*>(.*?)</h\1>", re.I | re.S)
# **辿るのは2本まで。** それ以上は総当たりに近づく（3.4）
MADE = 2


def ikisaki(limit: int = 1):
    """**この回で出て行く先。** 見張りがここを呼ぶ。

    `teiden_get.py` と同じ約束——**URL の一覧を返す。**
    行き先の正本は探す段の記録なので、**本番と同じ道を通す。**

    **辿った先はここに出ない。** 開いてみないと分からないため
    （robots はホストごとに見直している）。
    """
    from teiden_get import yomu
    return [u for _t, u in yomu()][:max(limit, 0)]


def moji(s):
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


def erabu(base, raw, ctype):
    """**向こうが書いたリンク**から、実データページの候補を選ぶ。

    **記録を先に、速報を後に。** 鯨屋が欲しいのは記録のほう（`teiden_recon.py`）。
    **語が似ているものを混ぜない**（3.5）——「停電情報」は**いまの停電**。

    **2本まで。** `id` や連番を作らない。
    """
    honbun, _m = decode_html(raw, ctype)
    mita, kiroku, sokuho = set(), [], []
    for u, naka in LINK.findall(honbun):
        t = moji(naka)
        if not t or len(t) > 60:
            continue
        saki = urllib.parse.urljoin(base, html.unescape(u))
        if not saki.startswith("http") or saki in mita:
            continue
        if any(g in t for g in KIROKU_GO):
            mita.add(saki)
            kiroku.append({"text": t[:40], "url": saki, "muki": "記録"})
        elif any(g in t for g in SOKUHO_GO):
            mita.add(saki)
            sokuho.append({"text": t[:40], "url": saki, "muki": "速報"})
    return (kiroku + sokuho)[:MADE]


def yakusoku_no_arika(base, raw, ctype):
    """規約らしいリンクの **URL を拾うだけ。取りに行かない。**

    取るのは `yakusoku_get.py`（関所が別）。ここは**在りかを示すところまで。**
    **強い順**に並べる（サイト全体の約束が先、章の名前は後ろ）。
    """
    honbun, _m = decode_html(raw, ctype)
    de, mita = [], set()
    for u, naka in LINK.findall(honbun):
        t = moji(naka)
        if not t or len(t) > 40:
            continue
        atta = [g for g in ARIKA if g in t]
        if not atta:
            continue
        saki = urllib.parse.urljoin(base, html.unescape(u))
        if not saki.startswith("http") or saki in mita:
            continue
        mita.add(saki)
        de.append({"text": t[:40], "url": saki,
                   "tsuyosa": min(ARIKA.index(g) for g in atta)})
    de.sort(key=lambda d: d["tsuyosa"])
    return de[:5]


def midashi(raw, ctype):
    """**そのページが何のページか**を、向こうの見出しで示す。

    **こちらが名乗らない**（ルール⑥）。タイトルと h1〜h3 をそのまま出す。
    **停電の個票は入らない**——見出しは「停電履歴」などのページ名。
    """
    honbun, _m = decode_html(raw, ctype)
    t = TITLE.search(honbun)
    mi = [moji(m.group(2))[:60] for m in MIDASHI.finditer(honbun)]
    return {"title": moji(t.group(1))[:80] if t else "",
            "midashi": [x for x in mi if x][:8]}


def hozon(url, raw, hiduke):
    saki = INBOX / hiduke
    saki.mkdir(parents=True, exist_ok=True)
    p = urllib.parse.urlsplit(url)
    na = (p.netloc + p.path).replace("/", "-")
    na = "".join(c if c.isalnum() or c in "-._" else "-" for c in na)[:90]
    (saki / (na + ".html")).write_bytes(raw)
    return na + ".html"


def hiraku(url, hiduke, d):
    """robots を見て、通ったときだけ1回開く。**返すのは形と見出しだけ。**"""
    ok, why = check_robots(url)
    d["robots"] = {True: "許可", False: "拒否", None: "分からない"}[ok]
    d["robots_riyuu"] = why
    if ok is not True:
        d["kekka"] = "見送り"
        d["riyuu"] = f"robots が{d['robots']}：{why}"
        return d, None, None
    time.sleep(WAIT)
    try:
        status, ctype, raw = get(url)
    except Konde as e:
        d["kekka"], d["riyuu"] = "見送り", f"{e}。この回は開かない"
        return d, None, None
    except Exception as e:                                       # noqa: BLE001
        d["kekka"] = "届かなかった"
        d["riyuu"] = f"{type(e).__name__}: {e}"
        return d, None, None
    d["kekka"] = "開けた"
    d["status"] = status
    d["hozon"] = hozon(url, raw, hiduke)
    d.update(midashi(raw, ctype))
    # **形だけ。中身は持ち帰らない**
    d["katachi"] = shitami(url, raw, ctype)
    return d, raw, ctype


def hitotsu(f: dict, hiduke: str):
    """1社ぶん。**入口 → 実データページの候補 → 形 → 規約の在りか**まで。"""
    d = {"text": f.get("text", ""), "url": f["url"], "hi": hiduke,
         "saki": [], "yakusoku": []}
    d, raw, ctype = hiraku(f["url"], hiduke, d)
    if raw is None:
        return d

    d["yakusoku"] = yakusoku_no_arika(f["url"], raw, ctype)
    for saki in erabu(f["url"], raw, ctype):
        s = dict(saki)
        s, raw2, ctype2 = hiraku(saki["url"], hiduke, s)
        if raw2 is not None and not d["yakusoku"]:
            # 入口に無ければ、開いた先で探す。**作文はしない**
            d["yakusoku"] = yakusoku_no_arika(saki["url"], raw2, ctype2)
        d["saki"].append(s)
    return d


def awaseru(kono_kai, michi=None):
    """**前の回を消さない。** 相手（ホスト）ごとに最後の1回を持つ。

    2026-09-21、1社ずつ回す形にしたのに、**書き直しで前の社が消えていた。**
    保健所の探す段と規約の段で同じ形を踏んで直した。**同じ直し方をする。**

    **この回で見ていない相手も残す**——「見ていない」と「0本だった」は別（9節）。
    """
    michi = michi or JSON_SAKI
    dai = {}
    if michi.exists():
        try:
            for d in json.loads(michi.read_text(encoding="utf-8")).get("kekka", []):
                if isinstance(d, dict) and d.get("url"):
                    dai[urllib.parse.urlsplit(d["url"]).netloc] = d
        except (ValueError, TypeError):
            dai = {}               # 壊れていたら作り直す。**黙って0件にしない**
    for d in kono_kai:
        dai[urllib.parse.urlsplit(d["url"]).netloc] = d
    return [dai[k] for k in sorted(dai)]


def houkoku(kekka, hiduke):
    a = [].append
    a("# 停電の実データページを1社だけ見た記録")
    a("")
    a(f"{hiduke} に走らせた。**1社だけ。他社へ自動的に進んでいない**（統括の指示）。")
    a("")
    a("**この段は、発生日時・復旧日時・地域・戸数を1件も取っていない。**")
    a("入るのは**ページの形と、向こうが書いた見出しと、規約の在りか**だけ。")
    a("")
    a("**1回見たことを、許されたことにしない。** robots が通ったから1回開けた"
      "というだけで、**毎日取ってよいことにはならない**（関所が別・9節）。")
    a("")
    if not kekka:
        a("**行き先が0本だった。**")
        a("")
        a("**「0本」は「無い」ではない。** 探す段の記録に"
          "「記録らしいリンク」が1本も無いか、まだ回っていない。")
        a("")
        return "\n".join(a.__self__)

    a("| 入口 | robots | 結果 | 向こうのページ名 | 辿った先 | 規約の在りか |")
    a("|---|---|---|---|---:|---:|")
    for d in kekka:
        a(f"| {d.get('text') or d['url']} | **{d.get('robots','—')}** "
          f"| {d.get('kekka','—')} | {d.get('title') or '—'} "
          f"| {len(d.get('saki') or [])} | {len(d.get('yakusoku') or [])} |")
    a("")

    for d in kekka:
        a(f"## {d.get('text') or d['url']}")
        a("")
        a(f"読んだページ：{d['url']}")
        a("")
        if d.get("riyuu"):
            a(f"**{d['riyuu']}**")
            a("")
        if d.get("midashi"):
            a("**このページの見出し**（**向こうが書いた語。こちらが名乗らない**）")
            a("")
            for m in d["midashi"]:
                a(f"  - {m}")
            a("")
        ka = d.get("katachi") or {}
        if ka:
            ko = ka.get("kotei_url") or {}
            a("**このページの形**（**中身は入っていない**）")
            a("")
            a(f"- JS を落とす前 {ka['zenbu_moji']:,} 文字 → "
              f"落とした後 **{ka['mieru_moji']:,} 文字**")
            a(f"- 同じ形のリンク {ko.get('kazu', 0)} 本"
              f"（形：`{ko.get('katachi', '—')}`）")
            a(f"- リンクの形の種類 {ka.get('link_katachi', 0)}")
            a("")
            if ka["zenbu_moji"] and ka["mieru_moji"] * 2 < ka["zenbu_moji"]:
                a("**落とした後が半分を切っている。** JS で描いている疑いがある。")
                a("**「無い」ではない。** 形が違うだけのことがある。")
                a("")
        for s in d.get("saki") or []:
            a(f"### 辿った先（{s.get('muki','—')}）：{s.get('text','')}")
            a("")
            a(f"{s['url']}")
            a("")
            a(f"- robots **{s.get('robots','—')}**"
              f"{'：' + s['robots_riyuu'] if s.get('robots') != '許可' else ''}")
            a(f"- 結果 {s.get('kekka','—')}"
              + (f"（{s['riyuu']}）" if s.get("riyuu") else ""))
            if s.get("title"):
                a(f"- 向こうのページ名 **{s['title']}**")
            ka2 = s.get("katachi") or {}
            if ka2:
                a(f"- JS を落とす前 {ka2['zenbu_moji']:,} 文字 → "
                  f"落とした後 **{ka2['mieru_moji']:,} 文字**")
            a("")
            for m in (s.get("midashi") or [])[:8]:
                a(f"  - {m}")
            if s.get("midashi"):
                a("")
        if d.get("yakusoku"):
            a("**規約の在りか**（**強い順。この段は取っていない**）")
            a("")
            for y in d["yakusoku"]:
                a(f"  - [{y['text']}]({y['url']})")
            a("")
            a("**次は `yakusoku_get.py` が1回だけ読む。** 関所は robots だけ。")
            a("**①〜⑤の語と見出しを出して、判断は人がする**（統括 → 運営者）。")
            a("")
        else:
            a("**規約らしいリンクが0本。**")
            a("")
            a("**「無い」ではない。** 語が違うか、フッターが JS のことがある。")
            a("**人が画面で1回見るまで、「規約が無い」とは書かない**（ルール⑥）。")
            a("")

    a("## この段がやっていないこと")
    a("")
    a("- **発生日時・復旧日時・地域・戸数を1件も取っていない。**"
      "規約が通ってからにする（統括の指示の順番）")
    a("- **他社を1社も見ていない。** 1社で仮説を確かめるまで広げない")
    a("- **毎日取る許可は、どこにも出ていない。** 1回見ただけ")
    a("")
    return "\n".join(a.__self__)


def main(argv=None):
    p = argparse.ArgumentParser(
        description="停電の実データページを1社だけ見る。中身は取らない")
    p.add_argument("--limit", type=int, default=1,
                   help="何社見るか（既定 1。**他社へ自動的に進まない**）")
    p.add_argument("--url", default="",
                   help="人が渡した入口（**探さずに直に開く**。robots は見る）")
    a = p.parse_args(argv)

    hiduke = today()
    if a.url:
        saki = [{"text": "（人が渡した）", "url": a.url}]
    else:
        from teiden_get import yomu     # **行き先の正本は探す段の記録**
        saki = [{"text": t, "url": u} for t, u in yomu()][:max(a.limit, 0)]

    if not saki:
        print("行き先が0本。**探す段の記録に「記録らしいリンク」が無い。**")

    kekka = []
    for i, f in enumerate(saki):
        if i:
            time.sleep(WAIT)
        d = hitotsu(f, hiduke)
        kekka.append(d)
        print(f"{d.get('kekka','—'):6} {d.get('title') or d['url']}"
              f"  辿った先 {len(d.get('saki') or [])}"
              f"  規約 {len(d.get('yakusoku') or [])}本")

    zenbu = awaseru(kekka)

    KIROKU.parent.mkdir(parents=True, exist_ok=True)
    KIROKU.write_text(houkoku(zenbu, hiduke), encoding="utf-8")
    JSON_SAKI.write_text(
        json.dumps({"hi": hiduke, "kekka": zenbu}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print(f"\n{KIROKU} に書いた")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
