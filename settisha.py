#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""設置者と小売業者が別の届出を、店ごとにまとめる。

大規模小売店舗立地法の届出には「設置者」（建物を用意した人）と
「小売業者」（店をやる人）が別の欄で入る。両方あって、別のものだけを見る。
数は走らせれば出る（9節「実測値を説明文に書かない」）。

**これは「賃貸物件の一覧」ではない**（共通仕様3.3「見出しで性質が変わる」）。
デベロッパーと核テナントの関係、同じ企業グループ内で会社が分かれている形も
同じように見える。**「建物を用意した人と店をやる人が別」までが、
データが言っていること。**

届出は同じ店に何度も出る（新設・変更・承継・廃止）。
**そのまま数えると同じ店を何度も数える。** 店名＋番地でまとめ直す。

まとめる鍵は番地まで見る。町丁目でまとめ直したら 733店が 657店に減った
（2026-09-19）。**減った 76店は、同じ町丁目の別の店に吸われたもの。**

時間の値打ちはここにある（共通仕様1節）。

    設置者が途中で変わった店    建物の持ち主が変わった
    小売業者が途中で変わった店  店をやる人が変わった
"""
import json, os, sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "common"))
import addr as addrlib

HERE = os.path.dirname(os.path.abspath(__file__))
ALL = os.path.join(HERE, "data", "all.json")
OUT = os.path.join(HERE, "data", "settisha.json")
TSUBO = 3.305785


def key(r):
    try:
        return addrlib.normalize(r.get("pref", ""), r.get("city", ""),
                                 r.get("address", "")).get("addr_key")
    except Exception:
        return None


def day(r):
    return r.get("event_on") or r.get("notified_on")


def name(r, field):
    """画面に出す名前。個人は merge の時点で「個人」になっている（3.1）。"""
    return (r.get(field + "_display") or r.get(field) or "").strip()


def build(recs):
    split = [r for r in recs
             if r.get("operator") and r.get("retailer")
             and str(r["operator"]).strip() != str(r["retailer"]).strip()]

    groups = {}
    for r in split:
        store = (r.get("store") or "").strip()
        k = key(r)
        if not store or not k:
            continue
        groups.setdefault((store, k), []).append(r)

    out = []
    for (store, k), rows in groups.items():
        rows.sort(key=lambda x: (day(x) or "", x.get("notified_on") or ""))
        last = rows[-1]
        ops = [name(x, "operator") for x in rows if name(x, "operator")]
        rets = [name(x, "retailer") for x in rows if name(x, "retailer")]

        out.append({
            "store": store,
            "addr_key": k,
            "addr": last.get("address") or "",
            "city": last.get("city") or "",
            "pref": last.get("pref") or "",
            "operator_now": ops[-1] if ops else "",
            "retailer_now": rets[-1] if rets else "",
            # 個人かどうかは画面に出す名前だけでは分からない。検査が
            # 「個人の店に番地が出ていないか」を見られるように、
            # 判定そのものを持たせる（taiten.json と同じ形）
            "operator_kind": last.get("operator_kind"),
            "retailer_kind": last.get("retailer_kind"),
            # 途中で変わった回数。同じ名前が続くぶんは数えない
            "operator_changes": len(dict.fromkeys(ops)) - 1 if ops else 0,
            "retailer_changes": len(dict.fromkeys(rets)) - 1 if rets else 0,
            "area_m2": last.get("area_m2"),
            "area_tsubo": (round(last["area_m2"] / TSUBO, 1)
                           if isinstance(last.get("area_m2"), (int, float)) else None),
            "zoning": last.get("zoning") or "",
            "first_on": day(rows[0]),
            "last_on": day(last),
            "notices": len(rows),
            "history": [{
                "date": day(x),
                "kind": x.get("kind"),
                "operator": name(x, "operator"),
                "retailer": name(x, "retailer"),
                "operator_kind": x.get("operator_kind"),
                "retailer_kind": x.get("retailer_kind"),
            } for x in rows],
            "source_url": last.get("source_url"),
            "fetched_on": last.get("fetched_on"),
        })

    out.sort(key=lambda x: (x["last_on"] or ""), reverse=True)
    return out


def main():
    with open(ALL, encoding="utf-8") as f:
        recs = json.load(f)
    rows = build(recs)
    doc = {"generated_at": date.today().isoformat(), "count": len(rows), "stores": rows}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))

    oc = sum(1 for r in rows if r["operator_changes"])
    rc = sum(1 for r in rows if r["retailer_changes"])
    print(f"設置者と小売業者が別の店 {len(rows)} 件  →  {OUT}")
    print(f"  設置者が途中で変わった店    {oc}")
    print(f"  小売業者が途中で変わった店  {rc}")
    print(f"  面積あり                    {sum(1 for r in rows if r['area_m2'])}")
    print(f"  用途地域あり                {sum(1 for r in rows if r['zoning'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
