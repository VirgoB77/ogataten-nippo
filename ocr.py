#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""紙をスキャンしたPDFから文字を起こす（OCR）。

兵庫県の「資料」PDFは33本中32本が画像で、pdf.py では文字が取れなかった。
神戸市の「届出書」も様式に1文字ずつ置かれていて表にならない。
ここでは Tesseract（日本語）で最初の2ページだけ読む。届出書の1枚目に
名称・所在地・届出者・届出の種類が書いてあり、あとは図面や添付なので要らない。

出力
  data/ocr/<id>/<ファイル名>.txt … 起こした文字そのまま
  data/ocr/<id>.json             … そこから拾った項目（名称・所在地・届出者・種類・日付・面積）

要るもの: tesseract（jpn）と pdftoppm（poppler-utils）。無ければ理由を出して何もしない。
1本1.5秒くらい。8MB級（30ページ超）でも最初の2ページしか描かないので同じ。
"""

import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
FILES = os.path.join(HERE, "data", "files")
OUT = os.path.join(HERE, "data", "ocr")
PAGES = 2
DPI = 200

sys.path.insert(0, HERE)
import pdf as pdflib  # noqa: E402


# 法人かどうかの判定は privacy.py に一本化する。ここに別の一覧を置くと、
# 「㈱」を足したときに片方だけ直して食い違う（共通仕様5節）
sys.path.insert(0, HERE)
from common import privacy


def have_tools():
    missing = [t for t in ("tesseract", "pdftoppm") if not shutil.which(t)]
    if missing:
        return False, f"{', '.join(missing)} が無い（apt-get install tesseract-ocr tesseract-ocr-jpn poppler-utils）"
    langs = subprocess.run(["tesseract", "--list-langs"], capture_output=True, text=True).stdout
    if "jpn" not in langs:
        return False, "tesseract に日本語（jpn）が入っていない"
    return True, ""


def ocr_pdf(path):
    """最初の PAGES ページを描いて読む。文字が埋まっているPDFならそちらを使う。"""
    try:
        rows = pdflib.extract_rows(path)
    except Exception:
        rows = []
    if rows and sum(len("".join(r)) for r in rows) > 80:
        return "\n".join(" ".join(r) for r in rows), "embedded"
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(["pdftoppm", "-r", str(DPI), "-f", "1", "-l", str(PAGES), "-png", path, os.path.join(td, "p")],
                       capture_output=True, timeout=120)
        texts = []
        for png in sorted(glob.glob(os.path.join(td, "p-*.png"))):
            r = subprocess.run(["tesseract", png, "stdout", "-l", "jpn", "--psm", "6"],
                               capture_output=True, text=True, timeout=120)
            texts.append(r.stdout)
    return "\n".join(texts), "ocr"


# 届出書の1枚目から拾う項目。OCRは「!」「昌」のような誤読があるので、ゆるく拾う
PAT = {
    "form":      r"様式第\s*(\d+)",
    "article":   r"第\s*(\d+)\s*条\s*第\s*(\d+)\s*項",
    "date":      r"(令和|平成)\s*(\d{1,2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*[日昌曰]",
    "store":     r"名\s*称\s*[:：]\s*([^\n]{2,40})",
    "address":   r"所\s*在\s*地\s*[:：]\s*([^\n]{2,50})",
    "area":      r"店舗面積[^\d]{0,12}([\d,，]{3,7})\s*(?:㎡|m2|平方)",
    "content":   r"変更\s*した\s*事項\s*\n?([^\n]{2,60})",
}
KIND_BY_FORM = {"1": "新設", "2": "変更", "3": "廃止"}   # 大店立地法施行規則の様式番号


def pick(text):
    out = {}
    m = re.search(PAT["form"], text)
    if m:
        out["form"] = m.group(1)
        out["kind_guess"] = KIND_BY_FORM.get(m.group(1), "")
    m = re.search(PAT["article"], text)
    if m:
        out["article"] = f"第{m.group(1)}条第{m.group(2)}項"
    m = re.search(PAT["date"], text)
    if m:
        base = {"令和": 2018, "平成": 1988}[m.group(1)]
        out["date"] = f"{base + int(m.group(2)):04d}-{int(m.group(3)):02d}-{int(m.group(4)):02d}"
    for k in ("store", "address", "area", "content"):
        m = re.search(PAT[k], text)
        if m:
            out[k] = m.group(1).strip()
    names = applicants_of(text)
    if names:
        out["applicant"] = "／".join(names)
    elif out.get("address"):
        # 届出者が読めていない＝個人かもしれない。merge の apply_privacy と同じ判断で、
        # ここ（data/ocr/<id>.json）の時点で町丁目までに丸める。地番を残さない（3.1）
        out["address"] = privacy.redact_addr(out["address"], "individual")
        out["address_redacted"] = True
    return out


# 様式の項目名。OCRだと「名 称」のように字の間が空くので、空白を許す
_LABEL = re.compile(
    r"^\s*(?:氏\s*名\s*又\s*は\s*名\s*称|名\s*称|氏\s*名|届\s*出\s*者"
    r"|設\s*置\s*者\s*[①②③④⑤一二三四五の]*)\s*[:：]?\s*")
# 代表者の氏名は個人の氏名なので取らない（共通仕様3.1）。
# 肩書きが出てきたら、そこから後ろは全部落とす。
# 協同組合は「組合長理事」、学校法人は「理事長」など、会社と呼び方が違う。
# 一度「生活協同組合コープこうべ／代表者名組合長理事岩山利久」を
# 設置者として出してしまったので、肩書きは広めに入れてある
_REP = re.compile(
    r"(代表取締役|代表執行役|執行役|取締役|代表社員|無限責任社員|業務執行社員"
    r"|代表者名|代表者|代表理事|組合長理事|組合長|理事長|理事|監事|評議員"
    r"|会長|社長|支配人|園長|校長|院長|館長|代表$)")
# OCRが拾う罫線のかけら
_JUNK = re.compile(r"[「」『』|｜│┃╎¦\[\]]")
# 届出者の名乗りが終わる合図
_END = re.compile(r"(大規模小売店舗立地法|法第\s*\d+\s*条|^\s*記\s*$|^\s*下\s*記)")
# 住所の行。名乗りのすぐ下に必ず続くので、取り違えないようにする
_ADDR = re.compile(r"^(住\s*所|所\s*在\s*地|本\s*店)")
_ADDR_SHAPE = re.compile(r"[0-9０-９]+\s*(丁目|番地|番|号)")


def clean_name(line):
    """1行から、設置者の名称だけを取り出す。取れなければ空文字。"""
    v = _JUNK.sub(" ", line)
    v = _LABEL.sub("", v)
    m = _REP.search(v)
    if m:
        v = v[:m.start()]          # 「○○株式会社 代表取締役 …」の後ろを落とす
    v = re.sub(r"[　\s]+", " ", v).strip(" 　:：,、。")
    # 日本語の社名に意味のある空白はほぼ無い。英字どうしの空白だけ残す
    v = re.sub(r"(?<=[^\x00-\x7F])\s+(?=[^\x00-\x7F])", "", v)
    v = re.sub(r"(?<=[^\x00-\x7F])\s+(?=[\x00-\x7F])", "", v)
    v = re.sub(r"(?<=[\x00-\x7F])\s+(?=[^\x00-\x7F])", "", v)
    return v.strip()


def applicants_of(text):
    """届出者（設置者）の名称を取り出す。

    様式第1〜3は「○○知事　様」のあとに届出者が並ぶ。共同で設置するときは
    複数並ぶので、全部取る。代表者の氏名と住所は取らない。

    法人かどうかの判定は privacy.is_corp() に任せる。ここに別の一覧を
    持つと、「㈱」を足したときに片方だけ直して食い違う。
    """
    lines = text.splitlines()
    out = []
    for i, line in enumerate(lines):
        if not re.search(r"(?:知事|市長)\s*[殿様欄宛]?\s*$", line.strip()):
            continue
        for j in range(i + 1, min(i + 14, len(lines))):
            nxt = lines[j]
            if _END.search(nxt):
                break
            name = clean_name(nxt)
            if len(name) < 3 or len(name) > 60:
                continue
            if _ADDR.match(name) or _ADDR_SHAPE.search(name):
                continue                      # 住所の行。名乗りの下に必ず続く
            # ここは privacy.is_corp() より狭く、法人格の語がある行だけを取る。
            # is_corp は「大阪市」のような地方公共団体も真になるので、
            # 「住所 大阪府堺市」を社名として拾ってしまう
            if any(w in name for w in privacy.CORP_WORDS) and name not in out:
                out.append(name)
        if out:
            break
    return out


def main():
    # 「repick」を付けると、PDFを読み直さずに、保存してある .txt から
    # 取り出しだけをやり直す。取り出しの規則を直したときに使う。
    # tesseract も poppler も要らない
    repick = "repick" in sys.argv[1:]
    ok, why = have_tools()
    if not ok and not repick:
        print(f"OCRはしない: {why}")
        return
    with open(os.path.join(HERE, "sources.json"), encoding="utf-8") as f:
        srcs = [s for s in json.load(f)["sources"] if s.get("pdf") and s.get("enabled")]
    args = [a for a in sys.argv[1:] if a != "repick"]
    only = args[0] if args else None

    lines = ["# OCRの結果", ""]
    for s in srcs:
        sid = s["id"]
        if only and only != sid:
            continue
        pdfs = sorted(glob.glob(os.path.join(FILES, sid, "*.pdf")))
        if not pdfs and not repick:
            continue
        d = os.path.join(OUT, sid)
        os.makedirs(d, exist_ok=True)
        done = new = fail = 0
        picked = {}
        jpath = os.path.join(OUT, f"{sid}.json")
        if os.path.exists(jpath):
            with open(jpath, encoding="utf-8") as f:
                picked = json.load(f)
        targets = pdfs if pdfs else (sorted(glob.glob(os.path.join(d, "*.txt"))) if repick else [])
        for p in targets:
            stem = os.path.splitext(os.path.basename(p))[0]
            tpath = os.path.join(d, stem + ".txt")
            if os.path.exists(tpath):
                done += 1
                if repick or stem not in picked:
                    how = (picked.get(stem) or {}).get("how")
                    picked[stem] = pick(open(tpath, encoding="utf-8").read())
                    if how:
                        picked[stem]["how"] = how
                continue
            try:
                text, how = ocr_pdf(p)
            except Exception as e:
                fail += 1
                lines.append(f"  - {stem}: 失敗 {type(e).__name__}")
                continue
            with open(tpath, "w", encoding="utf-8") as f:
                f.write(text)
            picked[stem] = pick(text)
            picked[stem]["how"] = how
            new += 1
        with open(jpath, "w", encoding="utf-8") as f:
            json.dump(picked, f, ensure_ascii=False, indent=1)
        got_store = sum(1 for v in picked.values() if v.get("store"))
        lines.append(f"- **{s['name']}**: 新しく読んだ {new}本 / 読んであった {done}本 / 失敗 {fail}本 / 店名が拾えた {got_store}/{len(picked)}")
    text = "\n".join(lines)
    print(text)
    gh = os.environ.get("GITHUB_STEP_SUMMARY")
    if gh:
        with open(gh, "a", encoding="utf-8") as f:
            f.write("\n" + text + "\n")


if __name__ == "__main__":
    main()
