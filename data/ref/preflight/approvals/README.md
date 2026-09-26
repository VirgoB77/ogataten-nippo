# 取得可否確認の許可の置き場

**ここに置くのは、運営者本人だけ。** PC参謀（AI）も、リサーチも、自動実行も、ここには書かない。

許可1つにつき、ファイル1つ。ファイル名は許可ID（英小文字・数字・`-`）＋ `.json`。
中身は PC参謀が枠に出す。運営者は、その枠をそのまま貼って保存する。

```json
{
 "approval_id": "value-domain-2026-09-28-1",
 "source_id": "value-domain",
 "purpose": "acquisition_preflight",
 "issued_by": "operator",
 "issued_at": "2026-09-28T10:00:00+09:00",
 "expires_at": "2026-09-29T10:00:00+09:00",
 "allowed_kinds": ["robots", "list", "detail"],
 "max_requests": 3,
 "min_interval_seconds": 5,
 "single_use": true,
 "card_version": 1,
 "card_fingerprint": "（カードの指紋。PC参謀が出す64文字）"
}
```

## この許可が効く条件（`common/kado.py` が毎回確かめる）

- `approval_id` がファイル名と同じ。`purpose` が `acquisition_preflight`、`issued_by` が `operator`、`single_use` が `true`
- `allowed_kinds` は `robots`・`list`・`detail` から（`robots` は必ず入れる）。`max_requests` はその数まで
- `min_interval_seconds` は 5 以上
- `expires_at` は `issued_at` から **24時間以内**。いまがその間にある（時差 `+09:00` まで書く）
- `card_version` と `card_fingerprint` が、**いまのカード**と一致する（許可のあとでカードが変わったら効かない）
- **まだ使っていない**（外へ1本でも出した記録・予約台帳の跡があれば、2回目は止まる）
- このファイルを入れた保存に **AI の印**（`Co-Authored-By: Claude` など）が無く、**自動実行**のものでもない。保存したあとで書き換えていない

どれか1つでも欠けたら、門は**1本も出さずに止まる**（止まったことは記録に残る）。

## 限界

AI も運営者と同じ GitHub の鍵で動いている。**AI の印を付けずに保存されたもの**は、機械では見分けられない。
AI は、このフォルダに書かないことを決まりにしている。
