# -*- coding: utf-8 -*-
"""住所を4サイトで突き合わせるための正規化。標準ライブラリのみ。

正本は ogataten-nippo/docs/kyotsu-shiyo.md の4節。姉妹サイトはこのファイルを
そのままコピーして使う（submodule も pip も使わない）。直したら正本も直す。

normalize(pref, city, addr) → dict
  pref / city / city_code / town / addr / addr_key / addr_key_town

town の決め方（4節）
  ① 正規化で自分がハイフンにした場所があれば、その手前まで（確実）
  ② 1つも置き換えなかったときは、町丁目の一覧（data/ref/towns.json）で最長一致。
     **当たった直後が数字か末尾のときだけ採る**（短い町名へ化けさせない）
  ①' 丁目が無くて①で決まらなかったときは、数字の手前が一覧の町名と
     **丸ごと同じときだけ**決める（前方一致にはしない）
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


def machi_wo_ateru(s, towns):
    """町丁目の一覧で最長一致。**当たった直後が数字か、末尾のときだけ採る。**

    4節②は「きつい側に外す」の例外で、**外れると別の町丁目になる。**
    だから「短い町名が、長い別の町名の頭に一致しただけ」では決めない。

        一覧に「甲子園」だけ在って「甲子園口北町」が無いとき
          甲子園口北町5-6  →  「甲子園」に当たってしまう（旧）
                           →  直後が「口」なので採らない（いま）

    **当たったのに境目が合わなければ、より短い候補へは下がらない。**
    下がると、もっと粗い町名へ化けるだけになる。決まらない側に倒す（4節③）。
    """
    for t in sorted(towns, key=len, reverse=True):
        if s.startswith(t):
            nokori = s[len(t):]
            return t if (nokori == "" or nokori[0].isdigit()) else ""
    return ""


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
# **印は2種類。町丁目の切れ目と、地番の区切りは別のもの。**
# 1種類にして「最初の印まで」を町丁目にすると、丁目の無い住所で
# 「本町847番地の1」の 847（地番）が町丁目に入る。実データ4,809件のうち
# **1,007件がそうなっていて、公開している index.json に出ていた**
# （2026-09-19、開発系が自分の実装と見比べて見つけた）
_CHOME = re.compile(r"(丁目|丁)(?=[0-9]|$)")       # ここまでが町丁目
_BAN = re.compile(r"(番地|番|号)の?(?=[0-9]|$)")    # ここからは地番
_MARK = chr(1)          # 地番の区切り。入力にもとからあるハイフンと区別する
_CMARK = chr(2)         # 町丁目の切れ目


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


# 市区町村の索引。`load_codes()` から作る。長いものから当てる
_BY_PREF = None
_PREFS = None
# 郡は市区町村コードの表に入っていない（「川辺郡猪名川町」は「猪名川町」で載る）
_GUN = re.compile(r"^(.{1,5}?郡)")


def _index(codes=None):
    """{都道府県: [市区町村, ...]}（長い順）と、都道府県の一覧（長い順）。"""
    global _BY_PREF, _PREFS
    codes = load_codes() if codes is None else codes
    if _BY_PREF is not None and _BY_PREF.get("__src__") is codes:
        return _BY_PREF["by"], _PREFS
    by = {}
    for (pref, city) in codes:
        by.setdefault(pref, []).append(city)
    for v in by.values():
        v.sort(key=len, reverse=True)
    _BY_PREF = {"__src__": codes, "by": by}
    _PREFS = sorted(by, key=len, reverse=True)
    return by, _PREFS


def split_city(addr, pref="", city="", codes=None):
    """「所在地」の1列から、都道府県と市区町村を切り出す。

    pref / city は収集先の台帳が知っている値を渡す**ヒント**。
    **文字列のほうを先に信じる。** 大阪市が岡山県備前市の土地を売って
    いることが実際にあるので、収集先の市をそのまま被せると、
    他県の土地が大阪市の升に入る（4節「収集先の市を、そのまま住所に被せない」）。

    戻り値は2つの欄で、**別のことを測る。**

        city_precision  どこまで決まったか（細かさ）。層の粒度に使う
          "区" / "市" / ""

        city_source     どこから取ったか（確かさ）。突き合わせてよいかに使う
          "住所"  所在地そのものから切れた。いちばん確か
          "台帳"  呼ぶ側の市で補った。**たぶんその市。**
                  住所と食い違ったら "住所" のほうを信じる
          ""      決められなかった。**推測で埋めない**

    **1つの欄に2つの意味を入れない。** 細かさだけを持っていたとき、
    住所から切れた「大阪市福島区」と、台帳の"大阪市"＋住所の"福島区"を
    足した「大阪市福島区」が、どちらも "区" で見分けられなかった
    （実データ456件のうち121件がヒントで補った行。開発系・2026-09-19）。

    **ヒントは狭めるためにだけ使う。探す範囲を広げるためには使わない。**
    ヒントを外して全国から探すと、大阪市の「北区梅田一丁目」が
    **東京都北区**になる（121件のうち23件がこの形）。
    """
    codes = load_codes() if codes is None else codes
    by, prefs = _index(codes)
    s = re.sub(r"[\s\u3000]+", "", addr or "")
    got_pref = ""
    for p in prefs:                        # 文字列に都道府県名が書いてあれば、それ
        if s.startswith(p):
            got_pref, s = p, s[len(p):]
            break
    if not got_pref and pref:
        got_pref = pref
    bare = _GUN.sub("", s)                 # 郡を落とした形でも当てる
    for p in ([got_pref] if got_pref else prefs):
        for c in by.get(p, ()):
            for t in (s, bare):
                if t.startswith(c):
                    return {"pref": p, "city": c, "rest": t[len(c):],
                            "city_precision": "区" if "区" in c else "市",
                            "city_source": "住所"}
    # 市名が省かれて区から書いてある（大阪市のページの「福島区海老江…」）
    m = re.match(r"^(.+?区)", s)
    if city and m and (got_pref, city + m.group(1)) in codes:
        return {"pref": got_pref, "city": city + m.group(1),
                "rest": s[len(m.group(1)):], "city_precision": "区",
                "city_source": "台帳"}
    # 区も書かれていない（大阪市のページの「矢田五丁目」）。
    # **ここに来るのは、他の都道府県・市区町村の名前で始まっていないときだけ。**
    if city and ((not got_pref) or got_pref == pref):
        if ((got_pref or pref), city) in codes:
            return {"pref": got_pref or pref, "city": city, "rest": s,
                    "city_precision": "市", "city_source": "台帳"}
    return {"pref": got_pref, "city": "", "rest": s,
            "city_precision": "", "city_source": ""}


def _conflicting_head(a, pref, city, codes=None):
    """整形後の住所 `a` の先頭が、呼ぶ側と違う都道府県／市を名乗っていたら、その名前。

    見るのは**都道府県名**と、**「市」で終わる市名**だけ。町丁目の名前は
    この2つと衝突しない（「甲子園町」で終わる市は無い）。区・町・村は
    町丁目と衝突しうるので見ない——**見落とすほうに倒す。**
    ここで拾えなかったぶんは、呼ぶ側が住所から市を読んで防ぐ。
    """
    codes = load_codes() if codes is None else codes
    for p in {p for (p, _) in codes}:
        if p != pref and a.startswith(p):
            return p
    code = city_code_of(pref, city, codes)
    hits = [n for (p, n), c in codes.items()
            if n.endswith("市") and c != code and a.startswith(n)]
    return max(hits, key=len) if hits else ""


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
    else:
        # 落とせなかった。**それが「別の市の名前」だったら、繋げずに止める。**
        # 市は自分の市の外の土地も売る。繋げると
        # 「大阪市北区兵庫県西宮市甲子園町1-1」のような、形は正しいのに
        # この世に無い住所ができて、検査を通ってしまう（4節・2026-09-19）
        other = _conflicting_head(a, pref, city, codes)
        if other:
            raise ValueError(
                "住所が別の市区町村を名乗っている。呼ぶ側の市を被せない： "
                f"呼ぶ側={pref}{city} / 住所の先頭={other} / 原文={raw!r}")

    # 3. 単位をハイフンに。置き換えた場所を印で覚えておく（① のため）。
    #    **丁目だけは別の印にする。** 町丁目がどこで終わるかは、
    #    自分が「丁目」を置き換えた場所しか確実に分からない（4節①）
    marked = _BAN.sub(_MARK, _CHOME.sub(_CMARK, a))
    marks = [i for i in (marked.find(_MARK), marked.find(_CMARK)) if i >= 0]
    first = min(marks) if marks else -1
    ci = marked.find(_CMARK)

    if first >= 0:
        # ① **丁目の印の手前だけが town。** 番地の印は町丁目を決めない。
        #    丁目が無ければ町丁目は決まらない → ③ で空のまま
        town = marked[:ci] if ci >= 0 else ""
        start = first
        while start > 0 and marked[start - 1].isdigit():
            start -= 1
        end = first
        while end < len(marked) and (marked[end].isdigit()
                                     or marked[end] in (_MARK, _CMARK, "-")):
            end += 1
        chain = marked[start:end].replace(_MARK, "-").replace(_CMARK, "-").strip("-")
        building = marked[end:].replace(_MARK, "-").replace(_CMARK, "-")
        key = marked[:start] + chain
        display = (key + (building if building else "")).rstrip("-")   # 末尾の「号」が印になって残る
        town = re.sub(r"-+$", "", town.replace(_MARK, "-").replace(_CMARK, "-"))
        if ci < 0 and not town:
            # **丁目が無いので町丁目が決まらなかった行。** ここは一覧を
            # 一度も見ていなかった（2026-09-22 に測った。西宮市で51件）。
            # 見るのは「数字の連なりが始まる手前」だけ。start は上で出ている。
            # **前方一致ではなく、丸ごと同じときだけ採る。**
            # 前方一致にすると「町A139番、町B2-3」のように1行に町が2つ在る
            # ときに片方を選んでしまう（実測で1件あった）。
            # first より前なので、marked[:start] に印は入らない
            mae = marked[:start]
            if code and mae and mae in load_towns().get(code, []):
                town = mae
    else:
        # ② 置き換えが無かった。町丁目の一覧で最長一致。無ければ ③ 空
        display = marked.replace(_MARK, '-').replace(_CMARK, '-')
        key = marked.replace(_MARK, '-').replace(_CMARK, '-')
        town = machi_wo_ateru(key, load_towns().get(code, []) if code else [])
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
