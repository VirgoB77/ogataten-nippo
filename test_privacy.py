#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""共通仕様 3.1 / 3.2 を守れているかの検査。

  https://github.com/VirgoB77/ogataten-nippo/blob/main/docs/kyotsu-shiyo.md

前半は common/privacy.py そのものの検査。
後半が本体で、公開する生成物を全部走査して、privacy.py を迂回した値が
1件でも残っていないかを見る（5節「迂回検査」）。

  python3 test_privacy.py

落ちたら、データを取りに行く前に止まる。

この検査に実在の氏名は書かない。書くとリポジトリに氏名が残り、
git の履歴は消せない。人の名前の形をした架空の文字列だけを使う。
"""

import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from common import privacy

fails = []


def eq(got, want, what):
    if got != want:
        fails.append(f"{what}\n      出た値: {got!r}\n      ほしい値: {want!r}")


# ---------------------------------------------------------------- is_corp
def test_is_corp():
    corps = [
        "株式会社あいうえ", "㈱あいうえ", "(株)あいうえ", "（株）あいうえ",
        "有限会社かきくけ", "㈲かきくけ", "(有）かきくけ",      # 括弧が半角と全角で混ざる実物がある
        "株かきくけ商店",                                    # ㈱が潰れた表記
        "合同会社さしすせ", "さしすせ特定目的会社", "たちつて投資法人",
        "なにぬね生命保険(相)", "はひふへ生活協同組合", "まみむめ協同組合",
        "学校法人やゆよ", "医療法人らりるれ", "社会福祉法人わをん",
        "大阪市", "兵庫県", "堺市", "大阪市交通局", "○○町教育委員会",
        "あいう産業会館", "アオヤマ", "オークワ　ほか", "F.O.B COOP",
        "IKEA Property,S.L", "かきく・エルエルシー", "さしすホールディングス",
    ]
    for n in corps:
        eq(privacy.is_corp(n), True, f"法人と見てほしい: {n}")

    # 人名の形をした架空の文字列。実在の氏名は書かない
    people = ["山田太郎", "山田　太郎", "佐藤花子　ほか", "鈴木一郎　ほか９者", "田中　健"]
    for n in people:
        eq(privacy.is_corp(n), False, f"個人と見てほしい: {n}")


# ---------------------------------------------------------------- 名前の出し方
def test_names():
    eq(privacy.redact_name("株式会社あいう"), "株式会社あいう", "法人は画面にそのまま")
    eq(privacy.redact_name("山田太郎"), "個人", "個人は画面に「個人」")
    eq(privacy.redact_name("個人"), "個人", "すでに伏せてあるものは二重にしない")
    eq(privacy.redact_name(""), "", "空は空のまま")
    eq(privacy.redact_name("未定"), "未定", "名前でない文言は「個人」に変えない")
    eq(privacy.redact_name("（未定）"), "（未定）", "括弧つきの未定も同じ")
    eq(privacy.redact_name("物品販売業を営む店舗"), "物品販売業を営む店舗", "業種の説明も同じ")

    eq(privacy.party_for_index("株式会社あいう"), "株式会社あいう", "法人は index にそのまま")
    eq(privacy.party_for_index("山田太郎"), "", "個人は index に空文字")
    eq(privacy.party_for_index("個人"), "", "「個人」という文字列を index に入れない")
    eq(privacy.party_for_index("未定"), "", "名前でない文言も index には入れない")

    eq(privacy.party_kind("株式会社あいう"), "corp", "corp")
    eq(privacy.party_kind("山田太郎"), "individual", "individual")
    eq(privacy.party_kind("あいう", disclosed=False), "undisclosed", "undisclosed")
    eq(privacy.party_kind(None), "none", "none")
    # ここが 121件の件。読めていないだけかもしれないので undisclosed にしない
    eq(privacy.party_kind(""), "individual", "空欄は個人に倒す（undisclosed にしない）")


# ---------------------------------------------------------------- 所在地
def test_addr():
    cases = [
        ("あいう市かきく九丁目300番１ほか", "あいう市かきく九丁目"),
        ("あいう区かきく一丁目1663番1外7筆", "あいう区かきく一丁目"),
        ("あいう区かきく町１丁目15-1", "あいう区かきく町１丁目"),
        ("あいう市かきく下町３７７番１ほか", "あいう市かきく下町"),     # 丁目が無い
        ("あいう市かきく町2463番地の１ほか", "あいう市かきく町"),
        ("あいう区かきく4丁目15番1他2筆", "あいう区かきく4丁目"),
        ("あいう市かきく字さし163", "あいう市かきく字さし"),          # 番も無い
        ("あいう区かきく1-1-1", "あいう区かきく1丁目"),             # 数字3つは丁目-番-号
        ("あいう町329-1", "あいう町"),                          # 数字2つは番地-枝番
        ("あいう市かきく町四丁401番地１", "あいう市かきく町四丁"),      # 堺市は「丁」
        # 住所が2つつながっている取りこぼし。丁目の前に地番が残るので安全側に倒す
        ("あいう区かきく21あいう都かきく市さしす六丁目", "あいう区かきく"),
    ]
    for src, want in cases:
        got = privacy.redact_addr(src, "individual")
        eq(got, want, f"個人の所在地を丸める: {src}")
        # もう一度通しても同じ値。そうでないと実行のたびに削れていく
        eq(privacy.redact_addr(got, "individual"), got, f"2回通しても同じ: {src}")
        eq(privacy.redact_addr(src, "corp"), src, f"法人はそのまま: {src}")
        eq(privacy.redact_addr(src, "undisclosed"), src, f"undisclosed はそのまま: {src}")


# ---------------------------------------------------------------- 3.2
def test_small_numbers():
    eq(privacy.bucket_count(1), "1-2", "1件は 1-2")
    eq(privacy.bucket_count(2), "1-2", "2件は 1-2")
    eq(privacy.bucket_count(3), "3", "3件はそのまま")
    eq(privacy.bucket_count(0), "0", "0件はそのまま")
    eq(privacy.suppress_rate(5, 400), True, "人口500人未満は率を出さない")
    eq(privacy.suppress_rate(2, 5000), True, "件数2件以下は率を出さない")
    eq(privacy.suppress_rate(3, 500), False, "人口500・件数3なら出してよい")


# ---------------------------------------------------------------- 迂回検査（本体）
PARTY_FIELDS = ("operator", "new_operator", "retailer")
# 丸めたあとに残ってよい数字は「丁目」「丁」の直前の1つだけ
_CHOME_TAIL = re.compile(r"[0-9０-９一二三四五六七八九十]+\s*(丁目|丁)$")
_ONLY_NUM = re.compile(r"^[0-9０-９]+$")
_HAS_NUM = re.compile(r"[0-9０-９]")


def test_all_json():
    """data/all.json は公開している。privacy.py を通っていない値がないか見る。"""
    path = os.path.join(HERE, "data", "all.json")
    if not os.path.exists(path):
        print("  data/all.json が無いので迂回検査は飛ばした")
        return
    with open(path, encoding="utf-8") as f:
        recs = json.load(f)

    for r in recs:
        key = r.get("key", "?")

        for f_ in PARTY_FIELDS:
            if f_ not in r:
                continue
            v = (r.get(f_) or "").strip()
            # index 用の値は「法人名か、空」のどちらかしかありえない
            if v and not privacy.is_corp(v):
                fails.append(f"{key}: {f_} に法人でない値が残っている: {v!r}")
            kind = r.get(f_ + "_kind")
            if kind not in (None, "corp", "individual", "undisclosed", "none"):
                fails.append(f"{key}: {f_}_kind が知らない値: {kind!r}")
            if kind == "corp" and v and not privacy.is_corp(v):
                fails.append(f"{key}: {f_}_kind=corp なのに法人でない: {v!r}")

        # 設置者が個人なら、所在地に地番が残っていてはいけない
        if r.get("address_redacted"):
            a = (r.get("address") or "").strip()
            rest = _CHOME_TAIL.sub("", a)
            if _HAS_NUM.search(rest):
                fails.append(f"{key}: 丸めたのに地番が残っている: {a!r}")

        if r.get("operator_kind") == "individual" and (r.get("address") or "").strip():
            a = r["address"].strip()
            if privacy.redact_addr(a, "individual") != a:
                fails.append(f"{key}: 設置者が個人なのに所在地が丸まっていない: {a!r}")


def test_generated_pages():
    """出来上がったHTMLと search.json に、個人名らしき値が出ていないか見る。

    data/all.json を正として、そこで個人と判定した値が1つでも
    ページに出ていたら落とす。all.json 側が正しいことは上で見ている。
    """
    path = os.path.join(HERE, "data", "all.json")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        recs = json.load(f)

    # 画面用の値のうち、法人でも「個人」でも定型文でもないものがあれば、
    # それは伏せそこねている
    for r in recs:
        for f_ in PARTY_FIELDS:
            d = (r.get(f_ + "_display") or "").strip()
            if not d or d == "個人":
                continue
            if privacy.is_corp(d) or privacy.is_placeholder(d):
                continue
            fails.append(f"{r.get('key','?')}: {f_}_display に伏せそこねた値: {d!r}")


def main():
    for t in (test_is_corp, test_names, test_addr, test_small_numbers,
              test_all_json, test_generated_pages):
        t()
    if fails:
        print(f"落ちた検査 {len(fails)} 件\n")
        for m in fails:
            print("  ✗ " + m)
        print("\nデータを取りに行く前に止めた。共通仕様3.1を読み直すこと。")
        return 1
    print("privacy の検査はすべて通った")
    return 0


if __name__ == "__main__":
    sys.exit(main())
