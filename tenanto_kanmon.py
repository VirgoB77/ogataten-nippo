#!/usr/bin/env python3
"""**テナント企業の側**から、店舗在籍を見られるかを確かめる段。**まだ1件も取らない。**

## 向きが逆になる

    施設 → 全テナント     施設を1館ずつ見る。**施設の規約に全部かかる**
    企業 → 全国の出店先   **1社見れば、複数の施設を横断できる**

**ただし「施設の規約が厳しいからテナント側なら取ってよい」とは扱わない。**
**企業ごとに robots.txt と利用規約を確かめる。** 向きが変わっても関所は同じ。

## 分け方は施設側と同じ4つ。**1か所に置く**

`tenant_recon.wakeru` を呼ぶ。**分け方を2か所に書かない**
（同じ言葉で違う判定をする形は、監査で何度も出ている）。

    許可 / 拒否 / **未確認** / **技術的に取得困難**

**「分からない」を許可扱いしない。「まだ調べていない」を0件扱いしない。**

## 2026-09-21：**この経路の追加調査は、いったん停止**

**統括の判断。言い方も統括が決めたものをそのまま置く。**

> **初期5社では継続観測可能な取得元を確認できず、**
> **主力取得経路としての追加調査を停止。**

**⚠️「企業公式ルートは不可能」とは記録しない。** そうは分かっていない。
分かったのは**初期5社で1社も確認できなかった**ことと、
**残り4社の未確認を解くのに要る人手とJS対応に対して、いま優先度が低い**こと。

    ロフト          人がURLを渡して、ようやく読めた → 止める判断
    Francfranc      URLを渡されても 403 で読めない
    ビームス        robots に届かない／規約URLが特定できない
    quadro          JS依存／規約URLが特定できない
    gelato pique    URLを渡されても、英語の商品一覧が返る

**今後、利用条件が明確で、CSV/API や静的HTML で出している企業が
別の調べもので見つかれば、再検討する。** 段はそのまま残す。

## 候補は5社。**大きさの幅を持たせる**

大手だけ選ぶと「店舗検索は当然ある」という結論になる。
**小さいところを必ず1社入れる**——そこが取れないなら、
**地場・個人店は原理的に取れない**ことの下限が見える。

## URLの出どころ

**検索で出たものをこちらが並べた。公的資料でも各社サイトでも確かめていない。**
検索で出なかった欄は**空のままにする。埋めない**（3.4「URLを作文しない」）。
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common.fetch import Konde, WAIT, check_robots  # noqa: E402
from common.runday import today  # noqa: E402
from tenant_recon import get, shitami, wakeru  # noqa: E402  **分け方は1か所**

INBOX = HERE / "inbox" / "tenanto"
KIROKU = HERE / "data" / "ref" / "tenanto-kanmon.md"
JSON_SAKI = HERE / "data" / "ref" / "tenanto-kanmon.json"

# **候補5社。** 2026-09-21、検索で出たURLをこちらが並べた。**開いていない。**
#
# `ichiran` … 公式の店舗一覧・店舗検索
# `kaihei`  … **開店・閉店の情報を、その会社自身が出しているページ**
#              施設側だけでなく**企業側にも履歴がある**ことが、この段で分かった
# `yakusoku`… 人が利用規約を読んだ結果。**空のうちは開かない**
_MI = {"mita_hi": "", "kekka": "未確認", "riyuu": "", "url": ""}
# **人が渡した規約ページのURL。**
#
# 2026-09-21、店舗一覧ページのフッターから規約を辿る形を試したが、
# **JS でフッターを描いている相手には届かなかった。**
# 人がブラウザで開けば見えるのに、静的HTMLには無い。
#
# **機械で規約を特定できない相手がいる、というのが結論。**
# その場合は**人が開いてURLを渡す。** ここに入れれば、探さずに直に取りに行く。
# **渡されたURLを、こちらでドメインに丸めたり作り変えたりしない**（3.4）。
YAKUSOKU_URL = {
    # 2026-09-21、**人が渡した。** こちらが検索で当てたものではない。
    # **作り変えない。**渡された文字列のまま使う
    "loft": "https://www.loft.co.jp/copyright/",
    # **別のホスト**（ヘルプセンター）。robots はそのホストの分を見る
    "francfranc": "https://help.francfranc.com/hc/ja/articles/360022766873",
}
KAISHA = (
    {"id": "beams", "mei": "ビームス", "kibo": "大手セレクト",
     "ichiran": "https://www.beams.co.jp/en/shop/",
     "ichiran_note": ("`/en/` が付くが、**検索で返るページの題は日本語**"
                      "（「ショップ - BEAMS」「ビームス メン 渋谷」など）。"
                      "**日本語だけの別URLがあるかは未確認。** 作文しないので、"
                      "検索が返したものをそのまま使う"),
     "kaihei": "",
     "hito_ga_mita": ("2026-09-21、人が見た範囲では、確認できた規約は"
                      "**オンラインショップの利用規約**だった。商用目的の利用の制限は"
                      "あるが、**その規約が店舗情報のページにも及ぶかは確認できていない。**"
                      "**店舗情報の側は未確認のまま。**"
                      "\n\n"
                      "**同日、統括の側でも店舗情報に適用される一般サイト規約を"
                      "確実には特定できなかった。推測のURLは渡されていない。**"
                      "**ここで止まっているのは「探していない」ではなく「見つからない」。**"),
     "yakusoku": dict(_MI)},
    {"id": "francfranc", "mei": "Francfranc", "kibo": "大手雑貨",
     "ichiran": "https://francfranc.com/pages/stores",
     "ichiran_note": "", "kaihei": "", "yakusoku": dict(_MI)},
    {"id": "loft", "mei": "ロフト", "kibo": "大手雑貨",
     "ichiran": "https://www.loft.co.jp/shop_list/",
     "ichiran_note": "",
     "kaihei": "https://www.loft.co.jp/category/store_info/",
     "yakusoku": {
         "mita_hi": "2026-09-21",
         "kekka": "取ってはいけない",
         "riyuu": (
             "**自動取得やDB化の明示的な禁止は、確認されなかった。**"
             "④も⑤も、語としては出てこなかった。"
             "\n\n"
             "止めた理由はそこではない。**「本サイトの内容」を承諾なく"
             "「複製その他利用」することを、広く制限している**ため。"
             "一般サイト向けの「ご利用に際して」なので、"
             "**店舗情報を含む本サイトに適用されると読むのが自然**（統括の判断）。"
             "\n\n"
             "**鯨屋の「規約・公開条件で迷ったら止まる」により、継続取得は止める。**"
             "\n\n"
             "**⚠️ これを「スクレイピングが明示的に禁止されている」と記録しない。**"
             "**書いていないことを書いてあることにしない**（ルール⑥）。"
             "**許可を取れば変わる。**"),
         "url": "https://www.loft.co.jp/copyright/（人が渡したURL）",
         "yonda": "統括（ChatGPT）が読んで判断。**取得開始の判断は運営者**",
         "kou": {"1": "あり（「著作権」）", "2": "あり（「本サイトの内容」）",
                 "3": "なし", "4": "**なし**", "5": "**なし**"},
     }},
    {"id": "gelatopique", "mei": "gelato pique", "kibo": "中堅アパレル",
     "ichiran": "https://gelatopique.com/Page/shoplist.aspx",
     "ichiran_note": ("**2026-09-21、統括が特定して渡した。**"
                      "公式の販売案内で「全国直営店」のリンク先として"
                      "継続して使われている、とのこと。**こちらは確かめていない。**"
                      "\n\n"
                      "**こちらは2回探して見つけられず、「海外向けの一覧」と書いた。"
                      "それはこちらの見立てで、間違いだった。**"
                      "\n\n"
                      "**URLが分かったことは、取ってよいことではない。**"
                      "robots から通常どおり見る"),
     "kaihei": "", "yakusoku": dict(_MI)},
    {"id": "quadro", "mei": "quadro", "kibo": "**小規模**（関西・東海・関東）",
     "ichiran": "https://quadro-web.com/contents/shoplist",
     "ichiran_note": "この1社だけ、施設側の答え合わせで**在籍を確認済み**",
     "kaihei": "",
     "hito_ga_mita": ("**同日、統括の側でも店舗情報に適用される一般サイト規約を"
                      "確実には特定できなかった。推測のURLは渡されていない。**"
                      "\n\n"
                      "2026-09-21、人がブラウザで見た範囲では——"
                      "公式の店舗一覧が在る。フッターにあるのは"
                      "**個人情報保護方針・返品規約・会員規約・特定商取引法に基づく表示**で、"
                      "**一般サイト向けの利用規約／サイトポリシー／ご利用条件／著作権の"
                      "リンクは確認できなかった。** `robots.txt` は **404 Not Found**。"
                      "\n\n"
                      "**robots が404だから取ってよい、とはしない。**"
                      "**規約が見つからないから許されている、ともしない。**"
                      "どちらも「**無い**」ではなく「**確認できなかった**」。"),
     "yakusoku": dict(_MI)},
)


def hitotsu(k, hiduke, ikkai=False):
    """1社ぶん。

    `ikkai` は「**1回だけ、構造を見る**」。**継続取得の許可ではない。**

    今日（2026-09-21）作った「規約を1回取る段」と同じ形——
    **1回見ることと、毎日取ることを分ける。**

        1回だけ見る   関所は **robots.txt だけ**
        毎日取る      関所は robots ＋ **人が読んだ結果**

    **`ikkai` で見ても、規約の欄は「未確認」のまま動かさない。**
    分けは必ず「未確認」に落ちる（`wakeru` が下見だけでは許可にしないため）。
    **見たことを、許されたことにしない**（ルール⑥）。
    """
    ya = k.get("yakusoku") or {}
    d = {"id": k["id"], "mei": k["mei"], "kibo": k["kibo"],
         "url": k.get("ichiran", ""), "note": k.get("ichiran_note", ""),
         "hito_ga_mita": k.get("hito_ga_mita", ""),
         "kaihei": k.get("kaihei", ""), "yakusoku": ya.get("kekka", "未確認"),
         "hi": hiduke}

    if not k.get("ichiran"):
        # **一覧のURLが無い。**「無い」ではなく「まだ見つけていない」
        d["robots"] = "見ていない"
        d["wake"], d["riyuu"] = "未確認", "公式一覧のURLをまだ見つけていない（**無いとは限らない**）"
        return d
    if d["yakusoku"] != "取ってよい" and not ikkai:
        d["robots"] = "見ていない"
        d["wake"], d["riyuu"] = wakeru(d)
        # **表に書いてある理由があれば、それを出す。**
        # まとめの一言（「利用規約が断っている」）で上書きすると、
        # **止めた本当の理由が消える**（2026-09-21）。
        # 相手が名指しで禁じたのか、こちらが迷って止めたのかは、別のこと
        if ya.get("riyuu"):
            d["riyuu"] = ya["riyuu"]
        d["yakusoku_kou"] = ya.get("kou") or {}
        d["yakusoku_url"] = ya.get("url", "")
        d["yonda"] = ya.get("yonda", "")
        return d
    if ikkai:
        d["ikkai"] = True
        d["ikkai_note"] = ("**1回だけ構造を見た。継続取得の許可ではない。**"
                           "規約の欄は未確認のまま動かしていない")

    ok, why = check_robots(k["ichiran"])
    d["robots"] = {True: "許可", False: "拒否", None: "分からない"}[ok]
    d["robots_riyuu"] = why
    if ok is not True:
        d["wake"], d["riyuu"] = wakeru(d)
        if ikkai:
            # **1回見る回で止まったのは robots。** 規約の理由を書くと、
            # **止めた理由と書いた理由が違う**ことになる（ルール⑥）
            d["riyuu"] = f"robots が{'拒否' if ok is False else '分からない'}：{why}"
        return d

    time.sleep(WAIT)
    try:
        status, ctype, raw = get(k["ichiran"])
    except Konde as e:
        d["wake"], d["riyuu"] = "未確認", f"{e}。その回は中止"
        return d
    except Exception as e:                                        # noqa: BLE001
        d["wake"], d["riyuu"] = "未確認", f"開けなかった {type(e).__name__}: {e}"
        return d

    saki = INBOX / k["id"]
    saki.mkdir(parents=True, exist_ok=True)
    (saki / f"shitami-{hiduke}.html").write_bytes(raw)
    d["status"] = status
    d["shitami"] = shitami(k["ichiran"], raw, ctype)
    if ikkai and d["yakusoku"] != "取ってよい":
        # **下見が通っても「許可」にしない。** 規約が未確認のままなので
        d["wake"] = "未確認"
        d["riyuu"] = ("構造は1回見た（下の表）。**規約が未確認なので、"
                      "継続観測は始めない**")
        return d
    d["wake"], d["riyuu"] = wakeru(d)
    return d


def houkoku(kekka, hiduke):
    a = [].append
    a("# テナント企業の側から見られるか・関所の記録")
    a("")
    a(f"{hiduke}。**店の名前は1つも入っていない。** 数と形だけ。")
    a("")
    a("**向きが逆になる。**「施設 → 全テナント」ではなく「企業 → 全国の出店先」。")
    a("1社見れば複数の施設を横断できる。")
    a("")
    a("**ただし「施設の規約が厳しいから企業側なら取ってよい」とは扱わない。**")
    a("**企業ごとに robots と規約を確かめる。** 向きが変わっても関所は同じ。")
    a("")
    ik = [d for d in kekka if d.get("ikkai")]
    if ik:
        a("**この回は「1回だけ構造を見る」で走らせた。**")
        a("**継続取得の許可ではない。規約の欄は未確認のまま動かしていない。**")
        a("")
    a("| 会社 | 規模 | **分け** | 規約 | robots | 公式一覧 | **開閉の情報** | 覚書 |")
    a("|---|---|---|---|---|---|---|---|")
    for d in kekka:
        a(f"| {d['mei']} | {d['kibo']} | **{d['wake']}** | {d['yakusoku']} "
          f"| {d.get('robots') or '—'} | {'あり' if d['url'] else '**未特定**'} "
          f"| {'**あり**' if d['kaihei'] else '未確認'} | {d['note'] or d['riyuu']} |")
    a("")
    kazu = collections.Counter(d["wake"] for d in kekka)
    for na in ("許可", "拒否", "未確認", "技術的に取得困難"):
        mei = [d["mei"] for d in kekka if d["wake"] == na]
        a(f"- **{na} {kazu[na]}**" + ("：" + "、".join(mei) if mei else ""))
    a("")
    a("**「分からない」を許可扱いしない。「まだ調べていない」を0件扱いしない。**")
    a("")
    a("## 2026-09-21：この経路の追加調査は、いったん停止")
    a("")
    a("> **初期5社では継続観測可能な取得元を確認できず、"
      "主力取得経路としての追加調査を停止。**")
    a("")
    a("**「企業公式ルートは不可能」とは記録していない。** そうは分かっていない。")
    a("分かったのは、初期5社で1社も確認できなかったことと、")
    a("残り4社の未確認を解くのに要る人手とJS対応に対して、いま優先度が低いこと。")
    a("")
    a("**利用条件が明確で、CSV/API や静的HTML で出している企業が見つかれば再検討する。**")
    a("**段はそのまま残してある。**")
    a("")
    for d in kekka:
        s_ = d.get("shitami")
        if not s_:
            continue
        ko = s_.get("kotei_url") or {}
        a(f"### {d['mei']}（構造を1回見た）")
        a("")
        a("| 見たもの | 値 |")
        a("|---|---|")
        a(f"| JS を落とす前の文字数 | {s_['zenbu_moji']:,} |")
        a(f"| JS を落とした後の文字数 | {s_['mieru_moji']:,} |")
        a(f"| **同じ形のリンク** | {ko.get('kazu', 0)} 本（形：`{ko.get('katachi', '—')}`）|")
        a(f"| 「◯◯店」の形のリンク | {s_.get('mise_katachi', 0)} 本 |")
        a(f"| 出店先らしい語を含むリンク | {s_.get('shisetsu_go', 0)} 本 |")
        a(f"| 階の表記の種類 | {s_['kai_kazu']} |")
        a(f"| 開閉らしいリンク | {s_.get('news_kazu', 0)} 本（**開いていない**）|")
        a("")
        a("**店の名前は1つも入っていない。数と形だけ。**")
        a("")
    hito = [k for k in KAISHA if k.get("hito_ga_mita")]
    if hito:
        a("## 人が画面で見た分")
        a("")
        a("**この箱が見たものではない。** 人がブラウザで開いて確かめたこと。")
        a("")
        for k in hito:
            a(f"**{k['mei']}**")
            a("")
            a(k["hito_ga_mita"])
            a("")
    kaihei = [d for d in kekka if d["kaihei"]]
    if kaihei:
        a("## 企業側にも開閉の履歴がある")
        a("")
        a("**施設側だけの話ではなかった。** 会社が自分で開店・閉店を出している：")
        a("")
        for d in kaihei:
            a(f"- {d['mei']}：{d['kaihei']}")
        a("")
        a("**中身は見ていない。** 何件あるか、いつまで残るかは未確認。")
        a("")
    return "\n".join(a.__self__)


def main(argv=None):
    p = argparse.ArgumentParser(description="テナント企業側の関所。規約が先")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--id")
    p.add_argument("--ikkai", action="store_true",
                   help="**1回だけ構造を見る。** 継続取得の許可ではない。--id が要る")
    a = p.parse_args(argv)

    if a.ikkai and not a.id:
        p.error("--ikkai は --id と一緒に使う。**1社ずつしか見ない**")
    kouho = [k for k in KAISHA if not a.id or k["id"] == a.id]
    if a.limit:
        kouho = kouho[:a.limit]

    hiduke = today()
    kekka = []
    for i, k in enumerate(kouho):
        if i:
            time.sleep(WAIT)
        d = hitotsu(k, hiduke, ikkai=a.ikkai)
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
