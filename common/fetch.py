# -*- coding: utf-8 -*-
"""取りに行くときの名乗りと間隔。4つの取得スクリプトが同じ値を使う（共通仕様 3.4）。

書式は仕様どおり：kujiraya archive bot (+<aboutページ>; <連絡フォーム>)
- about ページはサイト公開後なので 200 が返る。公開前なら404になるURLは入れない
- 連絡フォームは Google フォーム。ドメインに依存しないので、サイトを移しても変わらない
- ここ以外に UA の文字列を直書きしない（監査で4ファイルに重複していた）
"""

import re

ABOUT_URL = "https://ogataten-nippo.com/about.html"
CONTACT_FORM_URL = "https://forms.gle/pp93tSJ5p8SAMEMk8"

UA = f"kujiraya archive bot (+{ABOUT_URL}; {CONTACT_FORM_URL})"

# リクエスト間隔（秒）。同時接続は1本。仕様の「5秒以上」
WAIT = 5


# ---------------------------------------------------------------- robots.txt
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser

TIMEOUT = 40
# 相手が「混んでいる」「今は受けない」と言っている応答。押し込まずにその回は中止（3.4）
BUSY = (429, 503)

_robots_cache = {}


class Konde(Exception):
    """相手が「いま受けられない」と言った（429/503）。

    **ふつうの失敗と分けるための型。** `except Exception` で拾って
    「次へ」と進む書き方をしていると、**混んでいると言われても回り続ける。**
    型で分けておけば、呼ぶ側が `except Konde: raise` を1行足すだけで止まる。

    2026-09-19 の監査で出た。`ref_youto.py` は 429/503 を見ているつもりで、
    **`urlopen` が先に HTTPError を投げるので、その行は1度も通っていなかった。**
    しかも外側の `except Exception` が拾って次の URL へ進んでいた。
    """


def is_busy(exc):
    """HTTPError が 429 / 503 か。"""
    return isinstance(exc, urllib.error.HTTPError) and exc.code in BUSY


def robots_allows(body, url, ua=UA):
    """robots.txt の本文を渡して、この UA が url を取ってよいか。ネットに出ない純粋な判定。"""
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(body.splitlines())
    return rp.can_fetch(ua, url)


def check_robots(url):
    """robots.txt を、こちらの名乗りで取って確かめる。1回の実行につきホストごとに1回。

    返り値 (ok, why)
      True  … 許可
      False … robots.txt で拒否。取りに行かない
      None  … robots.txt 自体が 429/503 で返らない。相手が混んでいるので、その回は中止

    robots.txt が無い（404）・読めない（DNS/時間切れ）ときは、慣例どおり許可とみなす。
    以前の recon.py は urllib.robotparser にそのまま読ませていたので、名乗りが
    Python-urllib になり、429/503 も「全部許可」に倒れていた（監査で見つかった）。
    """
    p = urllib.parse.urlparse(url)
    host = f"{p.scheme}://{p.netloc}"
    if host in _robots_cache:
        body, note = _robots_cache[host]
    else:
        req = urllib.request.Request(f"{host}/robots.txt",
                                     headers={"User-Agent": UA, "Accept": "text/plain,*/*"})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                # **robots.txt も utf-8 と決めつけない。** 役所のサーバーには
                # Shift_JIS が残っている。`Disallow` は ASCII なので判断は当たるが、
                # 日本語の注記が置換文字になり、**壊れたことにどこでも気づけない**
                # （2026-09-19、4サイトのうち3つが同じ場所で見つけた）
                body, _enc = decode_html(r.read(200_000),
                                         r.headers.get("Content-Type") or "")
                note = ""
        except urllib.error.HTTPError as e:
            if e.code in BUSY:
                body, note = None, f"robots.txt が HTTP {e.code}（混んでいる）"
            else:
                body, note = "", f"robots.txt が HTTP {e.code}（無いものとして続ける）"
        except Exception as e:
            body, note = "", f"robots.txt が読めなかった {type(e).__name__}（続ける）"
        _robots_cache[host] = (body, note)
    if body is None:
        return None, note
    ok = robots_allows(body, url) if body else True
    return ok, (note or ("許可" if ok else "robots.txt で拒否されている"))


# ---------------------------------------------------------------- 文字コード

# 半角カナと置換文字。**化けたときに増えるもの。**
_NOISE = re.compile(r"[�｡-ﾟ\x00-\x08\x0B\x0C\x0E-\x1F]")
# 日本語らしさ。ひらがな・カタカナ・漢字
_JA = re.compile(r"[぀-ゟ゠-ヿ一-鿿]")
_CHARSET = re.compile(r"charset\s*=\s*[\"']?([\w-]+)", re.I)
# 総当たりの順。**この順に並べても足りない。**下の点で選ぶ
_TRY = ("utf-8", "cp932", "euc-jp", "iso-2022-jp")


def ja_score(text):
    """日本語として読めていそうか。大きいほどよい。

    **「例外が出なかった」は「読めた」ではない。** cp932 はほとんどのバイト列を
    受け取るので、EUC-JP のページがそこで「成功」する（2026-09-19、開発系が発見）。

        "大阪府".encode("euc-jp").decode("cp932")  →  "ﾂ郤衙ﾜ"   例外は出ない

    だから**例外の有無ではなく、中身の見た目で選ぶ。**
    化けると増えるもの（置換文字・半角カナ・制御文字）を引き、
    日本語らしい字を足す。
    """
    if not text:
        return 0.0
    n = len(text)
    return (len(_JA.findall(text)) - 3 * len(_NOISE.findall(text))) / n


def bakete_inai(text):
    """化けていないか。0.0〜1.0。**日本語かどうかは見ない。**（開発系の版）

    `ja_score()` と**測っているものが違う。** 使い分ける。

        ja_score()     日本語として読めたか   英数字だけのページでは 0.0（外す）
        bakete_inai()  化けているか           英数字だけのページでも 1.0（外さない）

    大型店日報の収集先には、英数字だけのページが**実測0枚**なので
    `ja_score()` を使う（生ページ955枚、2026-09-19）。
    **英数字だけのページが来る置き場では、こちらを使う。**
    どちらも片方だけだと外すので、置き場ごとに選ぶこと。
    """
    if not text:
        return 0.0
    return 1.0 - len(_NOISE.findall(text)) / len(text)


def decode_html(raw, content_type=""):
    """バイト列を文字にする。**UTF-8 と決めつけない。**（共通仕様9節）

    宣言（Content-Type → ページの中の meta）があれば信じる。
    無ければ**総当たりして、いちばん日本語らしく読めたもの**を採る。
    **どれで読んだかを返す。** 黙って選ぶと、次に見る人が確かめられない。
    """
    declared = []
    m = _CHARSET.search(content_type or "")
    if m:
        declared.append(m.group(1))
    m = _CHARSET.search(raw[:4096].decode("ascii", "replace"))
    if m:
        declared.append(m.group(1))
    for enc in declared:
        try:
            return raw.decode(enc), enc
        except (UnicodeDecodeError, LookupError):
            continue

    best = None
    for enc in _TRY:
        try:
            text = raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
        score = ja_score(text)
        if best is None or score > best[0]:
            best = (score, text, enc)
    if best:
        return best[1], best[2]
    return raw.decode("utf-8", "replace"), "utf-8（化けたまま）"
