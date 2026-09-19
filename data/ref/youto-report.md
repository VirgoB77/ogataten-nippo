# 用途地域の元データ（2026-09-19 に見た）

## A29  https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-A29-v2_1.html
- robots: robots.txt が読めなかった URLError（続ける）
- 一覧ページが読めなかった：URLError <urlopen error Tunnel connection failed: 403 Forbidden>

## ISJ  https://nlftp.mlit.go.jp/isj/
- robots: robots.txt が読めなかった URLError（続ける）
- 一覧ページが読めなかった：URLError <urlopen error Tunnel connection failed: 403 Forbidden>

## 次にやること

この報告を読んでから、当てるコードを書く（属性名・座標系・番地の粒度を見る）。
**取れたものは `zoning` には入れない。** 届出が言ったことと、いまの地図が
言うことは別（共通仕様3.5）。入れるなら `zoning_now` と `zoning_asof`。
