#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""共通仕様 3.1 と 3.2 を、人の判断ではなくコードで守るための層。

  https://github.com/VirgoB77/ogataten-nippo/blob/main/docs/kyotsu-shiyo.md

出力する値は必ずここを通す。通さない経路を作らない。
姉妹サイト（開発系・競売統計・犯罪統計）と同じ内容にすること。
直したらリンク先の5節も直す。

なぜ要るか
  大店立地法の届出者は、ほとんどが法人だが、個人が23件まざっていた。
  設置者名と地番の両方をそのまま出していた。行政の縦覧は4か月で消えるが、
  こちらのサイトは消えない。「消えない」ことが、そのまま責任になる。
"""

import re

# ---------------------------------------------------------------- 法人かどうか

# 法人格を表す語。これを1つも含まなければ個人として扱う（安全な側に倒す）。
# 丸囲み文字（㈱㈲）と括弧書き（(株)）は、公報と自治体の一覧表で実際に多い。
# 共通仕様5節の最低限の一覧に、実物で出てきたものを足してある。
CORP_WORDS = (
    "株式会社", "有限会社", "合同会社", "合資会社", "合名会社", "相互会社",
    "特定目的会社", "投資法人", "有限責任事業組合",
    "一般社団法人", "公益社団法人", "一般財団法人", "公益財団法人",
    "社団法人", "財団法人", "医療法人", "学校法人", "宗教法人", "社会福祉法人",
    "独立行政法人", "地方独立行政法人", "国立大学法人", "特定非営利活動法人",
    "弁護士法人", "税理士法人",
    "生活協同組合", "農業協同組合", "漁業協同組合", "事業協同組合", "協同組合", "組合",
    "公社", "公団", "事業団", "機構", "振興会", "協会", "連合会", "商工会",
    "会館", "センター", "COOP", "コープ", "生協",
    # 括弧書き。全角・半角が混ざっているので _norm() でそろえてから見る
    "(株)", "(有)", "(同)", "(資)", "(名)", "(福)", "(医)", "(相)",
    # 丸囲み
    "㈱", "㈲", "㈳", "㈶", "㈴", "㈻", "㈷",
    # 「株赤ちゃん本舗」のように㈱が潰れた表記。人名に「株」は出てこない。
    # 「有」は有田・有村など姓に出るので、単独では入れない
    "株",
    # 外国法人
    "Co.", "Ltd", "Inc", "LLC", "L.L.C", "Corp", "K.K.", "PLC",
    "S.L", "S.A", "N.V", "B.V", "GmbH", "A/S", "Pty",
    "エルエルシー", "リミテッド", "コーポレーション", "ホールディングス",
)

# 国・地方公共団体。法人格の語を持たないが個人ではない。
PUBLIC_RE = re.compile(
    r"^(国|日本国)$"
    r"|(都|道|府|県|市|区|町|村)$"
    r"|(都|道|府|県|市|区|町|村).*(長|役所|役場|委員会|局|公社|公団)$"
)

# 日本の戸籍の氏名はカタカナだけ・ローマ字だけにはならない。
# 「オークワ ほか」「F.O.B COOP」のような屋号を個人と取り違えないため。
_KANA_ONLY = re.compile(r"^[ァ-ヶー・\s]+$")
_HAS_LATIN = re.compile(r"[A-Za-zＡ-Ｚａ-ｚ]")

_BRACKETS = str.maketrans("（）［］〔〕　", "()[][] ")


def _norm(name):
    """全角と半角の括弧をそろえる。「(有）末広」のように混ざった実物がある。"""
    return (name or "").translate(_BRACKETS).strip()


def is_corp(name):
    """法人格を表す語を含むか。含まなければ個人として扱う。"""
    n = _norm(name)
    if not n:
        return False
    if any(w in n for w in CORP_WORDS):
        return True
    if PUBLIC_RE.search(n):
        return True
    core = re.sub(r"\s*(ほか|他)\s*[0-9０-９]*\s*者?\s*$", "", n).strip()
    if core and (_KANA_ONLY.match(core) or _HAS_LATIN.search(core)):
        return True
    return False


# ---------------------------------------------------------------- 名前の出し方

# 一次情報の側が、すでに伏せて公表しているときの書き方。
# これを個人名と間違えて二重に伏せないため、先に拾う。
ALREADY_HIDDEN = {"個人", "個人名", "非公開", "個人情報"}

# 名前ではないもの。「未定」「物品販売業を営む店舗」など、一次情報が
# 名前の代わりに書いている文言。個人と取り違えて「個人」に変えない。
_PLACEHOLDER = re.compile(
    r"^[（(\[]?\s*(未定|未詳|不明|なし|無し|―|—|ー|-|－|‐)\s*[0-9０-９]*\s*者?\s*[)）\]]?$"
    r"|^物品販売業"
)


def is_placeholder(name):
    """名前が入るべき場所に、名前以外の文言が入っているか。"""
    n = (name or "").strip()
    return bool(n) and bool(_PLACEHOLDER.match(n))


def redact_name(name):
    """画面に出す用。法人ならそのまま。個人なら "個人" を返す。

    空欄にしない。空欄だと「取れなかった」のか「個人だから伏せた」のかが
    読者に分からない。伏せたことは、伏せたと書く（3.1）。
    """
    n = (name or "").strip()
    if not n:
        return ""
    if n in ALREADY_HIDDEN:
        return "個人"
    if is_placeholder(n):
        return n
    return n if is_corp(n) else "個人"


def party_for_index(name):
    """index.json の party に入れる用。法人ならそのまま、個人なら空文字。

    redact_name() とは別の関数にする。機械が読むデータに "個人" という
    文字列を入れると、全国の別人が同じ名前として扱われ、横断ハブで混ざる（3.1）。
    """
    n = (name or "").strip()
    if not n or n in ALREADY_HIDDEN or is_placeholder(n):
        return ""
    return n if is_corp(n) else ""


def party_kind(name, disclosed=True):
    """当事者の出し方。4つのどれか。3.1 の表と対応する。

    "corp"        法人と分かった
    "individual"  個人（法人と確かめられない場合を含む）
    "undisclosed" 一次情報の側が名前を載せていない（disclosed=False）
    "none"        そもそも当事者を持たない制度のレコード

    disclosed=False を渡してよいのは、一次情報に名前の欄が無いことを
    確かめたときだけ。欄はあるのに読めていないときは individual にする。
    こちらの解析の穴が、そのまま地番の公開になるため（3.1）。
    """
    if name is None:
        return "none"
    if not disclosed:
        return "undisclosed"
    n = (name or "").strip()
    if not n or is_placeholder(n):
        # 名前の欄はあるが、そこに名前が入っていない。相手が載せていないのか、
        # こちらが読めていないのかを決めつけない。安全な側に倒す（3.1）
        return "individual"
    if n in ALREADY_HIDDEN:
        return "individual"
    return "corp" if is_corp(n) else "individual"


# ---------------------------------------------------------------- 所在地の粒度

# 「ほか」「外7筆」「他2筆」などの、地番のあとに付く書き足し
_TAIL = re.compile(r"\s*(ほか|外|他)\s*\d*\s*筆?\s*$")
# 「一丁目」「1丁目」「１丁目」まで
_CHOME = re.compile(r"^(.*?[0-9０-９一二三四五六七八九十]+\s*丁目)")
# 丁目とその直前の数字。丸めたあとに残ってよい数字はこれだけ
_CHOME_NUM = re.compile(r"[0-9０-９一二三四五六七八九十]+\s*丁目$")
_HAS_NUM = re.compile(r"[0-9０-９]")
# 丁目が無く、数字が3つ以上ハイフンでつながっているとき（梅田1-1-1 → 梅田1）。
# 数字が2つだけ（永代町329-1）は「番地-枝番」なので、この形にはしない
_HYPHEN3 = re.compile(
    r"^(.*?[0-9０-９]+)[-‐−－ー―][0-9０-９]+[-‐−－ー―][0-9０-９]")
# それも無いとき、最初の算用数字の手前まで（池田下町３７７番１ → 池田下町）
_FIRST_NUM = re.compile(r"^(.*?)(?=[0-9０-９])")


def redact_addr(addr, kind):
    """所在地の粒度。kind は party_kind() の戻り値。

    "individual" のときだけ町丁目まで丸める。
    corp / undisclosed / none は地番まで出す。
    """
    a = (addr or "").strip()
    if kind != "individual" or not a:
        return a

    a = _TAIL.sub("", a)

    m = _CHOME.match(a)
    if m:
        r = m.group(1).replace(" ", "")
        # 丸めたあとに残ってよい数字は「丁目」の直前の1つだけ。
        # ほかに数字が混じっていたら、住所が2つつながっているなどの
        # 取りこぼしなので、安全な側に倒して下の規則に落とす
        if not _HAS_NUM.search(_CHOME_NUM.sub("", r)):
            return r

    m = _HYPHEN3.match(a)
    if m and m.group(1).strip():
        # 「梅田1-1-1」の最初の数字は丁目。丁目と書いて返す。
        # そのまま「梅田1」にすると、もう一度この関数に通したときに
        # 「梅田」まで削れてしまう。同じ値を返し続ける形にしておく
        return _TAIL.sub("", m.group(1)).strip() + "丁目"

    m = _FIRST_NUM.match(a)
    if m and m.group(1).strip():
        return _TAIL.sub("", m.group(1)).strip().rstrip("　 ")

    return a


# ---------------------------------------------------------------- 小さい母数

def suppress_rate(count, population):
    """率を伏せるべきか。人口500人未満、または件数2件以下で True（3.2）。"""
    return (population or 0) < 500 or (count or 0) <= 2


def bucket_count(n):
    """件数の表示。1〜2件は "1-2"、それ以外は str(n)（3.2）。"""
    n = n or 0
    return "1-2" if 1 <= n <= 2 else str(n)
