#!/usr/bin/env python3
"""G空間情報センターの目録を引いて、**返ってきたものをバイトのまま保存する。**

ここは**見に行くだけ。** 読み取りは書かない。理由は正本9節——

> **見本は実物から取る。作文しない。**

返事の形（CKAN の JSON がどのキーを持つか）を**こちらで決め打ちすると、
自分が書いた見本に合わせた読み取りができあがる。** 先に実物を1回取る。

分かっていること（2026-09-19、中島さんが画面を見て教えてくれた）——

    目録      https://www.geospatial.jp/ckan/  （CKAN）
    データセット例  .../ckan/dataset/houmusyouchizu-2026-1-1348
    リソース名     01101-4300-2026.Zip
                 01101 市区町村コード（**持っている**）
                 4300  登記所コード（**持っていない**）
                 2026  年度
    形式      XML（法務省の原本）と、G空間情報センターが機械的に変換した
             シェープファイル・GeoJSON。**変換は「保証するものではありません」**
    留意事項   **一部、複数年分のデータがない市町村がある**（合併・再編・統廃合）
             地震で測量成果が改定された地域は、座標が**地震発生前のもの**

`houmusyouchizu-2026-1-1348` の `1348` が何かは分かっていない。
**だから名前を組み立てない。** 探して、向こうが書いた URL を使う。

**守ること（3.4）**：robots を見る／同時1本／5秒以上あける／
429・503 が来たらその回は中止（押し込まない）。
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from common.fetch import UA, WAIT, check_robots, is_busy  # noqa: E402

BASE = "https://www.geospatial.jp/ckan"
SEARCH = BASE + "/api/3/action/package_search"
LIST = os.path.join(HERE, "data", "ref", "chizu-worklist.json")
INBOX = os.path.join(HERE, "inbox", "chizu", "search")
REPORT = os.path.join(HERE, "data", "ref", "chizu-recon.md")
TIMEOUT = 40


# 目録に並んでいるデータセットの名前（画面で見た実物）
#     【データセット名】札幌市中央区（札幌法務局）登記所備付地図データ
# **都道府県は入っていない。** こちらの `name` は「大阪府大阪市都島区」なので、
# そのまま投げると1件も当たらない（2026-09-19、実際に3件とも0件で返った）
_PREF = re.compile(r"^(..[都道府県]|.{2,3}県)")


def shichoson(name):
    """「大阪府大阪市都島区」→「大阪市都島区」。**都道府県だけ落とす。**

    市区町村の名前に「県」で始まるものは無い（県庁所在地でも市が付く）。
    だから頭の都道府県だけを外せば足りる。
    """
    return _PREF.sub("", name or "", count=1) or (name or "")


def ask(city_name):
    """1市区町村ぶんの目録を引く URL。**キーワードは画面に出ていた語をそのまま使う。**"""
    q = f'{shichoson(city_name)} 登記所備付地図データ'
    return SEARCH + "?" + urllib.parse.urlencode({"q": q, "rows": 50})


def mitsukatta(raw):
    """**いくつ見つかったか**だけ読む。中身は読まない。

    「返ってきた」と「見つかった」は別（2026-09-19、3件とも 200 で
    210バイト＝0件だったのに、記録は「目録が返ってきた 3」と書いていた）。

    返り値は件数。**読めなければ None。** 0 と None を混ぜない——
    0 は「向こうが無いと言った」、None は「こちらが読めなかった」。
    """
    try:
        return int(json.loads(raw.decode("utf-8"))["result"]["count"])
    except Exception:                              # noqa: BLE001
        return None


def get(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/json",
        "Accept-Language": "ja",
    })
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.status, r.headers.get("Content-Type", ""), r.read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=3,
                    help="引く市区町村の数。**既定は3。** 112本まとめて叩かない")
    args = ap.parse_args()

    if not os.path.exists(LIST):
        print(f"{LIST} が無い。先に chizu_worklist.py")
        return 1
    with open(LIST, encoding="utf-8") as f:
        cities = json.load(f)["cities"]

    ok, why = check_robots(SEARCH)
    if ok is False:
        print("robots.txt が拒否している。取りに行かない")
        return 1
    if ok is None:
        print(f"robots.txt が返らない（{why}）。相手が混んでいるので、この回は中止")
        return 1

    os.makedirs(INBOX, exist_ok=True)
    # **「相手が答えた」と「そもそも出られなかった」を分ける。**
    # 一緒にすると、こちらのネットワークの都合が
    # 「目録に無い」に見える（6節 unresolved / unobserved）
    totta, kotaeta_ga_dame, deraretakatta, yamete = [], [], [], []
    mokuhyo = cities[:args.limit]
    for i, c in enumerate(mokuhyo):
        if i:
            time.sleep(WAIT)
        url = ask(c["name"])
        try:
            status, ctype, raw = get(url)
        except urllib.error.HTTPError as e:
            if is_busy(e):
                # **押し込まない。** 残りは「見に行っていない」として数える
                print(f"{e.code} が返った（{c['name']}）。この回は中止")
                yamete = [x["code"] for x in mokuhyo[i:]]
                break
            print(f"× {c['code']} {c['name']} 相手が HTTP {e.code} と答えた")
            kotaeta_ga_dame.append(c["code"])
            continue
        except Exception as e:                      # noqa: BLE001
            # **相手は何も言っていない。** こちらが出られなかった
            print(f"× {c['code']} {c['name']} 出られなかった（{type(e).__name__}: {e}）")
            deraretakatta.append(c["code"])
            continue

        # **バイトのまま保存する。** 文字にすると戻らない形で壊れる（正本9節）
        michi = os.path.join(INBOX, f"{c['code']}.json")
        with open(michi, "wb") as f:
            f.write(raw)
        n_ken = mitsukatta(raw)
        totta.append((c["code"], n_ken))
        shirushi = "○" if n_ken else ("？" if n_ken is None else "×0件")
        print(f"{shirushi} {c['code']} {c['name']}  {status} {ctype} "
              f"{len(raw):,} バイト / 見つかった {n_ken} → {michi}")
        # **小さい返事は、そのままログに出す。** 実物を見ないと読み取りが書けない。
        # 大きいものは出さない（ログが読めなくなる）。中身は保存せずログだけ
        if len(raw) <= 4000:
            print("  ↳ " + raw.decode("utf-8", "replace"))

    mita = len(totta) + len(kotaeta_ga_dame) + len(deraretakatta)
    # **「返ってきた」と「見つかった」は別。** 200 が返っても 0件のことがある
    # （2026-09-19、3件とも 200・210バイト・0件。記録は「返ってきた 3」だった）
    lines = [
        "# 目録を引いた記録", "",
        "**このファイルは `chizu_recon.py` が書く。** 手で直さない。", "",
        "ここは**見に行っただけ**で、まだ1件も読み取っていない。",
        "返事の形を決め打ちすると、自分が書いた見本に合わせた読み取りになる（9節）。", "",
        f"| | 件数 |", "|---|---:|",
        f"| **見つかった**（1件以上） | {sum(1 for _, n in totta if n):,} |",
        f"| 返ってきたが **0件** | {sum(1 for _, n in totta if n == 0):,} |",
        f"| 返ってきたが **件数を読めなかった** | {sum(1 for _, n in totta if n is None):,} |",
        f"| 相手が「だめ」と答えた | {len(kotaeta_ga_dame):,} |",
        f"| **こちらが出られなかった** | {len(deraretakatta):,} |",
        f"| **混んでいて中止した** | {len(yamete):,} |",
        f"| **まだ引いていない** | {len(cities) - mita - len(yamete):,} |",
        f"| 要る市区町村（全部） | {len(cities):,} |", "",
        "**「まだ引いていない」を0にしない。** 0にすると、",
        "引いていないことが「無い」に見える（6節 `unobserved`）。", "",
        "**「相手が答えた」と「こちらが出られなかった」も分ける。** 一緒にすると、",
        "こちらのネットワークの都合が「目録に無い」に見える。", "",
        "## 次に見ること", "",
        f"`inbox/chizu/search/*.json` を**人が1つ開く。**",
        "リソースの URL がどのキーに入っているか、年度がいくつ並ぶか、",
        "**GeoJSON が本当に在るか**を実物で見てから、読み取りを書く。", "",
    ]
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("\n".join(lines[6:14]))
    print(f"→ {REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
