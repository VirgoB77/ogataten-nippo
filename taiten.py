#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""退店（廃止）の一覧を作る。

大規模小売店舗立地法の「廃止」届出を、閉じた日の新しい順に並べる。
役所の縦覧は数か月で消えるが、こちらは消えない（共通仕様1節）。

**開店日が分かるものだけ「何年もったか」を出す。**
同じ場所の「新設」届出と突き合わせるが、**町丁目の一致だけでは信用しない**
（同じ町丁目の別の店を拾う。実測で 55件中 46件が店名不一致だった）。
店名も一致したものだけを繋ぐ。

**個人の設置者には「何年いたか」を出さない**（共通仕様3.1）。
「誰がいつまでそこにいたか」になる。一覧には出す（住所は町丁目まで丸めてある）。
"""
import json, os, sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "common"))
import addr as addrlib
import privacy

HERE = os.path.dirname(os.path.abspath(__file__))
ALL = os.path.join(HERE, "data", "all.json")
OUT = os.path.join(HERE, "data", "taiten.json")

TSUBO = 3.305785


def norm(r, field):
    """住所の突き合わせキー。取れなければ None。"""
    try:
        return addrlib.normalize(r.get("pref", ""), r.get("city", ""),
                                 r.get("address", "")).get(field)
    except Exception:
        return None


def day(r):
    """その届出の「起きた日」。event_on を優先し、無ければ届出日。"""
    return r.get("event_on") or r.get("notified_on")


def build(recs):
    closed = [r for r in recs if r.get("kind") == "廃止"]
    opened = [r for r in recs if r.get("kind") == "新設"]

    # 新設を「番地キー + 店名」で引けるようにする。町丁目だけでは繋がない
    idx = {}
    for r in opened:
        store = (r.get("store") or "").strip()
        if not store:
            continue
        for f in ("addr_key", "addr_key_town"):
            k = norm(r, f)
            if k:
                idx.setdefault((k, store), []).append(r)

    out, matched = [], 0
    for r in closed:
        store = (r.get("store") or "").strip()
        kind = r.get("operator_kind")
        rec = {
            "id": r.get("key"),
            "store": store,
            "addr": r.get("address") or "",
            "city": r.get("city") or "",
            "pref": r.get("pref") or "",
            "closed_on": day(r),
            "notified_on": r.get("notified_on"),
            "area_m2": r.get("area_m2"),
            "area_tsubo": (round(r["area_m2"] / TSUBO, 1)
                           if isinstance(r.get("area_m2"), (int, float)) else None),
            "operator": r.get("operator_display") or "",
            "operator_kind": kind,
            "source_url": r.get("source_url"),
            "fetched_on": r.get("fetched_on"),
            "opened_on": None,
            "lasted_days": None,
            "match": None,
        }

        # 開店日を探す。店名が一致するものだけ
        for f in ("addr_key", "addr_key_town"):
            k = norm(r, f)
            cand = idx.get((k, store)) if k else None
            if not cand:
                continue
            o = min((day(c) for c in cand if day(c)), default=None)
            if not o or not rec["closed_on"] or o >= rec["closed_on"]:
                continue
            rec["match"] = "番地+店名" if f == "addr_key" else "町丁目+店名"
            # 3.1：個人の設置者には「何年いたか」を出さない
            if kind != "individual":
                rec["opened_on"] = o
                rec["lasted_days"] = (date.fromisoformat(rec["closed_on"])
                                      - date.fromisoformat(o)).days
                matched += 1
            break
        out.append(rec)

    out.sort(key=lambda x: (x["closed_on"] or ""), reverse=True)
    return out, matched


def main():
    with open(ALL, encoding="utf-8") as f:
        recs = json.load(f)
    rows, matched = build(recs)
    doc = {"generated_at": date.today().isoformat(), "count": len(rows), "records": rows}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))

    ind = sum(1 for r in rows if r["operator_kind"] == "individual")
    with_area = sum(1 for r in rows if r["area_m2"])
    print(f"退店 {len(rows)} 件  →  {OUT}")
    print(f"  開店日が分かった（法人のみ）  {matched}")
    print(f"  個人の設置者（年数は出さない） {ind}")
    print(f"  面積あり                      {with_area}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
