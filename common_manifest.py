#!/usr/bin/env python3
"""`common/` の中身の指紋を出す。**4つの置き場がずれていないかを見るため。**

正本11節の手順3は「マージされたら、各サイトの `common/` を更新する」と
書いてある。**守られていなかった。** 2026-09-19、開発系が突き合わせたら
`common/addr.py` が 369行 と 197行で別物だった。しかも向こうが読んだのは
さらに古い 169行の版で、**ずれが二重になっていた。**

人が覚えている手順は、忘れられる。**機械が言うようにする。**

  こちら（正本の置き場）  この一覧を作って、コミットに入れる
  各サイト                この一覧を取ってきて、自分の common/ と比べる
                          違っていたら鳴らす（古いか、勝手に直したか）

`--check` で、いまのファイルと一覧が合っているかを見る（合わなければ 1 を返す）。
"""
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
COMMON = os.path.join(HERE, "common")
MANIFEST = os.path.join(COMMON, "MANIFEST.txt")
HEAD = ("# common/ の指紋。正本の置き場は VirgoB77/ogataten-nippo。\n"
        "# 各サイトはこれを取ってきて、自分の common/ と比べること（11節 手順3）。\n"
        "# 作り直す: python3 common_manifest.py\n")


def fingerprints():
    """{ファイル名: sha256}。**改行の違いは無視しない。** 写し間違いも見たい。"""
    out = {}
    for name in sorted(os.listdir(COMMON)):
        if not name.endswith(".py"):
            continue
        with open(os.path.join(COMMON, name), "rb") as f:
            out[name] = hashlib.sha256(f.read()).hexdigest()
    return out


def render(fp):
    return HEAD + "".join(f"{h}  {n}\n" for n, h in sorted(fp.items()))


def main():
    text = render(fingerprints())
    if "--check" in sys.argv:
        have = open(MANIFEST, encoding="utf-8").read() if os.path.exists(MANIFEST) else ""
        if have != text:
            print("common/MANIFEST.txt が中身と合っていない。"
                  "`python3 common_manifest.py` で作り直すこと", file=sys.stderr)
            return 1
        print(f"common/ の {len(fingerprints())} 本、一覧と一致")
        return 0
    with open(MANIFEST, "w", encoding="utf-8") as f:
        f.write(text)
    print(text, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
