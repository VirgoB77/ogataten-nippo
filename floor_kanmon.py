#!/usr/bin/env python3
"""フロアマップを**取ってよいかだけ**を確かめる段。**まだ1枚も取らない。**

## なぜ関所を別の段にするか

いままで取りに行ってきたのは**役所の届出**だった。あれは
**公開することが法律で決まっているもの**で、相手にとって「見せる義務」がある。

**フロアマップは違う。** 相手が自分の金でつくって、自分の判断で出しているもの。
**見せる義務は無い。** だから「取れるか」ではなく「**取ってよいか**」を先に見る。

## 関所は2つある。**片方だけでは足りない**

    robots.txt   **機械への指示。** 読むのはこの箱
    利用規約     **人への約束。** 読むのは人間

robots.txt が許可でも、利用規約が「複製・転載を禁じます」と書いていれば、
**取ってよいが、残して配ってはいけない**ことがある。
**この2つは別の問いなので、別の欄に書く**（共通仕様の「保存の状態と公開の状態を別の欄に」と同じ形）。

この段は robots.txt を読んで、**利用規約がどこにあるかを見つけるところまで**。
**規約を読んで良し悪しを決めるのは人間。** この箱は決めない。

## 候補のURLは、どこから来たか

2026-09-21、**検索で出たものをこちらが並べた。**
**役所の一覧から辿ったものではないし、公的資料で確かめてもいない。**
ドメインを思い出して作文したわけでもないが、**「確かめた」とは言えない**ので、
記録の側にそう書く（ルール⑥・名乗りは事実の主張になる）。

`--tops` で人が直に渡したときは、**渡されたURLをドメインに丸めない**
（`teiden_recon.py` で踏んだ形。10社中6社が親会社の玄関になるところだった）。

## 数え方

**「0件」は、その道を1回も通っていないときにも出る。**
robots が確かめられなかった相手は「拒否」ではなく「**分からない**」に入れる。
**分からないを、通ったことにも、断られたことにもしない。**
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

# 生のバイトは `inbox/`（`.gitignore`）。**公開側には1バイトも入れない**
INBOX = HERE / "inbox" / "floor"
# 記録は「何を見て、robots が何と言って、規約がどこにあるか」だけ。中身は入れない
KIROKU = HERE / "data" / "ref" / "floor-kanmon.md"

LINK = re.compile(r'<a\s[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)

# **人への約束**が書いてありそうなリンクの語。
# 「規約」だけだと会員規約やポイント規約まで拾うので、複数の言い方を並べる
YAKUSOKU = ("利用規約", "サイトポリシー", "ご利用にあたって", "ご利用について",
            "サイトのご利用", "著作権", "免責", "禁止事項", "Terms")

# 候補。**検索で出たものをこちらが並べた。公的資料で確かめていない**（上の注記）。
# 店舗面積は手元の `data/all.json` の最大値。**施設の大きさの順に並べただけ**で、
# 「これがよい」と決めているわけではない。
#
# **`unei` を欄に持つのは、横に広げるのが安いかどうかがここで決まるから。**
# robots も利用規約も**運営者ごとに1つ**なので、同じ運営者の2軒目からは
# 関所を通し直す必要がほぼ無い。**面を広げるなら、まず同じ運営者の中で広げる。**
#
# **`yakusoku` は、人が利用規約を読んだ結果。**
#
#     未確認          まだ誰も読んでいない。**取りに行かない**
#     取ってよい      人が読んで決めた。**この日付が入って初めて取りに行く**
#     取ってはいけない 相手が禁じている。**robots が許可でも通さない**
#     規約未確定      **人が読んだ。そのうえで、拒否とも許可とも決まらなかった**
#
# **「未確認」と「取ってはいけない」を同じ顔にしない。**
# どちらも取りに行かないが、**前者は調べれば変わり、後者は許可を取るまで変わらない。**
# 数えるときに混ぜると、「あと5件調べれば増える」のか「もう頭打ち」なのかが分からなくなる。
#
# **「規約未確定」を、その2つのどちらにも混ぜない**（2026-09-21・統括の判断で足した）。
#
#     未確認      **読んでいない。** 読めば動く
#     規約未確定  **読んだ。** 読んでも動かなかった。**次に動くのは、許可を取ったときだけ**
#     取ってはいけない **読んで、禁じていると分かった**
#
# 「未確認」に入れると**まだ調べる余地があるように見え**、
# 「取ってはいけない」に入れると**相手が書いていない禁止を書いてあることにする**（ルール⑥）。
# **どちらも事実と違う。** だから欄を分ける。
#
# 2026-09-21、1件目で当たった。阪急西宮ガーデンズのサイトポリシーが
# **「許可無く無断で複製・二次利用などする事はできません」**と書いていた。
# **robots は関係ない。規約の確認は形式ではなく、実際に効く。**
#
# **`id` は URL からも施設名からも作らない。** どちらもあとで変わる（3.5「鍵には
# あとから変わらないと言い切れるものだけを入れる」）。ここで人が決めて、動かさない。
# **語はここで1つだけ持つ。** 数える側で並べ直さない（2か所に書くと必ずずれる）。
KEKKA = ("取ってよい", "未確認", "規約未確定", "取ってはいけない")

# **運営会社の規約は、施設の規約の代わりにならない。**
#
# robots と規約を別の欄で持つのと同じ形（正本9節）。**片方で他方を代用しない。**
# 阪急西宮ガーデンズの施設の欄は、**施設のサイトポリシー**を読んで決める
# （2026-09-24 に「規約未確定」へ戻し、取得を止めた。理由は下の KOUHO の欄）。
# 下の表は**運営会社の側の話**で、**施設の欄に流し込まない。**
UNEI_YAKUSOKU = (
    {"unei": "阪急阪神", "mei": "阪急阪神ホールディングス",
     "mita_hi": "2026-09-21", "kekka": "規約未確定",
     "url": "https://www.hankyu-hanshin.co.jp/terms/",
     "riyuu": "robots は許可。**自動取得・DB化の明示的な禁止は無い**（④⑤とも語として"
              "出てこなかった）。ただし**コンテンツの利用制限がある**ため、"
              "鯨屋の「**規約・公開条件で迷ったら止まる**」線から、継続自動観測は保留。"
              "**拒否とも許可とも扱わない**（統括の判断・2026-09-21）。"
              "**阪急阪神系の規約調査は、ここで深追いしない。**"},
)

KOUHO = (
    {"id": "gardens",   "mei": "阪急西宮ガーデンズ",   "basho": "兵庫県西宮市",
     "unei": "阪急阪神",     "top": "https://nishinomiya-gardens.com/",
     # **2026-09-21、観測元をショップガイドからフロアのページに替えた**（統括の判断）。
     #
     #     ショップガイド  1枚に **32店**。ページ送り **10枚**。区画の識別子 **無し**
     #     フロアのページ  1枚に **314店**（全部）。ページ送り **無し**。識別子 **在り**
     #
     # **相手への負荷は軽くなる**（10枚 → 1枚）。
     # **URL は原典が書いていたもの**（ショップガイドの中に「フロアマップ」の文字で）。
     # 9/21 のショップガイド32店は**試験観測**として残す。**全店観測としては扱わない**
     "chizu": "https://nishinomiya-gardens.com/floor/1",
     "yakusoku": {"mita_hi": "2026-09-21", "kekka": "規約未確定",
                  # **2026-09-24、「取ってよい」から「規約未確定」に戻した。取得は止まる。**
                  # 「取ってはいけない」とは決めていない。決まるまで新しく取りに行かない。
                  # 9/21 に付けた条件（jouken）は、効いていない欄に見えるので外し、理由の中に残した
                  "riyuu": "**［相手が書いていること］** サイトポリシーの"
                           "「著作権について」が、掲載しているデジタル素材"
                           "（文章・写真・イラスト等の全てのデジタル情報）を"
                           "**許可無く無断で複製・二次利用などする事はできません**"
                           "と書いている。"
                           "**［機械で数えた］** 16語のうち出たのは**複製1回と"
                           "二次利用1回だけ**。**自動取得・クローリング・"
                           "スクレイピング・DB化・商用・営利は、語として0回。**"
                           "**ページそのものの利用と、そこから確かめた事実の記録を"
                           "分ける文言も無い（明示なし）。**"
                           "**［2026-09-21］** 「取って保存することが複製、抽出して配ることが"
                           "二次利用」という読みを、相手はそこまで書いていないとして取り下げ、"
                           "条件付きで「取ってよい」にした（条件：ページ・写真・説明文等を"
                           "再公開しない／公開ショップ情報から確認した事実の観測に限定する）。"
                           "**［2026-09-24、規約未確定に戻した］** その根拠が正本9節と合わない。"
                           "9節は「規約が複製や二次利用を断っていれば取らない」"
                           "「規約に自動取得の禁止が書かれていないことも、許可ではない」と書いている。"
                           "この施設の規約は複製・二次利用を許可なしでは断っていて、"
                           "9/21 の根拠は「自動取得の禁止が語として無い」に寄っていた。"
                           "運営会社（阪急阪神ホールディングス）の側も「規約未確定・継続自動観測は保留」"
                           "のままで、それを解いた根拠が残っていない。"
                           "**迷ったら止まる側に倒す。**「取ってはいけない」とは決めていない。"
                           "**決まるまで新しく取りに行かない。**"
                           "2026-09-21〜24 に取った分の扱いは、取得を止めたこととは別に決める。",
                  "url": "https://nishinomiya-gardens.com/usage"}},
    {"id": "abeno-qs",  "mei": "あべのキューズモール", "basho": "大阪市阿倍野区",
     "unei": "東急不動産",   "top": "https://qs-mall.jp/abeno/",
     "chizu": "https://qs-mall.jp/abeno/shop/floor", "yakusoku": {"mita_hi": "", "kekka": "未確認", "riyuu": "", "url": ""}},
    {"id": "namba-parks", "mei": "なんばパークス",     "basho": "大阪市浪速区",
     "unei": "南海",         "top": "https://nambaparks.com/",
     "chizu": "https://nambaparks.com/floor/map2", "yakusoku": {"mita_hi": "", "kekka": "未確認", "riyuu": "", "url": ""}},
    {"id": "aeon-itami", "mei": "イオンモール伊丹",    "basho": "兵庫県伊丹市",
     "unei": "イオンモール", "top": "https://itami.aeonmall.jp/",
     "chizu": "https://itami.aeonmall.jp/floormap", "yakusoku": {"mita_hi": "", "kekka": "未確認", "riyuu": "", "url": ""}},
    {"id": "aeon-shijonawate", "mei": "イオンモール四條畷", "basho": "大阪府四條畷市",
     "unei": "イオンモール", "top": "https://shijonawate.aeonmall.jp/",
     "chizu": "https://shijonawate.aeonmall.jp/floormap", "yakusoku": {"mita_hi": "", "kekka": "未確認", "riyuu": "", "url": ""}},
    {"id": "lalaport-koshien", "mei": "ららぽーと甲子園", "basho": "兵庫県西宮市",
     "unei": "三井不動産",   "top": "https://mitsui-shopping-park.com/lalaport/koshien/",
     "chizu": "https://mitsui-shopping-park.com/lalaport/koshien/floor/",
     "yakusoku": {"mita_hi": "2026-09-21", "kekka": "取ってはいけない",
                  "riyuu": "サイトポリシーの「著作権について」が、掲載されている"
                           "**情報**・デザイン・レイアウト等について"
                           "**権利者の許可なく複製、転用等されることのないようお願いいたします**"
                           "と書いている。**「できません」ではなく「お願いいたします」だが、"
                           "言っていることは同じ**なので、同じ扱いにする。"
                           "**文体の強さで判断を変えない。** 許可を取れば変わる",
                  "url": "サイトポリシー（人が画面で読んだ。この箱は見ていない）"}},
    {"id": "kuzuha",    "mei": "くずはモール",         "basho": "大阪府枚方市",
     "unei": "京阪",         "top": "https://kuzuha-mall.com/",
     "chizu": "https://kuzuha-mall.com/shopguide/floor/", "yakusoku": {"mita_hi": "", "kekka": "未確認", "riyuu": "", "url": ""}},
    {"id": "lalaport-expocity", "mei": "ららぽーとEXPOCITY", "basho": "大阪府吹田市", "unei": "三井不動産",
     "top": "https://mitsui-shopping-park.com/lalaport/expocity/",
     "chizu": "", "chizu_moto": "未確認（トップから人が辿る）",
     "moto": "参謀が名前から書いた。原典の一覧から辿っていない",
     "yakusoku": {"mita_hi": "", "kekka": "未確認", "riyuu": "", "url": ""}},
    {"id": "grandfront", "mei": "グランフロント大阪", "basho": "大阪市北区", "unei": "グランフロント大阪TMO",
     "top": "https://www.grandfront-osaka.jp/",
     "chizu": "", "chizu_moto": "未確認（トップから人が辿る）",
     "moto": "参謀が名前から書いた。原典の一覧から辿っていない",
     "yakusoku": {"mita_hi": "", "kekka": "未確認", "riyuu": "", "url": ""}},
    {"id": "lucua", "mei": "ルクア大阪", "basho": "大阪市北区", "unei": "JR西日本SC開発",
     "top": "https://www.lucua.jp/",
     "chizu": "", "chizu_moto": "未確認（トップから人が辿る）",
     "moto": "参謀が名前から書いた。原典の一覧から辿っていない",
     "yakusoku": {"mita_hi": "", "kekka": "未確認", "riyuu": "", "url": ""}},
    {"id": "tennoji-mio", "mei": "天王寺ミオ", "basho": "大阪市天王寺区", "unei": "JR西日本SC開発",
     "top": "https://www.tennojimio.co.jp/",
     "chizu": "", "chizu_moto": "未確認（トップから人が辿る）",
     "moto": "参謀が名前から書いた。原典の一覧から辿っていない",
     "yakusoku": {"mita_hi": "", "kekka": "未確認", "riyuu": "", "url": ""}},
    {"id": "hankyu-sanbangai", "mei": "阪急三番街", "basho": "大阪市北区", "unei": "阪急阪神",
     "top": "https://www.h-sanbangai.com/",
     "chizu": "", "chizu_moto": "未確認（トップから人が辿る）",
     "moto": "参謀が名前から書いた。原典の一覧から辿っていない",
     "yakusoku": {"mita_hi": "", "kekka": "未確認", "riyuu": "", "url": ""}},
    {"id": "namba-city", "mei": "なんばCITY", "basho": "大阪市中央区", "unei": "南海",
     "top": "https://www.nambacity.com/",
     "chizu": "", "chizu_moto": "未確認（トップから人が辿る）",
     "moto": "参謀が名前から書いた。原典の一覧から辿っていない",
     "yakusoku": {"mita_hi": "", "kekka": "未確認", "riyuu": "", "url": ""}},
    {"id": "amagasaki-qs", "mei": "あまがさきキューズモール", "basho": "兵庫県尼崎市", "unei": "東急不動産",
     "top": "https://qs-mall.jp/amagasaki/",
     "chizu": "", "chizu_moto": "未確認（トップから人が辿る）",
     "moto": "参謀が名前から書いた。原典の一覧から辿っていない",
     "yakusoku": {"mita_hi": "", "kekka": "未確認", "riyuu": "", "url": ""}},
    {"id": "umie", "mei": "神戸ハーバーランドumie", "basho": "神戸市中央区", "unei": "イオンモール",
     "top": "https://umie.jp/",
     "chizu": "", "chizu_moto": "未確認（トップから人が辿る）",
     "moto": "参謀が名前から書いた。原典の一覧から辿っていない",
     "yakusoku": {"mita_hi": "", "kekka": "未確認", "riyuu": "", "url": ""}},
    {"id": "ario-kakogawa", "mei": "セブンパークアリオ加古川", "basho": "兵庫県加古川市", "unei": "セブン&アイ",
     "top": "https://kakogawa.ario.jp/",
     "chizu": "", "chizu_moto": "未確認（トップから人が辿る）",
     "moto": "参謀が名前から書いた。原典の一覧から辿っていない",
     "yakusoku": {"mita_hi": "", "kekka": "未確認", "riyuu": "", "url": ""}},
    {"id": "aeon-kyoto", "mei": "イオンモールKYOTO", "basho": "京都市南区", "unei": "イオンモール",
     "top": "https://kyoto.aeonmall.com/",
     "chizu": "", "chizu_moto": "未確認（トップから人が辿る）",
     "moto": "参謀が名前から書いた。原典の一覧から辿っていない",
     "yakusoku": {"mita_hi": "", "kekka": "未確認", "riyuu": "", "url": ""}},
)


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


def yakusoku_no_arika(base: str, raw: bytes, ctype: str):
    """トップから「人への約束」が書いてありそうなリンクを拾う。**読まない。**

    **在りかを見つけるところまで。** 中身が何と書いてあるかは人間が読む。
    """
    honbun, _enc = decode_html(raw, ctype)
    de, mita = [], set()
    for href, naka in LINK.findall(honbun):
        t = moji(naka)
        if not any(g in t for g in YAKUSOKU):
            continue
        u = urllib.parse.urljoin(base, html.unescape(href))
        if u in mita:
            continue
        mita.add(u)
        de.append({"text": t[:40], "url": u})
    return de


def hitotsu(mei: str, basho: str, top: str, chizu: str, sid: str = "", unei: str = "",
            yakusoku: str = "未確認"):
    """1施設ぶん。**robots を先に見て、通ったときだけトップを1回開く。**"""
    d = {"id": sid, "名前": mei, "場所": basho, "運営": unei,
         "トップ": top, "フロアマップ": chizu, "規約": yakusoku}
    ok, why = check_robots(chizu)
    d["robots"] = {True: "許可", False: "拒否", None: "分からない"}[ok]
    d["robots_riyuu"] = why
    if ok is not True:
        # **拒否のときは取りに行かない。分からないときも行かない**（3.4）
        d["約束"] = []
        d["note"] = "robots が通らなかったので、トップを開いていない"
        return d
    time.sleep(WAIT)
    try:
        status, ctype, raw = get(top)
    except Konde as e:
        d["約束"] = []
        d["note"] = f"{e}。その回は中止"
        return d
    except Exception as e:
        d["約束"] = []
        d["note"] = f"トップが開けなかった {type(e).__name__}"
        return d
    d["top_status"] = status
    d["約束"] = yakusoku_no_arika(top, raw, ctype)
    if not d["約束"]:
        # **0件は「無い」ではない。** 語の並べ方が足りないだけのことがある
        d["note"] = "約束らしいリンクが0件。**無いとは限らない**（語の一覧が足りない／JSで出している）"
    return d


def houkoku(kekka, hiduke):
    a = [].append
    a("# フロアマップの関所")
    a("")
    a(f"{hiduke} に確かめた。**この段は1枚も取っていない。**")
    a("")
    a("**候補のURLは、こちらが名前から書いたか、検索で出たものを並べた。**")
    a("役所の一覧から辿ったものではなく、公的資料で確かめてもいない。")
    a("**届かなかった回は「その名前のサイトが無い」ではなく、")
    a("「この道すじでは届かなかった」**（ルール⑥）。")
    a("")
    a("**フロアページの在りかが「未確認」の候補は、トップで関所だけ通している。**")
    a("`/floormap` のような道すじを当てに行くのは作文なので、しない（9節）。")
    a("")
    a("**関所は2つある。片方だけでは足りない。**")
    a("")
    a("    robots.txt   機械への指示。読むのはこの箱")
    a("    利用規約     人への約束。**読むのは人間。この箱は良し悪しを決めない**")
    a("")
    a("**robots が許可でも、規約が転載を禁じていれば、取ってよいが配ってはいけない。**")
    a("")
    a("**関所は運営者ごとに1つ。** 同じ運営者の2軒目は、通し直す必要がほぼ無い。")
    a("**面を広げるなら、まず同じ運営者の中で広げるのがいちばん安い。**")
    a("")
    a("| 施設 | 場所 | 運営 | robots | **規約** | **フロアページ** | 理由 | 約束の在りか |")
    a("|---|---|---|---|---|---|---|---|")
    for d in kekka:
        arika = "<br>".join(f"[{x['text']}]({x['url']})" for x in d["約束"]) or "—"
        a(f"| {d['名前']} | {d['場所']} | {d.get('運営') or '—'} | **{d['robots']}** "
          f"| **{d.get('規約') or '未確認'}** "
          f"| {d.get('フロアページ') or '未確認'} "
          f"| {d['robots_riyuu']} | {arika} |")
    a("")
    kazu = {"許可": 0, "拒否": 0, "分からない": 0}
    for d in kekka:
        kazu[d["robots"]] += 1
    a(f"許可 {kazu['許可']} / 拒否 {kazu['拒否']} / **分からない {kazu['分からない']}**")
    a("")
    a("**「分からない」を、通ったことにも、断られたことにもしない。**")
    a("robots.txt を1バイトも読めていない回がここに入る（こちらが外に出られないときも同じ顔で出る）。")
    a("")
    for d in kekka:
        if d.get("note"):
            a(f"- {d['名前']}：{d['note']}")
    a("")
    return "\n".join(a.__self__)


def main(argv=None):
    p = argparse.ArgumentParser(description="フロアマップの関所。取らない")
    p.add_argument("--tops", help="人が直に渡す。名前=トップ=フロアマップ をカンマ区切り")
    p.add_argument("--limit", type=int, default=0, help="上から何件だけ見るか（0＝全部）")
    a = p.parse_args(argv)

    kouho = list(KOUHO)
    if a.tops:
        kouho = []
        for x in a.tops.split(","):
            bu = x.split("=")
            if len(bu) != 3:
                p.error(f"名前=トップ=フロアマップ の形で渡す: {x}")
            kouho.append({"id": "", "mei": bu[0].strip(), "basho": "（人が渡した）",
                          "unei": "", "top": bu[1].strip(), "chizu": bu[2].strip(),
                          "yakusoku": {"mita_hi": "", "kekka": "未確認",
                                       "riyuu": "", "url": ""}})
    if a.limit:
        kouho = kouho[:a.limit]

    hiduke = today()
    kekka = []
    for i, k in enumerate(kouho):
        if i:
            time.sleep(WAIT)
        # **フロアページの在りかが未確認の候補は、トップで関所だけ通す。**
        # `/floormap` のような道すじを当てに行くのは作文（9節）
        michi = k.get("chizu") or k["top"]
        d = hitotsu(k["mei"], k["basho"], k["top"], michi, k["id"], k["unei"],
                    (k.get("yakusoku") or {}).get("kekka", "未確認"))
        # **候補の出どころを、結果にそのまま持たせる。**
        # 「検索で出た」と「原典の一覧から辿った」は別（ルール⑥）
        d["候補の出どころ"] = k.get("moto") or "検索で出たものを参謀が並べた"
        d["フロアページ"] = "確かめた道すじ" if k.get("chizu") else (
            k.get("chizu_moto") or "未確認")
        print(f"{d['robots']:　<5} {k['mei']}  {d['robots_riyuu']}")
        kekka.append(d)

    INBOX.mkdir(parents=True, exist_ok=True)
    (INBOX / f"kanmon-{hiduke}.json").write_text(
        json.dumps({"hiduke": hiduke, "kekka": kekka}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    KIROKU.parent.mkdir(parents=True, exist_ok=True)
    KIROKU.write_text(houkoku(kekka, hiduke), encoding="utf-8")
    print(f"\n{KIROKU} に書いた")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
