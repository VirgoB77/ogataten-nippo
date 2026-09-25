"""門（common/kado.py）を回り込む道が無いかを見る、構造の見張り（指示書3）。

**名前の一覧では作らない。** 置き場の木を実際に歩いて、`.py` を1本ずつ読む。
足したファイルが「知らない名前」というだけで見張りから漏れることがない形にする。

見ること2つ。

    ① `.py`（`common/kado.py` 自身は除く）に、門を回り込める道具
       （`build_opener` / `HTTPSConnection` / `HTTPConnection` / `http.client` /
       `requests` / `urllib3` / `socket.create_connection` /
       `urlopen(..., context=...)` ・ `cafile=`）が出ていないか。
       出ていても、その行に `# kado-soto: <理由>` があれば許す
       （**自分のサイトを見るもの**だけ。取得先を見るものには付けない）。
    ② `urlopen(` か `urllib.request` を使う `.py` は、`common/kado.py` を
       import しているか（直接でも、`common.fetch` 経由でもよい。経由のときは、
       経由先の `common/fetch.py` が kado を import していることも確かめる）。

歩く範囲：`.git` `__pycache__` `node_modules` は常に除く。
`tests/` `data/` `inbox/` `_raw/` は**置き場の根に直接あるものだけ**除く
（根から見た1階の名前で判定する。深いところに同じ名前の階があっても除かない）。
`tests/` を除くのは、この検査自身の中に「見る語」がそのまま文字列で
出てくるので、自分自身を検査対象にすると必ず引っかかるため。
`data/` `inbox/` `_raw/` を除くのは、取得した生データの置き場で `.py` が無く、
歩く時間だけがかかるため（本番は金庫への symlink で、中身がとても大きい）。
"""
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

KADO_PY = os.path.normpath(os.path.join(HERE, "common", "kado.py"))
FETCH_PY = os.path.join(HERE, "common", "fetch.py")

# **常に除く**（どの深さでも）
TSUNE_NOZOKU = {".git", "__pycache__", "node_modules"}
# **根の1階だけ除く**（除く理由は上のdocstring）
NE_DAKE_NOZOKU = {"tests", "data", "inbox", "_raw"}

# 門を回り込める道具。この語がある行は、`# kado-soto:` が無ければ落とす
MAWARIKOMU = re.compile(
    r"build_opener|HTTPSConnection|HTTPConnection\(|http\.client\."
    r"|(?<!\.)\brequests\.(get|post|put|delete|head|Session)\("
    r"|^\s*import\s+requests\b|^\s*from\s+requests\b"
    r"|\burllib3\b|socket\.create_connection|cafile\s*=|urlopen\([^)]*context\s*="
)
KADO_SOTO = re.compile(r"#\s*kado-soto\s*:")

# `urllib.request` を使っているか（urlopen 単体でも、モジュールとしてでも）
URLLIB_TSUKAU = re.compile(r"\burlopen\(|\burllib\.request\b")

KADO_CHOKUSETSU = re.compile(
    r"^\s*from\s+common\s+import\s+[^\n#]*\bkado\b"
    r"|^\s*import\s+common\.kado\b"
    r"|^\s*from\s+common\.kado\s+import\b", re.M)
FETCH_KEIYU = re.compile(
    r"^\s*from\s+common\s+import\s+[^\n#]*\bfetch\b"
    r"|^\s*import\s+common\.fetch\b"
    r"|^\s*from\s+common\.fetch\s+import\b", re.M)


def aruku(ne):
    """置き場の木を歩いて、`.py` の絶対パスを返す（`common/kado.py` 以外）。"""
    for dirpath, dirnames, filenames in os.walk(ne):
        dirnames[:] = [d for d in dirnames if d not in TSUNE_NOZOKU]
        if os.path.normpath(dirpath) == os.path.normpath(ne):
            dirnames[:] = [d for d in dirnames if d not in NE_DAKE_NOZOKU]
        for name in filenames:
            if not name.endswith(".py"):
                continue
            p = os.path.normpath(os.path.join(dirpath, name))
            if p == KADO_PY:
                continue
            yield p


def _yomu(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


class 門を回り込まないか(unittest.TestCase):

    def test_見た_pyの数が0なら落ちる(self):
        """**数え方そのものが壊れていないか。** 0本は「歩けていない」の印。"""
        n = sum(1 for _ in aruku(HERE))
        self.assertGreater(n, 0, "置き場を歩いて .py が1本も見つからなかった。歩き方が壊れている")

    def test_回り込む道具が_kado_soto_無しで出ていないか(self):
        ihan = []
        for path in aruku(HERE):
            text = _yomu(path)
            for i, line in enumerate(text.splitlines(), 1):
                if MAWARIKOMU.search(line) and not KADO_SOTO.search(line):
                    ihan.append(f"{os.path.relpath(path, HERE)}:{i}: {line.strip()[:100]}")
        self.assertEqual(ihan, [],
                          "門（common/kado.py）を回り込める道具が、kado-soto の断りも無く出ている：\n"
                          + "\n".join(ihan))

    def test_urllib_requestを使うものは_kadoをimportしているか(self):
        moretsu = []
        fetch_ga_kado_wo_import = bool(KADO_CHOKUSETSU.search(_yomu(FETCH_PY)))
        for path in aruku(HERE):
            text = _yomu(path)
            if not URLLIB_TSUKAU.search(text):
                continue
            if KADO_CHOKUSETSU.search(text):
                continue
            if FETCH_KEIYU.search(text):
                if fetch_ga_kado_wo_import:
                    continue
                moretsu.append(
                    f"{os.path.relpath(path, HERE)}: common.fetch 経由だが、"
                    "common/fetch.py が kado を import していない")
                continue
            moretsu.append(
                f"{os.path.relpath(path, HERE)}: urlopen/urllib.request を使うのに、"
                "common/kado.py を import していない（直接でも common.fetch 経由でもない）")
        self.assertEqual(moretsu, [],
                          "門を通らずに urllib.request を使えるファイルがある：\n" + "\n".join(moretsu))


if __name__ == "__main__":
    unittest.main()
