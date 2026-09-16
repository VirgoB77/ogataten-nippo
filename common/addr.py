# -*- coding: utf-8 -*-
"""住所を4サイトで突き合わせるための正規化。標準ライブラリのみ。

正本は ogataten-nippo/docs/kyotsu-shiyo.md の4節。姉妹サイトはこのファイルを
そのままコピーして使う（submodule も pip も使わない）。直したら正本も直す。

normalize(pref, city, addr) → dict
  pref / city / city_code / town / addr / addr_key / addr_key_town

town の決め方（4節）
  ① 正規化で自分がハイフンにした場所があれば、その手前まで（確実）
  ② 1つも置き換えなかったときは、町丁目の一覧（data/ref/towns.json）で最長一致
  ③ どちらでも決まらなければ空文字。推測で埋めない

city_code は data/ref/jis-codes.json（総務省「全国地方公共団体コード」を
ref_jis.py が取ってきたもの）から引く。無ければ空文字。
"""

import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.join(os.path.dirname(HERE), "data", "ref")
CODES_PATH = os.path.join(REF, "jis-codes.json")
TOWNS_PATH = os.path.join(REF, "towns.json")

_codes = None
_towns = None

# ---------------------------------------------------------------- 一覧の読み込み

def load_codes(path=CODES_PATH):
    """{(都道府県, 市区町村名): 5桁コード}。市区町村名は「大阪市北区」のように区まで。"""
    global _codes
    if _codes is None:
        _codes = {}
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                for row in json.load(f):
                    _codes[(row["pref"], row["city"])] = row["code"]
    return _codes


def load_towns(path=TOWNS_PATH):
    """{city_code: [町丁目名, ...]}。無ければ空（②は効かず、③で空になる）。"""
    global _towns
    if _towns is None:
        _towns = {}
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                _towns = json.load(f)
    return _towns


def city_code_of(pref, city, codes=None):
    codes = load_codes() if codes is None else codes
    if not city:
        return ""
    for name in (city, re.sub(r"^[^\s]{1,3}郡", "", city)):
        c = codes.get((pref, name))
        if c:
            return c
    # 郡付きで登録されていて、こちらが郡なしの場合
    for (p, n), c in codes.items():
        if p == pref and n.endswith(city) and re.fullmatch(r"[^\s]{1,3}郡" + re.escape(city), n):
            return c
    return ""


# ---------------------------------------------------------------- 正規化

_Z2H = str.maketrans(
    "０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ",
    "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz")
_DASHES = re.compile(r"[－‐−–—―]")
_KANJI = {"〇": 0, "零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
# 漢数字を直すのは「丁目・番・号」の直前だけ。三田市・十三・四条畷・一宮のような地名を壊さない
_KANJI_NUM = re.compile(r"([〇零一二三四五六七八九十]+)(?=(丁目|丁(?=[0-9]|$)|番|号))")
# 「丁目・番地・番・号」は直後が数字か終わりのときだけハイフンにする（「番町」の番は置き換えない）
# 「847番地の1」の「の」は単位の続き。単位ごと置き換える
# 堺市は「鳳東町七丁733」のように「丁」だけで丁目を表す。直後が数字か終わりのときだけ単位と見る
_UNIT = re.compile(r"(丁目|丁|番地|番|号)の?(?=[0-9]|$)")
_MARK = chr(1)          # 自分が置き換えた場所の印。入力にもとからあるハイフンと区別する


def _kanji_to_int(s):
    total, cur = 0, 0
    for ch in s:
        if ch == "十":
            cur = (cur or 1) * 10
            total += cur
            cur = 0
        else:
            cur = _KANJI[ch]
    return total + cur


def _clean(addr):
    a = (addr or "").translate(_Z2H)
    a = _DASHES.sub("-", a)
    a = re.sub(r"(?<=[0-9])ー", "-", a)                 # 数字のあとの長音は「の」代わりのハイフン
    a = re.sub(r"[\s　]+", "", a)                    # 5. 空白を除去
    a = re.sub(r"大字|^字|(?<=[市区町村])字", "", a)        # 4. 大字・字を除去
    a = _KANJI_NUM.sub(lambda m: str(_kanji_to_int(m.group(1))), a)   # 2. 漢数字 → 算用数字
    a = re.sub(r"(?<=[0-9])の(?=[0-9])", "-", a)          # 「2463番地の1」の「の」
    return a


def normalize(pref, city, addr, codes=None):
    pref = (pref or "").strip()
    city = (city or "").strip()
    raw = (addr or "").strip()
    code = city_code_of(pref, city, codes)

    a = _clean(raw)
    # 住所に市区町村名や都道府県名が先頭に付いていたら落とす（表示では city を足し直す）
    ward = re.sub(r"^.*?市", "", city) if re.search(r"市.+区$", city) else ""   # 「堺市西区」→「西区」
    for head in (pref + city, city, pref, ward):
        if head and a.startswith(head):
            a = a[len(head):]
            break

    # 3. 単位をハイフンに。置き換えた場所を印で覚えておく（① のため）
    marked = _UNIT.sub(_MARK, a)
    first = marked.find(_MARK)

    if first >= 0:
        # ① 印の手前が town。地番の連なりは印の直前の数字から始まる
        town = marked[:first]
        start = first
        while start > 0 and marked[start - 1].isdigit():
            start -= 1
        end = first
        while end < len(marked) and (marked[end].isdigit() or marked[end] in (_MARK, "-")):
            end += 1
        chain = marked[start:end].replace(_MARK, "-").strip("-")
        building = marked[end:].replace(_MARK, "-")
        key = marked[:start] + chain
        display = (key + (building if building else "")).rstrip("-")   # 末尾の「号」が印になって残る
        town = re.sub(r"-+$", "", town)
    else:
        # ② 置き換えが無かった。町丁目の一覧で最長一致。無ければ ③ 空
        display = marked
        key = marked
        towns = load_towns().get(code, []) if code else []
        town = ""
        for t in sorted(towns, key=len, reverse=True):
            if key.startswith(t):
                town = t
                break
        # 建物名は地番の連なりの後ろ。「上ケ原2番町3-5」なら 3-5 の後ろ。
        # 地番の連なりは「ハイフンを含む最初の数字の列」。無ければ最後の数字の列。
        # 最後の列にすると「○○ビル3F」の 3 を地番と取り違える
        m = list(re.finditer(r"[0-9]+(?:-[0-9]+)*", key))
        if m:
            hy = [x for x in m if "-" in x.group(0)]
            key = key[:(hy[0] if hy else m[-1]).end()]

    key = re.sub(r"(ほか|他[0-9]*|外[0-9]*筆|他[0-9]*筆|の一部)$", "", key)
    return {
        "pref": pref,
        "city": city,
        "city_code": code,
        "town": town,
        "addr": f"{city}{display}" if display else city,
        "addr_key": f"{code}|{key}" if code and key else "",
        "addr_key_town": f"{code}|{town}" if code and town else "",
    }
