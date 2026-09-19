# 用途地域の元データ（2026-09-19 に見た）

## A29  https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-A29-v2_1.html
- robots: robots.txt が HTTP 404（無いものとして続ける）
- HTTP 200 / text/html; charset=UTF-8 / 115,500 バイト
- title: 国土数値情報 | 用途地域データ
- a/link の href 184 本 ／ script などの src 12 本 ／ form 1 個
  - form: `<form class="search-form" action="https://www.google.co.jp/cse" name="cse-search-box" target="_blank">`
- href の拡張子: [('html', 96), ('（拡張子なし）', 73), ('pdf', 6), ('cgi', 3), ('css', 2), ('png', 2), ('xlsx', 2)]
- 27／28 を含む href（拡張子を問わず）2 本:
  - `#prefecture27`
  - `#prefecture28`
- ページの実物を置いた → `A29-page.html`（金庫）
- ここでは見つからなかった。次のページも見る

## A29-1  https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-A29.html
- robots: robots.txt が HTTP 404（無いものとして続ける）
- HTTP 200 / text/html; charset=UTF-8 / 74,143 バイト
- title: 国土数値情報 | 用途地域データ
- a/link の href 178 本 ／ script などの src 12 本 ／ form 1 個
  - form: `<form class="search-form" action="https://www.google.co.jp/cse" name="cse-search-box" target="_blank">`
- href の拡張子: [('html', 96), ('（拡張子なし）', 73), ('cgi', 3), ('pdf', 3), ('css', 2), ('png', 1)]
- 27／28 を含む href（拡張子を問わず）2 本:
  - `#prefecture27`
  - `#prefecture28`
- ページの実物を置いた → `A29-1-page.html`（金庫）
- ここでは見つからなかった。次のページも見る

## A29-2  https://nlftp.mlit.go.jp/ksj/index.html
- robots: robots.txt が HTTP 404（無いものとして続ける）
- HTTP 200 / text/html; charset=UTF-8 / 143,180 バイト
- title: 国土数値情報ダウンロードサイト
- a/link の href 446 本 ／ script などの src 23 本 ／ form 1 個
  - form: `<form class="search-form" action="https://www.google.co.jp/cse" name="cse-search-box" target="_blank">`
- href の拡張子: [('html', 391), ('（拡張子なし）', 43), ('css', 4), ('pdf', 4), ('cgi', 3), ('xlsx', 1)]
- 27／28 を含む href（拡張子を問わず）5 本:
  - `./gml/datalist/KsjTmplt-A27-2023.html`
  - `./gml/datalist/KsjTmplt-P28-2022.html`
  - `./gml/datalist/KsjTmplt-P27.html`
  - `./gml/datalist/KsjTmplt-A28.html`
  - `./gml/datalist/KsjTmplt-C28-2021.html`
- ページの実物を置いた → `A29-2-page.html`（金庫）
- ページの中の zip リンク（全部）: 0 本
- 大阪府（27）: 0 本
  - **見つからなかった。ページの作りが変わったかもしれない**
- 兵庫県（28）: 0 本
  - **見つからなかった。ページの作りが変わったかもしれない**

## ISJ  https://nlftp.mlit.go.jp/isj/
- robots: robots.txt が HTTP 404（無いものとして続ける）
- HTTP 200 / text/html; charset=UTF-8 / 26,936 バイト
- title: 位置参照情報とは
- a/link の href 120 本 ／ script などの src 12 本 ／ form 1 個
  - form: `<form class="search-form" action="https://www.google.co.jp/cse" name="cse-search-box" target="_blank">`
- href の拡張子: [('html', 88), ('（拡張子なし）', 24), ('cgi', 4), ('css', 2), ('pdf', 2)]
- 27／28 を含む href（拡張子を問わず）0 本:
- ページの実物を置いた → `ISJ-page.html`（金庫）
- ここでは見つからなかった。次のページも見る

## ISJ-1  https://nlftp.mlit.go.jp/isj/index.html
- robots: robots.txt が HTTP 404（無いものとして続ける）
- HTTP 200 / text/html; charset=UTF-8 / 26,936 バイト
- title: 位置参照情報とは
- a/link の href 120 本 ／ script などの src 12 本 ／ form 1 個
  - form: `<form class="search-form" action="https://www.google.co.jp/cse" name="cse-search-box" target="_blank">`
- href の拡張子: [('html', 88), ('（拡張子なし）', 24), ('cgi', 4), ('css', 2), ('pdf', 2)]
- 27／28 を含む href（拡張子を問わず）0 本:
- ページの実物を置いた → `ISJ-1-page.html`（金庫）
- ページの中の zip リンク（全部）: 0 本
- 大阪府（27）: 0 本
  - **見つからなかった。ページの作りが変わったかもしれない**
- 兵庫県（28）: 0 本
  - **見つからなかった。ページの作りが変わったかもしれない**

## 次にやること

この報告を読んでから、当てるコードを書く（属性名・座標系・番地の粒度を見る）。
**取れたものは `zoning` には入れない。** 届出が言ったことと、いまの地図が
言うことは別（共通仕様3.5）。入れるなら `zoning_now` と `zoning_asof`。
