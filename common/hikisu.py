# -*- coding: utf-8 -*-
"""知らない引数で止める。**取りに行く前に。**

2026-09-19、開発系の事故報告——

> `python3 recon.py --help` と打ちました。**`--help` は受け取らないので、
> そのまま毎日の収集が走り出しました。**

`sys.argv[1]` をそのまま使う書き方だと、**知らない語が「対象の名前」になる。**
当たらなければ全部走る形なら、**打ち間違いが本番の収集になる。**

9節の「既定値は倒す向きが問題」。**その既定値で動いたとき外に何か出るなら、
止まる側に倒す。** ここで出るのは役所への接続なので、既定は止まる。

    ❌ 知らない引数 → 無視して走る     打ち間違いが本番になる
    ✅ 知らない引数 → **取りに行かずに終わる**
"""
import sys


def check(ukeru, argv=None, tsukaikata=""):
    """受け取る引数の一覧を渡す。**それ以外が来たら止める。**

    `ukeru` は受け取る語の集合。`--` で始まらない自由な語（収集先の id など）も
    受け取るなら、**呼ぶ側が先に絞ってから**ここへ渡す。

    返り値は無い。止めるときは `SystemExit(2)`。
    **0 で終わらない**のは、workflow が「通った」と読まないため。
    """
    warui = [a for a in (sys.argv[1:] if argv is None else argv) if a not in ukeru]
    if not warui:
        return
    print(f"知らない引数：{' '.join(warui)}", file=sys.stderr)
    if ukeru:
        print(f"受け取るのは：{' '.join(sorted(ukeru))}", file=sys.stderr)
    if tsukaikata:
        print(tsukaikata, file=sys.stderr)
    print("**取りに行かずに終わる。** 打ち間違いが本番の収集になるのを防ぐため",
          file=sys.stderr)
    raise SystemExit(2)
