#!/usr/bin/env python3
"""登記所備付地図データ（法務省）を取る段。**まだ全部は取らない。**

規約は統括が 2026-09-21 に読んだ。**取ってよい**（正本9節に逐語で残してある）。

    ダウンロード・保存   複製を明示的に認めている。機械取得・保存の明示的禁止は無い
    加工・二次利用      編集・加工利用が規約上明示的に想定されている
    商用利用           規約本文に「商用利用も可能です」
    出典              **必須。** 加工したときは加工した旨も別に表示する

禁止の線（越えない）——

    ・サーバ・ネットワークの妨害、公開を妨害するおそれのある取得
    ・**取得したコンテンツについて、他の情報と照合する等して
      特定の個人を識別する行為**

**規約と robots は別の欄。** 片方で他方を代用しない（正本9節）。
規約が「取ってよい」でも、robots が拒んでいたら取りに行かない。

案B（統括 2026-09-21）——

    同じ市区町村・同じ年度の zip が、2つの目録に並んでいることがある。
    **1回だけ両方取って**、大きさ・SHA-256・zip の中のファイル一覧を比べる。
    **1組一致しただけで、全市区町村・全年度が同一とは一般化しない。**
    不一致ならその時点で止めて報告する。

**URL を組み立てない。** `data/ref/chizu-recon.md`（`chizu_recon.py` が
目録から書いた記録）に載っている、**向こうが書いた URL をそのまま使う**（9節）。

取った zip は `inbox/`（公開側に入らない）に置く。**公開リポジトリには
台帳だけが入る。** 台帳には出典に要る8つを残す——

    データセット名 ／ 市区町村 ／ 年度 ／ 元URL
    取得日 ／ 取得元データセットID ／ ファイル名 ／ SHA-256

**推測で欠損を埋めない。** 読めなかった欄は `null` のままにする。
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from common.fetch import UA, WAIT, check_robots, is_busy  # noqa: E402

MOTO = os.path.join(HERE, "data", "ref", "chizu-recon.md")
OKIBA = os.path.join(HERE, "inbox", "chizu", "zip")
DAICHO = os.path.join(HERE, "data", "ref", "chizu-get.json")
REPORT = os.path.join(HERE, "data", "ref", "chizu-get.md")
TIMEOUT = 300
JST = datetime.timezone(datetime.timedelta(hours=9))

# 規約の欄。**robots の欄とは別に持つ。** 4つの言葉だけを使う（正本9節）
KEKKA = ("取ってよい", "未確認", "規約未確定", "取ってはいけない")
YAKUSOKU = {
    "moto": "houmusho-chizu",
    "mei": "登記所備付地図データ（法務省／G空間情報センター）",
    "kekka": "取ってよい",
    "mita_hi": "2026-09-21",
    "mita_no_wa": "統括",
    "url": "https://www.geospatial.jp/ckan/dataset/"
           "fc3b0593-ce9e-40d1-aa33-94382d5f0da1/resource/"
           "47871bf1-4c85-48f7-a8fe-b27c6643c1c5/download/license.pdf",
    "shutten_hissu": True,
    "kinshi": (
        "サーバ・ネットワークの妨害、公開を妨害するおそれのある取得",
        "取得したコンテンツについて、他の情報と照合する等して"
        "特定の個人を識別する行為",
    ),
}

# 目録の URL の形（向こうが書いたもの）。**組み立てには使わない。読み取るだけ**
_URL = re.compile(
    r"/ckan/dataset/(?P<ds>[0-9a-f-]{36})/resource/(?P<rs>[0-9a-f-]{36})"
    r"/download/(?P<na>[^/\s|]+)$", re.I)
# `27102-1203-2025.zip` の 2025。**ファイル名から読む。決め打ちしない**
_NENDO = re.compile(r"^\d{5}-\d{3,5}-(\d{4})\.zip$", re.I)
_GYO = re.compile(r"^\|\s*`(?P<code>\d{5})`\s*(?P<name>[^|]*?)\s*\|"
                  r"\s*(?P<ds>[^|]*?)\s*\|\s*(?P<rn>[^|]*?)\s*\|"
                  r"\s*(?P<fmt>[^|]*?)\s*\|\s*(?P<url>\S+)\s*\|\s*$")


def nendo(filename):
    """ファイル名から年度を読む。**読めなければ None。** 0 にも今年にもしない。"""
    m = _NENDO.match(filename or "")
    return int(m.group(1)) if m else None


def mokuroku(michi=None):
    """`chizu_recon.py` が書いた記録から、目録に並んでいたものを読む。

    **ここで URL を作らない。** 表に載っている URL をそのまま持ち出す。
    返り値は [{code, name, dataset, filename, format, url, dataset_id,
    resource_id, nendo}]。**読めなかった行は落とさず数える。**
    """
    michi = michi or MOTO
    de, yomenai = [], 0
    if not os.path.exists(michi):
        return de, None
    with open(michi, encoding="utf-8") as f:
        for line in f:
            m = _GYO.match(line.rstrip("\n"))
            if not m:
                continue
            u = _URL.search(m.group("url"))
            if not u:
                yomenai += 1
                continue
            de.append({
                "code": m.group("code"),
                "name": m.group("name"),
                "dataset": m.group("ds"),
                "filename": u.group("na"),
                "format": (m.group("fmt") or "").upper(),
                "url": m.group("url"),
                "dataset_id": u.group("ds"),
                "resource_id": u.group("rs"),
                "nendo": nendo(u.group("na")),
            })
    return de, yomenai


def kasanari(rows):
    """**同じ市区町村・同じ年度で、目録が2つ以上あるもの**を拾う。

    データセットID が違えば別の目録。**ファイル名が同じでも同一とは読まない。**
    それを確かめるのがこの段。返り値は [( (code, nendo), [row, ...] )]。
    """
    tana = {}
    for r in rows:
        if r["format"] != "ZIP" or r["nendo"] is None:
            continue
        tana.setdefault((r["code"], r["nendo"]), {})[r["dataset_id"]] = r
    return [(k, list(v.values())) for k, v in sorted(tana.items())
            if len(v) >= 2]


def yubiwa(michi):
    """ファイルの SHA-256。**中身は持ち出さない。**"""
    h = hashlib.sha256()
    with open(michi, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def nakami(michi):
    """zip の中のファイル一覧。

    返り値 (件数, 一覧の指紋, 読めなかった理由)。
    **読めなければ (None, None, 理由)。** 0件と「読めなかった」を混ぜない——
    0件は「中が空だと向こうが言った」、None は「こちらが開けなかった」。
    """
    try:
        with zipfile.ZipFile(michi) as z:
            hyo = sorted((i.filename, i.file_size, i.CRC)
                         for i in z.infolist())
    except Exception as e:                          # noqa: BLE001
        return None, None, f"{type(e).__name__}: {e}"
    nama = "\n".join(f"{n}\t{s}\t{c}" for n, s, c in hyo).encode("utf-8")
    return len(hyo), hashlib.sha256(nama).hexdigest(), None


def get(url, dest):
    """1本だけ取る。**押し込まない。** 429/503 はその回を中止する合図。"""
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/zip, application/octet-stream, */*",
        "Accept-Language": "ja",
    })
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r, \
            open(dest, "wb") as f:
        n = 0
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            n += len(chunk)
        return r.status, r.headers.get("Content-Type", ""), \
            r.headers.get("Last-Modified"), r.headers.get("ETag"), n


def shutten(rec):
    """規約が求める出典の1行。**取得日まで入れる。**"""
    return (f'出典：「{rec["dataset"]}」（法務省）'
            f'{rec["url"]}（{rec["totta_hi"]}に利用）')


def kuraberu(a, b):
    """2本を比べる。**比べる相手が無い／読めない欄は「未判定」。**

    「一致」と書いてよいのは、**3つとも見えていて3つとも同じ**ときだけ。
    1つでも見えていなければ、残りが同じでも「未判定」。
    """
    mita, chigau, mienai = [], [], []
    for k, mei in (("bytes", "大きさ"), ("sha256", "SHA-256"),
                   ("nakami_yubiwa", "zip の中の一覧")):
        x, y = a.get(k), b.get(k)
        if x is None or y is None:
            mienai.append(mei)
        elif x == y:
            mita.append(mei)
        else:
            chigau.append(mei)
    if chigau:
        return "不一致", mita, chigau, mienai
    if mienai:
        return "未判定", mita, chigau, mienai
    return "一致", mita, chigau, mienai


def kaku(kiroku, kumi_kekka, nokori, yomenai, report=None, daicho=None):
    """台帳を書く。**数えていないものを0にしない。**

    置き場は `def` のときに固めない。**呼ぶ側が差し替えられる**ようにする。
    2026-09-21、`def yomu(michi=RECON)` が既定値を定義時に束ねていて、
    **検査が差し替えたつもりの置き場を素通りして本物を読んでいた。**
    ここは逆向きの同じ穴——**検査が本物の台帳に書き込んでしまう。**
    """
    report = report or REPORT
    daicho = daicho or DAICHO
    hi = datetime.datetime.now(JST).strftime("%Y-%m-%d")
    lines = [
        "# 地図データを取った記録", "",
        "**このファイルは `chizu_get.py` が書く。** 手で直さない。", "",
        f"規約：**{YAKUSOKU['kekka']}**（{YAKUSOKU['mita_no_wa']}が "
        f"{YAKUSOKU['mita_hi']} に読んだ）。出典の表示が必須。",
        "**規約と robots は別の欄。** 片方で他方を代用しない。", "",
        "禁止の線（越えない）——", "",
    ] + [f"  ・{x}" for x in YAKUSOKU["kinshi"]] + [
        "", "| | 件数 |", "|---|---:|",
        f"| 取れた | {sum(1 for r in kiroku if r['status'] == 200):,} |",
        f"| 相手が「だめ」と答えた | {sum(1 for r in kiroku if r.get('kotae')):,} |",
        f"| **こちらが出られなかった** | {sum(1 for r in kiroku if r.get('derarenai')):,} |",
        f"| **混んでいて中止した** | {sum(1 for r in kiroku if r.get('konde')):,} |",
        f"| **まだ取っていない組** | {nokori:,} |", "",
        "**「まだ取っていない」を0にしない。** 0にすると、",
        "取っていないことが「無い」に見える（6節 `unobserved`）。", "",
    ]
    if yomenai:
        lines += [f"目録の行のうち **URL を読めなかったもの: {yomenai:,}**。",
                  "読めなかった行を「無かった」と数えない。", ""]

    lines += ["## 同じ市区町村・同じ年度の2本を比べた（案B）", ""]
    if not kumi_kekka:
        lines += ["**まだ1組も比べていない。**", ""]
    for k in kumi_kekka:
        lines += [
            f"### `{k['code']}` {k['name']} ／ {k['nendo']}年度", "",
            f"**判定：{k['hantei']}**", "",
            "| 見たところ | 1本目 | 2本目 | |",
            "|---|---|---|---|",
        ]
        a, b = k["a"], k["b"]
        for key, mei in (("bytes", "大きさ（バイト）"),
                         ("sha256", "SHA-256"),
                         ("nakami_kensuu", "zip の中のファイル数"),
                         ("nakami_yubiwa", "zip の中の一覧の指紋")):
            x, y = a.get(key), b.get(key)
            shirushi = "—" if x is None or y is None else ("○" if x == y else "×")
            fx = "**読めなかった**" if x is None else (f"{x:,}" if isinstance(x, int) else f"`{x[:16]}…`")
            fy = "**読めなかった**" if y is None else (f"{y:,}" if isinstance(y, int) else f"`{y[:16]}…`")
            lines.append(f"| {mei} | {fx} | {fy} | {shirushi} |")
        lines += [
            "", "| | 取得元データセットID |", "|---|---|",
            f"| 1本目 | `{a['dataset_id']}` |",
            f"| 2本目 | `{b['dataset_id']}` |", "",
            "**1組一致しただけで、全市区町村・全年度が同一とは一般化しない。**",
            "別の市区町村か別の年度でも少量確かめてから、",
            "以後片方だけにできるかを改めて決める（統括 2026-09-21）。", "",
        ]

    lines += ["## 取ったものの出典（規約が求める8つ）", "",
              "| データセット名 | 市区町村 | 年度 | ファイル名 | 取得日 |"
              " 取得元データセットID | SHA-256 | 元URL |",
              "|---|---|---:|---|---|---|---|---|"]
    for r in kiroku:
        if r["status"] != 200:
            continue
        sha = r.get("sha256") or "**読めなかった**"
        lines.append(
            f"| {r['dataset']} | `{r['code']}` {r['name']} | {r['nendo']} |"
            f" `{r['filename']}` | {r['totta_hi']} | `{r['dataset_id']}` |"
            f" `{sha}` | {r['url']} |")
    lines += ["", "**この表がそのまま出典になる。**",
              "加工して出すときは、加工した旨も別に書く。", "",
              f"（{hi} 現在）", ""]

    os.makedirs(os.path.dirname(report), exist_ok=True)
    with open(report, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    with open(daicho, "w", encoding="utf-8") as f:
        json.dump({"yakusoku": {k: v for k, v in YAKUSOKU.items()
                                if k != "kinshi"},
                   "kinshi": list(YAKUSOKU["kinshi"]),
                   "kiroku": kiroku, "kumi": kumi_kekka,
                   "mada_totteinai_kumi": nokori,
                   "mokuroku_yomenai_gyo": yomenai},
                  f, ensure_ascii=False, indent=2, sort_keys=True)
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kumi", type=int, default=1,
                    help="比べる組の数。**既定は1。** まとめて叩かない")
    ap.add_argument("--code", help="市区町村コードを指定する（省くと先頭から）")
    ap.add_argument("--nokosu", action="store_true",
                    help="取った zip を inbox に残す（既定は残す）")
    args = ap.parse_args()

    if YAKUSOKU["kekka"] != "取ってよい":
        print(f"規約が「{YAKUSOKU['kekka']}」。取りに行かない")
        return 1

    rows, yomenai = mokuroku()
    if not rows:
        print(f"{MOTO} が読めない。先に chizu_recon.py")
        return 1
    kumi = kasanari(rows)
    if args.code:
        kumi = [k for k in kumi if k[0][0] == args.code]
    if not kumi:
        print("同じ市区町村・同じ年度で2つ以上ある組が、目録の記録に無い")
        return 1

    mato = kumi[:args.kumi]
    print(f"目録の記録から、重なっている組が {len(kumi)} 組 見つかった。"
          f"このうち {len(mato)} 組を取る")

    ok, why = check_robots(mato[0][1][0]["url"])
    if ok is False:
        print("robots.txt が拒否している。取りに行かない")
        return 1
    if ok is None:
        print(f"robots.txt が返らない（{why}）。この回は中止")
        return 1
    print(f"robots：許可（規約とは別の欄として記録する）")

    os.makedirs(OKIBA, exist_ok=True)
    kiroku, kumi_kekka = [], []
    hajimete = True
    for (code, nen), futatsu in mato:
        toreta = []
        for r in futatsu[:2]:
            if not hajimete:
                time.sleep(WAIT)          # **同時1本・5秒以上あける**
            hajimete = False
            rec = dict(r)
            rec["totta_hi"] = datetime.datetime.now(JST).strftime("%Y-%m-%d")
            rec["totta_nichiji"] = datetime.datetime.now(JST).isoformat()
            rec["kansoku_moto"] = os.path.relpath(MOTO, HERE)
            dest = os.path.join(OKIBA, f"{rec['dataset_id']}_{rec['filename']}")
            try:
                st, ctype, lm, etag, n = get(rec["url"], dest)
            except urllib.error.HTTPError as e:
                if is_busy(e):
                    print(f"{e.code} が返った。この回は中止（押し込まない）")
                    rec.update(status=e.code, konde=True)
                    kiroku.append(rec)
                    break
                print(f"× 相手が HTTP {e.code} と答えた")
                rec.update(status=e.code, kotae=True)
                kiroku.append(rec)
                continue
            except Exception as e:                  # noqa: BLE001
                print(f"× 出られなかった（{type(e).__name__}: {e}）")
                rec.update(status=None, derarenai=True)
                kiroku.append(rec)
                continue
            kensuu, yubi, riyuu = nakami(dest)
            rec.update(status=st, content_type=ctype, bytes=n,
                       last_modified=lm, etag=etag,
                       sha256=yubiwa(dest),
                       nakami_kensuu=kensuu, nakami_yubiwa=yubi,
                       nakami_yomenai=riyuu,
                       okiba=os.path.relpath(dest, HERE))
            kiroku.append(rec)
            toreta.append(rec)
            print(f"○ {rec['filename']}  {st} {ctype} {n:,} バイト"
                  f" / zip の中 {kensuu if kensuu is not None else '読めなかった'}"
                  f" / sha256 {rec['sha256'][:16]}…")
            print(f"   {shutten(rec)}")

        if len(toreta) == 2:
            hantei, onaji, chigau, mienai = kuraberu(*toreta)
            kumi_kekka.append({
                "code": code, "nendo": nen, "name": toreta[0]["name"],
                "hantei": hantei, "onaji": onaji, "chigau": chigau,
                "mienai": mienai, "a": toreta[0], "b": toreta[1]})
            print(f"\n判定：**{hantei}**  同じ {onaji} ／ 違う {chigau}"
                  f" ／ 見えなかった {mienai}")
            if hantei == "不一致":
                print("不一致。ここで止める（統括 2026-09-21）")
                break
        else:
            # **比べる相手がそろっていない回は「未判定」。**
            # 「一致」でも「不一致」でもない（正本9節）
            print("2本そろわなかった。この組は未判定")

    lines = kaku(kiroku, kumi_kekka, len(kumi) - len(kumi_kekka), yomenai)
    print("\n".join(lines[:2]))
    print(f"→ {REPORT}")
    print(f"→ {DAICHO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
