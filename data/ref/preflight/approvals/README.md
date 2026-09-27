# 取得可否確認の許可の置き場

**許可を出せるのは運営者だけ**（`approved_by: operator`）。運営者がはっきり許可した中身を、
運営者・Codex・Claude などが転記してよい。転記した者は `entered_by` に書く（2026-09-27）。
**commit した者から、許可した者を推し量らない。** 自動実行は、ここには書かない。

許可1つにつき、ファイル1つ。ファイル名は許可ID（英小文字・数字・`-`）＋ `.json`。

```json
{
 "approval_id": "value-domain-2026-09-28-1",
 "source_id": "value-domain",
 "purpose": "acquisition_preflight",
 "approved_by": "operator",
 "entered_by": "codex",
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

- `approval_id` がファイル名と同じ。`purpose` が `acquisition_preflight`、`single_use` が `true`
- `approved_by` が `operator`（AI・Codex などを許可した者として書いた許可は効かない）。`entered_by` が書いてある
- `allowed_kinds` は `robots`・`list`・`detail` から（`robots` は必ず入れる）。`max_requests` はその数まで
- `min_interval_seconds` は 5 以上
- `expires_at` は `issued_at` から **24時間以内**。いまがその間にある（時差 `+09:00` まで書く）
- `card_version` と `card_fingerprint` が、**いまのカード**と一致する（許可のあとでカードが変わったら効かない）
- **まだ使っていない**。**実行を始めたら使用済み**（外へ1本も出さずに止まった回も）。
  記録か予約台帳にこの許可IDの跡があれば、2回目は止まる。もう一度確かめるときは、**新しい許可ID**で書く
- このファイルが保存（commit）されていて、保存したあとで書き換えられていない

どれか1つでも欠けたら、門は**1本も出さずに止まる**（止まったことは記録に残る）。

## 門が確かめないこと

**運営者が本当に許可したかは、門には分からない。** 門が読むのはファイルの中身と、それが保存されていることだけ。
許可を受けてから転記する、という運用の手順で担保する。

## 2026-09-27 の4件（value-domain・muumuu-domain・onamae-com・xserver-domain の -preflight-1）

運営者がチャットで許可し、Codex が転記した。`approved_by`・`entered_by` の欄ができる前の形（`issued_by`）のまま、
**書き換えずに残している**（実行の記録として）。4件とも使用済みで、いまの門では通らない。本番の承認には使っていない。
