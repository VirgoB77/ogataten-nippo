#!/usr/bin/env python3
"""**利用規約のページを探して、1回だけ取る**段。**店舗情報は1件も取らない。**

## なぜこの段が要るか——輪になっていた

2026-09-21、関所をこう作った。

    利用規約が「取ってよい」になるまで、**1バイトも開かない**

**すると利用規約のページも開けない。** 人が読む材料を取りに行けないので、
**判定が永久に「未確認」のまま**になる。**輪になっていた。**

## 解き方：**2つの行為を分ける**

    ① 規約のページを**1回だけ**取る        関所は **robots.txt だけ**
    ② 店舗情報を**毎日**取る               関所は robots ＋ **人が読んだ結果**

**①を robots だけで判断してよい理由**：robots.txt は**機械への指示**で、
相手が「このページは機械が読んでよい」と書いている。
規約ページを robots が許可しているなら、**それを1回読むことは相手の指示に沿う。**

**①が通っても、②が通るわけではない。** 別の関所（4節の設計どおり）。

## 記録に本文を入れない

相手の規約は相手の著作物。**公開側の記録には1文字も入れない。**

入れるのは **「①〜⑤に当たる語が、本文に出てきたか」だけ。**
語の有無は**こちらが数えた事実**であって、相手の文章の複製ではない。

**そして「語が無い」は「禁止が無い」ではない。**
別の言い回しで書いてあることがある。**決めるのは人。** この段は場所を示すだけ。

## ①〜⑤の分け方（統括の整理・2026-09-21）

    ① 著作物（写真・文章・画像）の複製・転載の禁止
    ② 「掲載内容」「掲載情報」など**広く**対象にした複製・転用の禁止
    ③ 商用・営利利用の制限
    ④ **スクレイピング・クローリング・自動取得**の明示的禁止
    ⑤ **データベース化・蓄積・再利用**の明示的禁止

**①②だけで「機械取得の拒否」に倒さない。** 著作物の転載禁止と、
店舗名・開店日という**事実の観測**は、別の問い。
**逆に、④⑤が見つからないことだけを理由に「許可」にもしない。**
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
from tenant_recon import shitami  # noqa: E402  **形の測り方は1か所に置く**

INBOX = HERE / "inbox" / "yakusoku"
KIROKU = HERE / "data" / "ref" / "yakusoku-get.md"
JSON_SAKI = HERE / "data" / "ref" / "yakusoku-get.json"

LINK = re.compile(r'<a\s[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
SCRIPT = re.compile(r"<(script|style)\b.*?</\1>", re.I | re.S)
# 見出し。**人が読む場所を示すために拾う。本文は拾わない**
MIDASHI = re.compile(r"<h([1-6])\b([^>]*)>(.*?)</h\1>", re.I | re.S)
# 見出しに `id` が付いていれば、**アンカー付きURLを作れる**——
# 人がそのまま開けば、その見出しの位置に飛ぶ
ID_ATTR = re.compile(r'\bid\s*=\s*["\']([^"\']+)["\']', re.I)

# 規約らしいリンクの語。**強い順に並べる。**
#
# 2026-09-21、並べずに「最初に当たったもの」を取ったら、
# **ソーシャルメディアポリシーを拾った。**「著作権」を含んでいたため。
# **店舗情報のページに適用される規約ではない。**
#
# **サイト全体の約束を指す語を上に、章の名前でしかない語を下に置く。**
# 「著作権」「免責」は**規約の中の章の名前**なので、単独で当てると別物を拾う。
ARIKA = (
    # 強い：サイト全体の約束
    "利用規約", "サイトポリシー", "ご利用にあたって", "ご利用について",
    "サイトのご利用", "ウェブサイトのご利用", "ご利用条件", "Terms of Use", "Terms",
    # 弱い：章の名前。**ほかに無いときだけ**
    "著作権", "免責", "禁止事項",
)
# **これを含むリンクは、サイト全体の約束ではない。** 下に落とす
YOWAI = ("ソーシャルメディア", "SNS", "会員", "ポイント", "返品", "配送",
         "特定商取引", "個人情報", "プライバシー", "クッキー", "Cookie",
         "アプリ", "メルマガ", "採用")

# ①〜⑤に当たる語。**本文は記録に入れない。出たかどうかだけ数える**
KOU = (
    ("1", "著作物の複製・転載",
     ("著作権", "著作物", "無断転載", "無断複製", "転載を禁", "複製を禁")),
    ("2", "掲載内容を広く対象にした複製・転用",
     ("掲載内容", "掲載情報", "本サイトの内容", "当サイトの内容", "当ウェブサイトの内容",
      "その他掲載", "二次利用", "転用")),
    ("3", "商用・営利利用の制限",
     ("商用", "営利", "商業目的", "営業目的")),
    ("4", "**自動取得の明示的禁止**",
     ("スクレイピング", "クローリング", "クロール", "クローラ", "自動取得", "自動収集",
      "データマイニング", "ロボット", "bot", "巡回プログラム", "自動的に取得")),
    ("5", "**データベース化の明示的禁止**",
     ("データベース", "蓄積", "再利用", "複製物の作成", "集積")),
)


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
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, r.headers.get("Content-Type", ""), r.read()
    except urllib.error.HTTPError as e:
        if is_busy(e):
            raise Konde(f"相手が混んでいると言っている（HTTP {e.code}）") from e
        raise


def arika(base, raw, ctype):
    """トップから規約らしいリンクを拾う。**読まない。在りかだけ。**

    **強い順に並べて返す。** 1本目を取りに行くので、並べ方がそのまま
    「どれを規約とみなすか」になる。**別物を拾うと、そこから先が全部ずれる。**
    """
    honbun, _m = decode_html(raw, ctype)
    de, mita = [], set()
    for u, naka in LINK.findall(honbun):
        t = moji(naka)
        atta = [g for g in ARIKA if g in t]
        if not atta:
            continue
        saki = urllib.parse.urljoin(base, html.unescape(u))
        if saki in mita:
            continue
        mita.add(saki)
        # 小さいほど強い。**弱い語を含むものは、後ろへ回す**
        tsuyosa = min(ARIKA.index(g) for g in atta)
        if any(g in t for g in YOWAI):
            tsuyosa += 100
        de.append({"text": t[:40], "url": saki, "tsuyosa": tsuyosa,
                   "atta": atta[:3]})
    de.sort(key=lambda x: x["tsuyosa"])
    return de


def midashi_de_wakeru(mieru):
    """見出しでページを区切る。**返すのは見出しの文字と位置だけ。本文は返さない。**

    人が読む場所を示すために要る（2026-09-21）。
    統括が規約の内容と適用範囲を整理するので、**どこを読めばよいか**が要る。
    **本文そのものは渡さない。**見出しと、あればアンカー付きURL。
    """
    de = []
    for m in MIDASHI.finditer(mieru):
        t = moji(m.group(3))
        if not t:
            continue
        a = ID_ATTR.search(m.group(2) or "")
        de.append({"lv": int(m.group(1)), "midashi": t[:60],
                   "anchor": a.group(1) if a else "", "at": m.end()})
    return de


def doko_ni_atta(mieru, midashi, go):
    """その語が**どの見出しの下**に出たかを返す。**前後の文は返さない。**"""
    de = []
    for m in re.finditer(re.escape(go), mieru):
        i = m.start()
        mae_ = [h for h in midashi if h["at"] <= i]
        h = mae_[-1] if mae_ else None
        de.append({"midashi": h["midashi"] if h else "（見出しの前）",
                   "anchor": h["anchor"] if h else ""})
    return de


# **①〜⑤より細かく分ける語**（統括の依頼・2026-09-21）。
# 「複製」と「自動取得」と「DB化」は、同じ①に入れると**別の禁止が1つに見える。**
KOMAKA_GO = ("複製", "転載", "転用", "二次利用", "改変", "再配布",
             "自動取得", "クローリング", "クロール", "スクレイピング",
             "ロボット", "自動的", "データベース", "蓄積", "商用", "営利")

# **何を対象にした禁止か。** 同じ文に出た語を拾う。**文そのものは記録に入れない**
TAISHOU_GO = ("デジタル素材", "コンテンツ", "情報", "画像", "文章", "イラスト",
              "写真", "映像", "音声", "データ", "素材", "記事", "ロゴ", "商標",
              "本サイト", "当サイト", "ホームページ", "ページ", "本ウェブサイト")

# **ページそのものの利用と、そこから確かめた事実の記録を、分ける文言が在るか。**
# 在れば「区別できる」。**無ければ「明示なし」。許可とも拒否とも読まない**
JIJITSU_GO = ("事実", "営業状況", "在籍", "出店", "退店", "店舗名", "テナント名",
              "営業時間", "開店", "閉店", "統計", "調査")

BUN = re.compile(r"[^。\n]{4,200}[。\n]")


def komaka(raw, ctype):
    """**禁止の中身を、語ごとに分けて数える**（統括の依頼・2026-09-21）。

    返すのは**語・回数・どの見出しの下か・同じ文に出た対象語**まで。
    **文そのものは返さない**——入れた時点で相手の文章を写したことになる。

    文は別に返す（`bun`）。**そちらは金庫にだけ置く。公開側には入れない。**
    """
    honbun, _m = decode_html(raw, ctype)
    mieru = SCRIPT.sub(" ", honbun)
    hontai = moji(mieru)
    midashi = midashi_de_wakeru(mieru)

    bunshou = [b.strip() for b in BUN.findall(hontai)]
    de, hirotta = [], []
    for go in KOMAKA_GO:
        n = hontai.count(go)
        if not n:
            de.append({"go": go, "kazu": 0, "basho": [], "taishou": [],
                       "jijitsu": []})
            continue
        ataru = [b for b in bunshou if go in b]
        taishou = sorted({g for b in ataru for g in TAISHOU_GO if g in b})
        jijitsu = sorted({g for b in ataru for g in JIJITSU_GO if g in b})
        basho = sorted({(x["midashi"], x["anchor"])
                        for x in doko_ni_atta(mieru, midashi, go)})
        de.append({"go": go, "kazu": n,
                   "basho": [{"midashi": a, "anchor": b} for a, b in basho][:4],
                   "taishou": taishou[:8], "jijitsu": jijitsu[:8]})
        hirotta += ataru
    # **区別できる文言が在るか。** 禁止の語と事実の語が同じ文に出ているか
    kubetsu = any(d["jijitsu"] for d in de if d["kazu"])
    return {"go": de, "kubetsu": kubetsu,
            "bun": sorted(set(hirotta))}      # **金庫にだけ置く**


def kazoeru_kou(raw, ctype):
    """①〜⑤に当たる語が出たかを数える。**本文は返さない。**

    返すのは**語そのものと回数**まで。**前後の文は入れない**——
    入れた時点で相手の文章の一部を写したことになる（2026-09-21）。
    """
    honbun, _m = decode_html(raw, ctype)
    mieru = SCRIPT.sub(" ", honbun)      # タグは残す（見出しの位置を見るため）
    hontai = moji(mieru)
    midashi = midashi_de_wakeru(mieru)
    de = []
    for no, mei, go in KOU:
        deta = [(g, hontai.count(g)) for g in go if g in hontai]
        # **どの見出しの下に出たか。**人が読む場所を示すため。本文は入れない
        basho = {}
        for g, _n in deta:
            for x in doko_ni_atta(mieru, midashi, g):
                k = (x["midashi"], x["anchor"])
                basho.setdefault(k, set()).add(g)
        de.append({"no": no, "mei": mei,
                   "atta": bool(deta),
                   "go": sorted(deta, key=lambda x: -x[1])[:5],
                   "kazu": sum(n for _g, n in deta),
                   "basho": [{"midashi": k[0], "anchor": k[1],
                              "go": sorted(v)} for k, v in basho.items()][:6]})
    # **日本語がほとんど無いページで①〜⑤が0なのは、当たり前。**
    # 探している語が全部日本語だから、**英語のページでは必ず0になる。**
    # **それを「禁止が無い」と読んではいけない**（2026-09-21、実際に起きた）。
    ja = len(re.findall(r"[぀-ゟ゠-ヿ一-鿿]", hontai))
    nihongo = (ja / len(hontai)) if hontai else 0.0
    return {"kou": de, "moji": len(hontai),
            "nihongo": round(nihongo, 3),
            "midashi": [{"lv": h["lv"], "midashi": h["midashi"],
                         "anchor": h["anchor"]} for h in midashi][:30]}


def hitotsu(k, hiduke):
    d = {"id": k["id"], "mei": k["mei"], "top": k["top"], "hi": hiduke,
         "arika": [], "yonda": None, "note": "", "hiraita": False}

    # **人が規約のURLを渡していれば、探さずに直に取りに行く。**
    # 店舗一覧のフッターを JS で描いている相手には、探しても届かない（2026-09-21）
    if k.get("yakusoku_url"):
        d["hito_ga_watashita"] = True
        d["arika"] = [{"text": "（人が渡した）", "url": k["yakusoku_url"],
                       "tsuyosa": -1, "atta": []}]
        return _yomu(d, k["yakusoku_url"], k["id"], hiduke)

    ok, why = check_robots(k["top"])
    d["robots_top"] = {True: "許可", False: "拒否", None: "分からない"}[ok]
    if ok is not True:
        # **robots が通らなければ、規約ページも取りに行かない**
        d["note"] = f"トップの robots が{'拒否' if ok is False else '分からない'}：{why}"
        return d

    time.sleep(WAIT)
    try:
        _s, ctype, raw = get(k["top"])
    except Konde as e:
        d["note"] = f"{e}。その回は中止"
        return d
    except Exception as e:                                        # noqa: BLE001
        d["note"] = f"トップが開けなかった {type(e).__name__}: {e}"
        return d
    # **開いたことを記録に残す。**「開いて0本だった」と「開いていない」は別
    # （2026-09-21、相手が 503 を返した回が「0本」と同じ顔で並んだ）
    d["hiraita"] = True
    d["arika"] = arika(k["top"], raw, ctype)
    if not d["arika"]:
        # **0本は「無い」ではない。** 語の一覧が足りない／画像やJSで出していることがある。
        # **どれなのかを分けるために、ページの形も測って残す**（2026-09-21）
        d["katachi"] = shitami(k["top"], raw, ctype)
        d["note"] = "規約らしいリンクが0本。**無いとは限らない**（語の一覧が足りない／JSで出している）"
        return d

    # **1ページだけ取る。** いちばん上の1本。残りは記録に在りかだけ残す
    return _yomu(d, d["arika"][0]["url"], k["id"], hiduke)


def _yomu(d, saki_url, sid, hiduke):
    """規約のページを1回取って、①〜⑤の語と見出しを記録する。**本文は残さない。**"""
    ok2, why2 = check_robots(saki_url)
    d["robots_yakusoku"] = {True: "許可", False: "拒否", None: "分からない"}[ok2]
    if ok2 is not True:
        d["note"] = f"規約ページの robots が{'拒否' if ok2 is False else '分からない'}：{why2}"
        return d

    time.sleep(WAIT)
    try:
        _s, ctype2, raw2 = get(saki_url)
    except Konde as e:
        d["note"] = f"{e}。その回は中止"
        return d
    except Exception as e:                                        # noqa: BLE001
        d["note"] = f"規約ページが開けなかった {type(e).__name__}: {e}"
        return d

    saki = INBOX / sid
    saki.mkdir(parents=True, exist_ok=True)
    (saki / f"yakusoku-{hiduke}.html").write_bytes(raw2)
    d["yonda"] = dict(kazoeru_kou(raw2, ctype2), url=saki_url)

    # **語ごとに細かく分ける**（統括の依頼・2026-09-21）。
    # **文そのものは金庫にだけ置く。** 公開側には1文字も入れない——
    # 相手の規約は相手の著作物なので、**分析のために写した分も外に出さない**
    km = komaka(raw2, ctype2)
    bun = km.pop("bun")
    d["komaka"] = km
    if bun:
        (saki / f"jobun-{hiduke}.md").write_text(
            "\n".join([
                "# 該当した文（**金庫にだけ置く。公開側には入れない**）", "",
                f"読んだページ：{saki_url}", "",
                "**人が読むための写し。** 判定はしない。",
                "**この見出しの下の文は、相手の著作物。** 外に出さない。", "",
            ] + [f"- {b}" for b in bun]), encoding="utf-8")
    return d


def houkoku(kekka, hiduke):
    a = [].append
    a("# 利用規約を探して1回取った記録")
    a("")
    a(f"{hiduke} に走らせた。**店舗情報は1件も取っていない。"
      f"規約の本文も1文字も入っていない。**")
    a("")
    a("**表には、相手ごとの「最後に見た回」が並ぶ。** この回で見ていない相手も残る。")
    a("**「見ていない」と「変わっていない」を、記録の上でも分けるため。**")
    a("")
    hito = [d for d in kekka if d.get("hito_ga_watashita")]
    if hito:
        a("**この回は、人が渡した規約のURLを直に読んだ。**")
        a("**フッターを探していない。URLも作り変えていない。**")
        a("")
    a("**この段の関所は robots.txt だけ。** 規約ページを1回読むことは、")
    a("相手が robots で「機械が読んでよい」と言っているページを読むこと。")
    a("**①が通っても、店舗情報を毎日取ってよいことにはならない**（関所が別）。")
    a("")
    a("入っているのは**①〜⑤に当たる語が出たかどうかと、どの見出しの下に出たか**だけ。")
    a("**規約の本文は1文字も入っていない。**人が読む場所を示すところまで。")
    a("**「語が無い」は「禁止が無い」ではない。** 別の言い回しのことがある。**決めるのは人。**")
    a("")
    a("| 相手 | 見た日 | robots | 規約の在りか | ①著作物 | ②掲載内容 | ③商用 "
      "| **④自動取得** | **⑤DB化** |")
    a("|---|---|---|---|---|---|---|---|---|")
    for d in kekka:
        y = d.get("yonda")
        hi = d.get("hi") or "—"
        # **人が渡した回は `robots_top` を見ていない。** 見たのは渡されたURLの robots。
        # そこを出さないと、**確かめたことが記録に出ない**（2026-09-21）
        rb = d.get("robots_yakusoku") or d.get("robots_top") or "—"
        if not y:
            # **「開いて0本だった」と「開いていない」を、同じ顔で出さない。**
            # 相手が混んでいた回・届かなかった回は、0本の側に入れない（9節）
            ar = (f"{len(d['arika'])}本"
                  if d["arika"] or d.get("hiraita") else "**—（開いていない）**")
            a(f"| {d['mei']} | {hi} | {rb} "
              f"| {ar} | — | — | — | — | — |")
            continue
        nh = y.get("nihongo")
        # **日本語がほとんど無いページは、「なし」と書かない。**「読めていない」と書く
        if nh is not None and nh < 0.10:
            m = {x["no"]: "**日本語なし**" for x in y["kou"]}
        else:
            m = {x["no"]: ("**あり**" if x["atta"] else "なし") for x in y["kou"]}
        a(f"| [{d['mei']}]({y['url']}) | {hi} | {rb} "
          f"| {len(d['arika'])}本 | {m['1']} | {m['2']} | {m['3']} | {m['4']} | {m['5']} |")
    a("")
    a("**④⑤が「なし」でも、取ってよいことにはならない。**")
    a("**①②が「あり」でも、機械取得の拒否とは限らない。**")
    a("著作物の転載禁止と、店舗名・開店日という**事実の観測**は、別の問い。")
    a("")
    for d in kekka:
        y = d.get("yonda")
        if not y:
            if d.get("note"):
                a(f"- {d['mei']}：{d['note']}")
            ka = d.get("katachi") or {}
            if ka:
                ko = ka.get("kotei_url") or {}
                a(f"    - このページの形：JS を落とす前 {ka['zenbu_moji']:,} 文字 → "
                  f"落とした後 **{ka['mieru_moji']:,} 文字**"
                  f"／同じ形のリンク {ko.get('kazu', 0)} 本")
            for x in d.get("arika") or []:
                a(f"    - 規約らしいリンク（取っていない）：[{x['text']}]({x['url']})")
            continue
        a(f"### {d['mei']}")
        a("")
        a(f"読んだページ：{y['url']}（{y['moji']:,} 文字）")
        a("")
        nh = y.get("nihongo")
        if nh is not None and nh < 0.10:
            a(f"> ⚠️ **このページは日本語がほとんど無い**（日本語の字が {nh:.1%}）。")
            a("> **探している語は全部日本語なので、①〜⑤が0になるのは当たり前。**")
            a("> **「禁止が無い」ではなく「日本語の規約を読んでいない」。**")
            a("> 日本語版の規約ページが別にあるか、人が確かめる。")
            a("")
        for x in y["kou"]:
            if not x["atta"]:
                a(f"- {x['no']} {x['mei']}：**出てこなかった**")
                continue
            go = "、".join(f"「{g}」×{n}" for g, n in x["go"])
            a(f"- {x['no']} {x['mei']}：{go}")
            for b in x.get("basho") or []:
                saki = (f"{y['url']}#{b['anchor']}" if b["anchor"] else y["url"])
                a(f"    - 見出し「{b['midashi']}」の下"
                  f"（{'、'.join(b['go'])}）→ [ここを読む]({saki})")
        a("")
        km = d.get("komaka")
        if km:
            a("**語ごとに分けた**（統括の依頼・2026-09-21）。"
              "**文そのものは入っていない**")
            a("")
            a("| 語 | 回数 | どの見出しの下か | 同じ文にあった**対象** "
              "| 同じ文にあった**事実の語** |")
            a("|---|---:|---|---|---|")
            for g in km["go"]:
                if not g["kazu"]:
                    continue
                ba = "／".join(x["midashi"] for x in g["basho"]) or "—"
                ta = "、".join(g["taishou"]) or "—"
                ji = "、".join(g["jijitsu"]) or "**—**"
                a(f"| **{g['go']}** | {g['kazu']} | {ba} | {ta} | {ji} |")
            a("")
            nakatta = [g["go"] for g in km["go"] if not g["kazu"]]
            if nakatta:
                a(f"**出てこなかった語**：{'、'.join(nakatta)}")
                a("")
                a("**「語が無い」は「禁止が無い」ではない。** 別の言い回しのことがある。")
                a("")
            if km["kubetsu"]:
                a("**ページそのものの利用と、そこから確かめた事実の記録を、"
                  "分ける文言が在った。** 上の「事実の語」の列を読む。")
            else:
                a("**ページそのものの利用と、そこから確かめた事実の記録を、"
                  "分ける文言は見当たらなかった（明示なし）。**")
                a("**許可とも拒否とも読まない**（統括の指示・2026-09-21）。")
            a("")
        if y.get("midashi"):
            a("**このページの見出し**（人が読む場所を探すため。本文は入っていない）")
            a("")
            for h in y["midashi"]:
                saki = (f"{y['url']}#{h['anchor']}" if h["anchor"] else "")
                a(f"  - {'#' * h['lv']} {h['midashi']}"
                  + (f" → [{saki}]({saki})" if saki else ""))
            a("")
        if len(d["arika"]) > 1:
            a("**ほかに規約らしいリンク（取っていない）。**")
            a("**1本目が本当に店舗情報に効く規約かは、人が決める。**")
            a("")
            for x in d["arika"][1:6]:
                a(f"  - [{x['text']}]({x['url']})")
            a("")
    return "\n".join(a.__self__)


# **運営会社。** 施設でも、テナント企業でもない三つ目の相手（2026-09-21）。
#
# 施設の公式サイトは規約で止まったが、**運営会社の広報発表は別の主体・別のドメイン。**
# 広報発表は**報道されることを前提に出される**ので、扱いが違う可能性がある。
# **ただし同じ企業グループなので、同じ方針かもしれない。確かめるまで分からない。**
#
# URLは検索で出た**一覧ページ**。PDFではなくHTMLを見る（フッターの規約を見るため）。
UNEI = (
    {"id": "hhp", "mei": "阪急阪神不動産",
     "top": "https://www.hhp.co.jp/news/"},
    {"id": "hankyu-hanshin-hd", "mei": "阪急阪神ホールディングス",
     "top": "https://www.hankyu-hanshin.co.jp/release/"},
)


def taisho(nani):
    """相手の一覧を返す。**施設・企業・運営会社・電力で同じ段を使う。**

    一覧は各正本から読む。**ここで URL を作文しない。**
    """
    if nani == "denryoku":
        # **1回見る段が拾った「規約の在りか」から読む**（2026-09-21）。
        # 向こうがページに書いたリンクなので、**こちらが組み立てていない。**
        # 見つからなければ**0件で返す。** 思い出して並べない
        michi = HERE / "data" / "ref" / "teiden-ikkai.json"
        if not michi.exists():
            return []
        try:
            kekka = json.loads(michi.read_text(encoding="utf-8")).get("kekka", [])
        except (ValueError, TypeError):
            return []
        de, mita = [], set()
        for d in kekka:
            ya = (d.get("yakusoku") or [])
            if not ya:
                continue
            # **いちばん強い1本だけ。** 弱い語まで取りに行かない（下の ARIKA の順）
            url = ya[0].get("url") or ""
            host = urllib.parse.urlsplit(url).netloc
            if not url or host in mita:
                continue
            mita.add(host)
            de.append({"id": host, "mei": d.get("title") or host,
                       "top": "", "yakusoku_url": url})
        return de
    if nani == "unei":
        return [dict(u, yakusoku_url="") for u in UNEI]
    if nani == "kaisha":
        from tenanto_kanmon import KAISHA, YAKUSOKU_URL
        return [{"id": k["id"], "mei": k["mei"],
                 "top": k.get("ichiran") or "",
                 "yakusoku_url": YAKUSOKU_URL.get(k["id"], "")}
                for k in KAISHA
                if k.get("ichiran") or YAKUSOKU_URL.get(k["id"])]
    from floor_kanmon import KOUHO
    return [{"id": k["id"], "mei": k["mei"], "top": k["top"]} for k in KOUHO]


def main(argv=None):
    p = argparse.ArgumentParser(description="利用規約を探して1回取る。店舗情報は取らない")
    p.add_argument("--taisho", choices=("kaisha", "shisetsu", "unei", "denryoku"),
                   default="kaisha")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--id")
    p.add_argument("--url", default="",
                   help="**人が渡した規約のURL。** --id と一緒に使う。"
                        "探さずに直に取りに行く。**作り変えない**")
    a = p.parse_args(argv)

    if a.url and not a.id:
        p.error("--url は --id と一緒に使う。**どの相手のものか分からなくなる**")

    kouho = [k for k in taisho(a.taisho) if not a.id or k["id"] == a.id]
    if a.url:
        for k in kouho:
            k["yakusoku_url"] = a.url      # **渡された文字列のまま**
    if a.limit:
        kouho = kouho[:a.limit]

    hiduke = today()
    kekka = []
    for i, k in enumerate(kouho):
        if i:
            time.sleep(WAIT)
        d = hitotsu(k, hiduke)
        y = d.get("yonda")
        print(f"{'読めた' if y else '—    '} {d['mei']}  "
              f"{d.get('note') or (y and y['url']) or ''}")
        kekka.append(d)

    # **前の回を消さない。** 1社ずつ回すと、書き直しで前の社の結果が消えていた
    # （2026-09-21）。**相手ごとに最後の1回を持って、そこから記録を組み直す。**
    # 「変わっていない」と「まだ見ていない」を、記録の上でも分けるため
    dai = {}
    if JSON_SAKI.exists():
        try:
            dai = {d["id"]: d for d in
                   json.loads(JSON_SAKI.read_text(encoding="utf-8")).get("kekka", [])}
        except (ValueError, KeyError, TypeError):
            dai = {}                       # 壊れていたら作り直す。**黙って0件にしない**
    for d in kekka:
        dai[d["id"]] = d
    zenbu = [dai[i] for i in sorted(dai)]

    KIROKU.parent.mkdir(parents=True, exist_ok=True)
    KIROKU.write_text(houkoku(zenbu, hiduke), encoding="utf-8")
    JSON_SAKI.write_text(
        json.dumps({"hi": hiduke, "taisho": a.taisho, "kekka": zenbu},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{KIROKU} に書いた")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
