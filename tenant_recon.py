#!/usr/bin/env python3
"""施設のショップ一覧を**下見する**段。**店の名前は1つも記録しない。**

## この段が答えるのは7つ

    ① 店舗一覧ページがあるか
    ② 階別の情報があるか
    ③ 店舗名が HTML に**文字として**入っているか（JS で描いていないか）
    ④ robots.txt
    ⑤ 利用規約で自動取得してよいか      **人が読む。この箱は決めない**
    ⑥ 1回の取得で何店舗ぶん取れるか      **推定。実数ではない**
    ⑦ 店舗ごとに固定URLやIDがあるか

**⑥⑦は「形」で測る。** 店の名前そのものは数えるだけで、**1つも書き出さない。**

## 順番が大事。**規約が先、robots が次、下見が最後**

    取ってはいけない → **開かない。** robots も見ない
    未確認           → **開かない。** 人が規約を読むまで
    取ってよい       → robots を見て、通れば1回だけ開く

**「HTMLなら軽い」は、規約の話を何も変えない。**
2026-09-21 に2施設で確かめた文面は、どちらも**「掲載している情報」**が対象で、
画像かHTMLかを分けていない。**取り方を変えても、壁は同じ場所にある。**

## 分け方は4つ。**「未確認」と「技術的に取得困難」を混ぜない**

    許可              規約が通り、robots も通り、下見で取れる形だった
    拒否              規約か robots が断っている
    未確認            **まだ人が規約を読んでいない**
    技術的に取得困難  規約も robots も通ったが、**HTMLに文字が無い**

**前の2つは相手の話。後ろの2つはこちらの話。** 混ぜると打つ手が分からなくなる。
"""

from __future__ import annotations

import argparse
import collections
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
from floor_kanmon import KOUHO  # noqa: E402  **施設の一覧は関所が正本。2か所に書かない**

INBOX = HERE / "inbox" / "floor"
KIROKU = HERE / "data" / "ref" / "tenant-recon.md"
JSON_SAKI = HERE / "data" / "ref" / "tenant-recon.json"

LINK = re.compile(r'<a\s[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
SCRIPT = re.compile(r"<(script|style)\b.*?</\1>", re.I | re.S)
# 階の表記。**「1F」だけで探さない**——地下と日本語表記を落とす
KAI = re.compile(r"(?:B\d{1,2}F|\d{1,2}F|地下\d{1,2}階|[１-９1-9]\d?階)")
# 「◯◯店」の形。**店の名前は持ち帰らない。数えるだけ**
MISE = re.compile(r".店$")
# 出店先らしい語。**これで施設名を当てるのではなく、分離できそうかの当たりを見る**
SHISETSU = re.compile(r"(モール|ガーデンズ|パーク|プラザ|タウン|シティ|スクエア|"
                      r"アウトレット|百貨店|ららぽ|ルミネ|パルコ|イオン|阪急|阪神|"
                      r"駅|ビル|センター)")
# 開店・閉店らしいリンク。**開きに行かない。有無だけ**
NEWS = re.compile(r"(NEWS|ニュース|お知らせ|新着|OPEN|オープン|CLOSE|クローズ|"
                  r"閉店|開店|新店)", re.I)


def moji(s):
    t = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    return re.sub(r"\s+", " ", t).strip()


def kata(u):
    """URLの**形**。数字を含む区切りを伏せる。**店の名前も番号も残さない。**

    `/shop/detail/1234` と `/shop/detail/5678` を同じ形として数えるため。
    **これが「店舗ごとに固定URLがあるか」の答えになる。**
    """
    p = urllib.parse.urlsplit(u).path
    return re.sub(r"/[^/]*\d[^/]*", "/＊", p) or "/"


def get(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ja",
    })
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, r.headers.get("Content-Type", ""), r.read()
    except urllib.error.HTTPError as e:
        if is_busy(e):
            raise Konde(f"相手が混んでいると言っている（HTTP {e.code}）") from e
        raise


def shitami(base, raw, ctype):
    """1枚の中身を**形だけ**測る。**店の名前は1つも返さない。**"""
    honbun, _m = decode_html(raw, ctype)
    # **JS と CSS を落としてから数える。** 落とさないと、
    # 画面に出ていない文字まで「HTMLに入っている」と数えてしまう
    mieru = SCRIPT.sub(" ", honbun)
    hontai = moji(mieru)

    katachi = collections.Counter()
    for u, naka in LINK.findall(mieru):
        t = moji(naka)
        if not t or len(t) > 40:
            continue
        saki = urllib.parse.urljoin(base, html.unescape(u))
        if urllib.parse.urlsplit(saki).netloc != urllib.parse.urlsplit(base).netloc:
            continue
        katachi[kata(saki)] += 1
    ichiban = katachi.most_common(1)
    kotei = {"katachi": ichiban[0][0], "kazu": ichiban[0][1]} if ichiban else None

    kai = sorted(set(KAI.findall(hontai)))

    # **「◯◯店」の形が何本あるか。** 店の名前は返さない。**数だけ。**
    # 企業側の一覧では、店名に出店先が入っていることが多い
    #（「◯◯モール店」など）。**分離できそうかの当たり**をここで見る
    mise = sum(1 for _u, naka in LINK.findall(mieru)
               if MISE.search(moji(naka) or ""))
    shisetsu = sum(1 for _u, naka in LINK.findall(mieru)
                   if SHISETSU.search(moji(naka) or ""))
    # **開店・閉店らしいページへのリンクがあるか。** 開きに行かない。**有無だけ**
    news = sorted({moji(naka)[:20] for _u, naka in LINK.findall(mieru)
                   if NEWS.search(moji(naka) or "")})

    return {
        "mieru_moji": len(hontai),            # JS を落とした後の文字数
        "zenbu_moji": len(moji(honbun)),      # 落とす前
        "kai_hyouki": kai[:12],
        "kai_kazu": len(kai),
        "kotei_url": kotei,                   # 形と本数。**中身は入れない**
        "link_katachi": len(katachi),
        "mise_katachi": mise,                 # 「◯◯店」の形の本数
        "shisetsu_go": shisetsu,              # 施設らしい語を含むリンクの本数
        "news_kazu": len(news),               # 開閉らしいリンクの本数。**開いていない**
    }


def wakeru(d):
    """4つに分ける。**「未確認」と「技術的に取得困難」を混ぜない。**"""
    if d["yakusoku"] == "取ってはいけない":
        return "拒否", "利用規約が断っている"
    if d["yakusoku"] != "取ってよい":
        return "未確認", "まだ人が利用規約を読んでいない"
    if d.get("robots") == "拒否":
        return "拒否", "robots.txt が断っている"
    if d.get("robots") != "許可":
        return "未確認", f"robots を確かめられなかった（{d.get('robots_riyuu') or ''}）"
    s = d.get("shitami")
    if not s:
        return "未確認", "下見をしていない"
    # **JS を落としたら中身がほとんど無い**＝画面は JS が描いている
    if s["zenbu_moji"] and s["mieru_moji"] / s["zenbu_moji"] < 0.15:
        return "技術的に取得困難", "JS を落とすと文字がほとんど残らない（画面は JS が描いている）"
    if not s["kotei_url"] or s["kotei_url"]["kazu"] < 10:
        return "技術的に取得困難", "同じ形のリンクが10本に満たない（店舗ごとの固定URLが見当たらない）"
    return "許可", "規約・robots が通り、下見でも取れる形だった"


def hitotsu(k, hiduke):
    ya = k.get("yakusoku") or {}
    d = {"id": k["id"], "mei": k["mei"], "unei": k.get("unei", ""),
         "url": k["chizu"], "yakusoku": ya.get("kekka", "未確認"),
         "yakusoku_hi": ya.get("mita_hi", ""), "hi": hiduke}

    if d["yakusoku"] != "取ってよい":
        # **開かない。** 規約が先（未確認も、断られているときも）
        d["robots"] = "見ていない"
        d["wake"], d["riyuu"] = wakeru(d)
        # **表に書いてある理由を、まとめの一言で上書きしない**（2026-09-21）
        if ya.get("riyuu"):
            d["riyuu"] = ya["riyuu"]
        return d

    ok, why = check_robots(k["chizu"])
    d["robots"] = {True: "許可", False: "拒否", None: "分からない"}[ok]
    d["robots_riyuu"] = why
    if ok is not True:
        d["wake"], d["riyuu"] = wakeru(d)
        return d

    time.sleep(WAIT)
    try:
        status, ctype, raw = get(k["chizu"])
    except Konde as e:
        d["robots_riyuu"] = f"{e}"
        d["wake"], d["riyuu"] = "未確認", f"{e}。その回は中止"
        return d
    except Exception as e:                                        # noqa: BLE001
        d["wake"], d["riyuu"] = "未確認", f"開けなかった {type(e).__name__}: {e}"
        return d

    saki = INBOX / k["id"]
    saki.mkdir(parents=True, exist_ok=True)
    (saki / f"shitami-{hiduke}.html").write_bytes(raw)
    d["status"] = status
    d["shitami"] = shitami(k["chizu"], raw, ctype)
    d["wake"], d["riyuu"] = wakeru(d)
    return d


def houkoku(kekka, hiduke):
    a = [].append
    a("# 商業施設のテナント一覧・下見の記録")
    a("")
    a(f"{hiduke}。**店の名前は1つも入っていない。** 数と形だけ。")
    a("")
    a("**順番は、規約 → robots → 下見。**")
    a("「HTMLなら軽い」は規約の話を何も変えない。2026-09-21 に確かめた2施設の文面は、")
    a("どちらも**「掲載している情報」**が対象で、画像かHTMLかを分けていない。")
    a("")
    a("| 施設 | 運営 | **分け** | 規約 | robots | 階の表記 | 同じ形のリンク | 理由 |")
    a("|---|---|---|---|---|---:|---:|---|")
    for d in kekka:
        s = d.get("shitami") or {}
        ko = s.get("kotei_url") or {}
        a(f"| {d['mei']} | {d['unei']} | **{d['wake']}** | {d['yakusoku']} "
          f"| {d.get('robots') or '—'} | {s.get('kai_kazu', '—')} "
          f"| {ko.get('kazu', '—')} | {d['riyuu']} |")
    a("")
    kazu = collections.Counter(d["wake"] for d in kekka)
    a("**分けた数**")
    a("")
    for na in ("許可", "拒否", "未確認", "技術的に取得困難"):
        mei = [d["mei"] for d in kekka if d["wake"] == na]
        a(f"- **{na} {kazu[na]}**" + ("：" + "、".join(mei) if mei else ""))
    a("")
    a("**前の2つは相手の話。後ろの2つはこちらの話。** 混ぜると打つ手が分からなくなる。")
    a("")
    a("## 「1回で何店舗取れるか」は、まだ数えていない")
    a("")
    a("上の「同じ形のリンク」は、**店舗ごとの固定URLが何本あるか**の推定にすぎない。")
    a("**店舗数そのものではない。** 一覧に載らない店・1店で複数リンクの店があるため。")
    a("**実数は、規約が通った施設で実物を見てから数える。**")
    a("")
    return "\n".join(a.__self__)


def main(argv=None):
    p = argparse.ArgumentParser(description="テナント一覧の下見。規約が先")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--id")
    a = p.parse_args(argv)

    kouho = [k for k in KOUHO if not a.id or k["id"] == a.id]
    if a.limit:
        kouho = kouho[:a.limit]

    hiduke = today()
    kekka = []
    for i, k in enumerate(kouho):
        if i:
            time.sleep(WAIT)
        d = hitotsu(k, hiduke)
        print(f"{d['wake']:　<9} {d['mei']}  {d['riyuu']}")
        kekka.append(d)

    KIROKU.parent.mkdir(parents=True, exist_ok=True)
    KIROKU.write_text(houkoku(kekka, hiduke), encoding="utf-8")
    JSON_SAKI.write_text(
        json.dumps({"hi": hiduke, "kekka": kekka}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print(f"\n{KIROKU} に書いた")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
