# -*- coding: utf-8 -*-
"""取りに行くときの名乗りと間隔。4つの取得スクリプトが同じ値を使う（共通仕様 3.4）。

書式は仕様どおり：kujiraya archive bot (+<aboutページ>; <連絡フォーム>)
- about ページはサイト公開後なので 200 が返る。公開前なら404になるURLは入れない
- 連絡フォームは Google フォーム。ドメインに依存しないので、サイトを移しても変わらない
- ここ以外に UA の文字列を直書きしない（監査で4ファイルに重複していた）
"""

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
                body, note = r.read(200_000).decode("utf-8", "replace"), ""
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
