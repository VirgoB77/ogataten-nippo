#!/usr/bin/env python3
"""地図データを取りに行く先の一覧を、手元のデータから作る。

法務省の登記所備付地図データ（G空間情報センター）は**市区町村ごと**に
1つの zip で置かれている。**うちが要るのは、届出が出ている市区町村だけ。**

    【データセット名】札幌市中央区（札幌法務局）登記所備付地図データ
    【リソース名】01101-4300-2026.Zip

    01101  全国地方公共団体コード（市区町村。**うちが持っている**）
    4300   登記所のコード（**持っていない**）
    2026   年度

**ファイル名を組み立てない。** 登記所コードを知らないし、
知っていても**当てに行くのは作文**（正本9節）。
目録（カタログ）を引いて、**向こうが書いた URL をそのまま使う。**

ここが作るのは「**どの市区町村が要るか**」の一覧だけ。
取りに行くのは workflow（この環境からは役所のサイトに出られない）。

**捕まえないもの**：その市区町村の地図データが実際に在るか。
向こうの留意事項に「一部、複数年分のデータがない市町村があります」とある。
**在るかどうかは、引いてみないと分からない。**
"""
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(HERE, "index.json")
REPORT = os.path.join(HERE, "data", "ref", "chizu-worklist.md")
LIST = os.path.join(HERE, "data", "ref", "chizu-worklist.json")


def worklist(records):
    """市区町村コードごとに、届出の件数と名前を返す。

    **コード無しの行も数える。** 黙って落とすと、
    「112市区町村ぶん取れば全部」と読めてしまう（6節）。
    """
    by_code, nashi = {}, 0
    for r in records:
        code = r.get("city_code")
        if not code:
            nashi += 1
            continue
        code = str(code)
        namae = (r.get("pref") or "") + (r.get("city") or "")
        h = by_code.setdefault(code, {"code": code, "name": namae, "n": 0})
        h["n"] += 1
        # **名前は、いちばん長いものを採る。** 途中から市区まで入った行がある
        if len(namae) > len(h["name"]):
            h["name"] = namae
    return by_code, nashi


def main():
    if not os.path.exists(INDEX):
        print(f"{INDEX} が無い。先に build_site.py")
        return 1
    with open(INDEX, encoding="utf-8") as f:
        recs = json.load(f)["records"]
    by_code, nashi = worklist(recs)

    by_pref = collections.defaultdict(list)
    for h in by_code.values():
        by_pref[h["code"][:2]].append(h)
    PREF = {"27": "大阪府", "28": "兵庫県"}

    lines = [
        "# 地図データを取りに行く先", "",
        "**このファイルは `chizu_worklist.py` が書く。** 手で直さない。", "",
        "法務省の登記所備付地図データ（G空間情報センター）は市区町村ごとに1つの zip。",
        "**うちが要るのは、届出が出ている市区町村だけ。**", "",
        f"| 都道府県 | 市区町村 | 届出 |", "|---|---:|---:|",
    ]
    for p in sorted(by_pref):
        hs = by_pref[p]
        lines.append(f"| {PREF.get(p, p)} | {len(hs):,} | {sum(h['n'] for h in hs):,} |")
    lines += [f"| **合計** | **{len(by_code):,}** | **{sum(h['n'] for h in by_code.values()):,}** |", ""]
    lines += [
        f"このほかに、**市区町村コードが付かなかった届出が {nashi:,}件**ある。",
        "**どの市区町村の地図データを引いても、この分は当たらない。**",
        "112市区町村ぶん取れば全部、とは読まないこと（6節）。", "",
        "## 引き方", "",
        "**ファイル名を組み立てない。** リソース名は",
        "`{市区町村コード}-{登記所コード}-{年度}.zip` の形だが、",
        "**登記所コードは手元に無い。** 当てに行くのは作文（9節）。",
        "目録を引いて、**向こうが書いた URL をそのまま使う。**", "",
        "## まだ分かっていないこと", "",
        "- 目録の引き方（API が在るか、ログインが要るか）",
        "- その市区町村の地図データが**実際に在るか**",
        "  （向こうの留意事項：「一部、複数年分のデータがない市町村があります」）",
        "- 落とした zip の中身が、地番まで当たるか", "",
        "## 市区町村ごと", "", "| コード | 市区町村 | 届出 |", "|---|---|---:|",
    ]
    for h in sorted(by_code.values(), key=lambda x: x["code"]):
        lines.append(f"| `{h['code']}` | {h['name']} | {h['n']:,} |")
    lines.append("")

    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    # **機械が読む形でも出す。** workflow はこちらを読む
    with open(LIST, "w", encoding="utf-8") as f:
        json.dump({"note": "chizu_worklist.py が書く。手で直さない",
                   "city_code_nashi": nashi,
                   "cities": sorted(by_code.values(), key=lambda x: x["code"])},
                  f, ensure_ascii=False, indent=1)
    print("\n".join(lines[:16]))
    print(f"→ {REPORT}\n→ {LIST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
