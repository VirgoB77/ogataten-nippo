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
- **`.cgi` の実物 1 本**（数ではなく URL そのもの）:
  - `/cgi-bin/isj/dls/_choose_method.cgi`
- **script の src 5 本**（どれが URL を組み立てているか）:
  - `https://cdnjs.cloudflare.com/ajax/libs/materialize/1.0.0-rc.2/js/materialize.min.js`
  - `https://ajax.googleapis.com/ajax/libs/jquery/3.7.1/jquery.min.js`
  - `https://tebot.jp/api/bot/1274/chat_embed_v8?lang=undefined&open_default=true&code=6eef28be8d4ae2512548634790c3a7c8`
  - `../../../ksj/js/gis.js`
  - `/__zenedge/assets/f.js?v=1674207422`
- **27 の印のまわり**（前後を切り出した実物）:
  ```html
  <span id="A29-19_26_GML.zip-close" style="display: none">
  <i class="material-icons">star</i>
  </span>
  </a>
  </td>
  </tr>
  <tr>
  <td class="bgc6" id="prefecture27">大阪</td>
  <td class="txtCenter">世界測地系</td>
  <td class="txtCenter">平成23年</td>
  <td class="txtCenter">3.77MB</td>
  <td class="txtCenter">A29-11_27_GML.zip</td>
  <td class="txtCenter">
  <a class="waves-effect waves-light btn indigo btn_padding" id="menu-button" onclick="javascript:DownLd('3.77MB','A29-11_27_GML.zip','../data/A29/A29-11/A29-11_27_GML.zip' ,this);">
  <span id="A29-11_27_GML.zip-open" style="display: block">
  <i class="material-icons">file_download</i>
  </span>
  <span id="A29-11_27_GML.zip-close" style="display: none">
  <i class="material-icons">star</i>
  </span>
  ```
- **28 の印のまわり**（前後を切り出した実物）:
  ```html
  <span id="A29-19_27_GML.zip-close" style="display: none">
  <i class="material-icons">star</i>
  </span>
  </a>
  </td>
  </tr>
  <tr>
  <td class="bgc6" id="prefecture28">兵庫</td>
  <td class="txtCenter">世界測地系</td>
  <td class="txtCenter">平成23年</td>
  <td class="txtCenter">3.08MB</td>
  <td class="txtCenter">A29-11_28_GML.zip</td>
  <td class="txtCenter">
  <a class="waves-effect waves-light btn indigo btn_padding" id="menu-button" onclick="javascript:DownLd('3.08MB','A29-11_28_GML.zip','../data/A29/A29-11/A29-11_28_GML.zip' ,this);">
  <span id="A29-11_28_GML.zip-open" style="display: block">
  <i class="material-icons">file_download</i>
  </span>
  <span id="A29-11_28_GML.zip-close" style="display: none">
  <i class="material-icons">star</i>
  </span>
  ```
- **中に書かれた script 2 個、うち zip/download に触れるもの 0 個**
- **ページ全体（href に限らず）で、探している形に当たるもの 188 本**:
  - `A29-11_01_GML.zip`
  - `A29-11/A29-11_01_GML.zip`
  - `A29-19_01_GML.zip`
  - `A29-19/A29-19_01_GML.zip`
  - `A29-11_02_GML.zip`
  - `A29-11/A29-11_02_GML.zip`
  - `A29-19_02_GML.zip`
  - `A29-19/A29-19_02_GML.zip`
  - `A29-11_03_GML.zip`
  - `A29-11/A29-11_03_GML.zip`
  - `A29-19_03_GML.zip`
  - `A29-19/A29-19_03_GML.zip`
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
- **`.cgi` の実物 1 本**（数ではなく URL そのもの）:
  - `/cgi-bin/isj/dls/_choose_method.cgi`
- **script の src 5 本**（どれが URL を組み立てているか）:
  - `https://cdnjs.cloudflare.com/ajax/libs/materialize/1.0.0-rc.2/js/materialize.min.js`
  - `https://ajax.googleapis.com/ajax/libs/jquery/3.7.1/jquery.min.js`
  - `https://tebot.jp/api/bot/1274/chat_embed_v8?lang=undefined&open_default=true&code=6eef28be8d4ae2512548634790c3a7c8`
  - `../../../ksj/js/gis.js`
  - `/__zenedge/assets/f.js?v=1674207422`
- **27 の印のまわり**（前後を切り出した実物）:
  ```html
  <span id="A29-11_26_GML.zip-close" style="display: none">
  <i class="material-icons">star</i>
  </span>
  </a>
  </td>
  </tr>
  <tr>
  <td class="bgc6" id="prefecture27">大阪</td>
  <td class="txtCenter">世界測地系</td>
  <td class="txtCenter">平成23年</td>
  <td class="txtCenter">3.77MB</td>
  <td class="txtCenter">A29-11_27_GML.zip</td>
  <td class="txtCenter">
  <a class="waves-effect waves-light btn indigo btn_padding" id="menu-button" onclick="javascript:DownLd('3.77MB','A29-11_27_GML.zip','../data/A29/A29-11/A29-11_27_GML.zip' ,this);">
  <span id="A29-11_27_GML.zip-open" style="display: block">
  <i class="material-icons">file_download</i>
  </span>
  <span id="A29-11_27_GML.zip-close" style="display: none">
  <i class="material-icons">star</i>
  </span>
  ```
- **28 の印のまわり**（前後を切り出した実物）:
  ```html
  <span id="A29-11_27_GML.zip-close" style="display: none">
  <i class="material-icons">star</i>
  </span>
  </a>
  </td>
  </tr>
  <tr>
  <td class="bgc6" id="prefecture28">兵庫</td>
  <td class="txtCenter">世界測地系</td>
  <td class="txtCenter">平成23年</td>
  <td class="txtCenter">3.08MB</td>
  <td class="txtCenter">A29-11_28_GML.zip</td>
  <td class="txtCenter">
  <a class="waves-effect waves-light btn indigo btn_padding" id="menu-button" onclick="javascript:DownLd('3.08MB','A29-11_28_GML.zip','../data/A29/A29-11/A29-11_28_GML.zip' ,this);">
  <span id="A29-11_28_GML.zip-open" style="display: block">
  <i class="material-icons">file_download</i>
  </span>
  <span id="A29-11_28_GML.zip-close" style="display: none">
  <i class="material-icons">star</i>
  </span>
  ```
- **中に書かれた script 2 個、うち zip/download に触れるもの 0 個**
- **ページ全体（href に限らず）で、探している形に当たるもの 94 本**:
  - `A29-11_01_GML.zip`
  - `A29-11/A29-11_01_GML.zip`
  - `A29-11_02_GML.zip`
  - `A29-11/A29-11_02_GML.zip`
  - `A29-11_03_GML.zip`
  - `A29-11/A29-11_03_GML.zip`
  - `A29-11_04_GML.zip`
  - `A29-11/A29-11_04_GML.zip`
  - `A29-11_05_GML.zip`
  - `A29-11/A29-11_05_GML.zip`
  - `A29-11_06_GML.zip`
  - `A29-11/A29-11_06_GML.zip`
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
- **`.cgi` の実物 1 本**（数ではなく URL そのもの）:
  - `/cgi-bin/isj/dls/_choose_method.cgi`
- **script の src 7 本**（どれが URL を組み立てているか）:
  - `https://cdnjs.cloudflare.com/ajax/libs/materialize/1.0.0-rc.2/js/materialize.min.js`
  - `https://ajax.googleapis.com/ajax/libs/jquery/3.7.1/jquery.min.js`
  - `//cdn.jsdelivr.net/npm/slick-carousel@1.8.1/slick/slick.min.js`
  - `https://tebot.jp/api/bot/1274/chat_embed_v8?lang=undefined&open_default=true&code=6eef28be8d4ae2512548634790c3a7c8`
  - `https://cse.google.com/cse.js?cx=ec63825938b5a5e25`
  - `../ksj/js/gis.js`
  - `/__zenedge/assets/f.js?v=1674207422`
- **中に書かれた script 2 個、うち zip/download に触れるもの 0 個**
- **ページ全体（href に限らず）で、探している形に当たるもの 0 本**:
  - （無し。**配り方が変わった**と見てよい）
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
- **`.cgi` の実物 1 本**（数ではなく URL そのもの）:
  - `/cgi-bin/isj/dls/_choose_method.cgi`
- **script の src 5 本**（どれが URL を組み立てているか）:
  - `https://cdnjs.cloudflare.com/ajax/libs/materialize/1.0.0-rc.2/js/materialize.min.js`
  - `https://ajax.googleapis.com/ajax/libs/jquery/3.7.1/jquery.min.js`
  - `https://tebot.jp/api/bot/1274/chat_embed_v8?lang=undefined&open_default=true&code=6eef28be8d4ae2512548634790c3a7c8`
  - `/ksj/js/gis.js`
  - `/__zenedge/assets/f.js?v=1674207422`
- **中に書かれた script 2 個、うち zip/download に触れるもの 0 個**
- **ページ全体（href に限らず）で、探している形に当たるもの 0 本**:
  - （無し。**配り方が変わった**と見てよい）
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
- **`.cgi` の実物 1 本**（数ではなく URL そのもの）:
  - `/cgi-bin/isj/dls/_choose_method.cgi`
- **script の src 5 本**（どれが URL を組み立てているか）:
  - `https://cdnjs.cloudflare.com/ajax/libs/materialize/1.0.0-rc.2/js/materialize.min.js`
  - `https://ajax.googleapis.com/ajax/libs/jquery/3.7.1/jquery.min.js`
  - `https://tebot.jp/api/bot/1274/chat_embed_v8?lang=undefined&open_default=true&code=6eef28be8d4ae2512548634790c3a7c8`
  - `/ksj/js/gis.js`
  - `/__zenedge/assets/f.js?v=1674207422`
- **中に書かれた script 2 個、うち zip/download に触れるもの 0 個**
- **ページ全体（href に限らず）で、探している形に当たるもの 0 本**:
  - （無し。**配り方が変わった**と見てよい）
- ページの中の zip リンク（全部）: 0 本
- 大阪府（27）: 0 本
  - **見つからなかった。ページの作りが変わったかもしれない**
- 兵庫県（28）: 0 本
  - **見つからなかった。ページの作りが変わったかもしれない**

## 次にやること

この報告を読んでから、当てるコードを書く（属性名・座標系・番地の粒度を見る）。
**取れたものは `zoning` には入れない。** 届出が言ったことと、いまの地図が
言うことは別（共通仕様3.5）。入れるなら `zoning_now` と `zoning_asof`。
