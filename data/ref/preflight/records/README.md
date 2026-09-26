# 取得可否確認の記録

門（`common/kado.py` の `Kado.kakunin`）が書く。**1回の確認で1ファイル。上書きしない**（再確認は新しいファイル）。
手で直さない。

**本文は残さない。** 残すのは、そのとき何を確かめたかを照らし合わせる材料（SHA-256 と長さ）だけ。

| 欄 | 中身 |
| --- | --- |
| `source_id`・`approval_id` | どの相手を、どの許可で |
| `run` | 実行した置き場・実行ID・試行・job・workflow |
| `started_at`・`finished_at` | 日本時間 |
| `external_requests` | 外へ出した本数 |
| `result`・`stop_reason` | `完了` か `STOP` と、止めた理由 |
| `robots` | **観測した事実**（`requested_url`・`final_url`・`checked_at`・`http_status`・`content_type`・`redirect`・`redirect_to`・`body_sha256`・`response_kind`）と、**鯨屋の決まりでの判定**（`kujiraya_judgment`・`judgment_reason`・`target_allowed`）を分けて持つ |
| `pages` | 一覧・詳細ごとの `requested_url`・`final_url`・`http_status`・`content_type`・`redirect`・`auth_required`・`captcha`・`items`（確かめる語の有無）・`stop_reason`・`body_sha256` |

`response_kind` は `valid_robots`・`html_response`・`not_found`・`denied`・`redirect`・`unavailable`・`other`。
**HTTP 200 は「robots が通す」ではない。** 200 でも中身が HTML なら `html_response`・判定は「確かめられなかった」で止まる。
**404 は「robots が許した」でもない。** `response_kind` は `not_found`、判定は「robots.txt なし（今の決まりで次へ進む）」。
404 のほかの 4xx（410 を含む）は進まない。

`items` は「本文にその語が有ったか」だけ。**その項目がそのページで取れる、という意味ではない。**
`false` は「今回の通常の HTTP 応答では確認できなかった」まで。**その項目が無い、とは読まない**
（JavaScript は実行しない。後から読み込む項目は、この1本では見えない）。

記録が1つでもある許可は、使用済み（外へ出した本数によらない）。

この記録は、取得してよいかを判断する材料。**本番の取得・private 長期保存・公開・商品化の承認ではない。**
