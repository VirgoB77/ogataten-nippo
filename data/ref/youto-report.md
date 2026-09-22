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
- ページの中の zip リンク（全部）: 0 本
- 大阪府（27）: 2 本
  - 候補: `https://nlftp.mlit.go.jp/ksj/gml/data/A29/A29-11/A29-11_27_GML.zip`
  - 候補: `https://nlftp.mlit.go.jp/ksj/gml/data/A29/A29-19/A29-19_27_GML.zip`
  - **選んだ**（いちばん新しい）:
  - https://nlftp.mlit.go.jp/ksj/gml/data/A29/A29-19/A29-19_27_GML.zip
  - 大きさ: 11,474,366 バイト
  - 落とした → `A29-27.zip`（11,474,366 バイト）
  - 中身 258 件: A29-19_27/, A29-19_27/01-01_âVâFü[âvâtâ@âCâïî`Ä«/, 01_âVâFü[âvâtâ@âCâïî`Ä«/A29-19_27140.dbf, 01_âVâFü[âvâtâ@âCâïî`Ä«/A29-19_27140.prj, 01_âVâFü[âvâtâ@âCâïî`Ä«/A29-19_27140.shp, 01_âVâFü[âvâtâ@âCâïî`Ä«/A29-19_27140.shx, 01_âVâFü[âvâtâ@âCâïî`Ä«/A29-19_27202.dbf, 01_âVâFü[âvâtâ@âCâïî`Ä«/A29-19_27202.prj, 01_âVâFü[âvâtâ@âCâïî`Ä«/A29-19_27202.shp, 01_âVâFü[âvâtâ@âCâïî`Ä«/A29-19_27202.shx, 01_âVâFü[âvâtâ@âCâïî`Ä«/A29-19_27203.dbf, 01_âVâFü[âvâtâ@âCâïî`Ä«/A29-19_27203.prj
- 兵庫県（28）: 2 本
  - 候補: `https://nlftp.mlit.go.jp/ksj/gml/data/A29/A29-11/A29-11_28_GML.zip`
  - 候補: `https://nlftp.mlit.go.jp/ksj/gml/data/A29/A29-19/A29-19_28_GML.zip`
  - **選んだ**（いちばん新しい）:
  - https://nlftp.mlit.go.jp/ksj/gml/data/A29/A29-19/A29-19_28_GML.zip
  - 大きさ: 9,985,745 バイト
  - 落とした → `A29-28.zip`（9,985,745 バイト）
  - 中身 180 件: A29-19_28/, A29-19_28/01-01_âVâFü[âvâtâ@âCâïî`Ä«/, 01_âVâFü[âvâtâ@âCâïî`Ä«/A29-19_28100.dbf, 01_âVâFü[âvâtâ@âCâïî`Ä«/A29-19_28100.prj, 01_âVâFü[âvâtâ@âCâïî`Ä«/A29-19_28100.shp, 01_âVâFü[âvâtâ@âCâïî`Ä«/A29-19_28100.shx, 01_âVâFü[âvâtâ@âCâïî`Ä«/A29-19_28202.dbf, 01_âVâFü[âvâtâ@âCâïî`Ä«/A29-19_28202.prj, 01_âVâFü[âvâtâ@âCâïî`Ä«/A29-19_28202.shp, 01_âVâFü[âvâtâ@âCâïî`Ä«/A29-19_28202.shx, 01_âVâFü[âvâtâ@âCâïî`Ä«/A29-19_28203.dbf, 01_âVâFü[âvâtâ@âCâïî`Ä«/A29-19_28203.prj

## ISJ  https://nlftp.mlit.go.jp/cgi-bin/isj/dls/_choose_method.cgi
- robots: robots.txt が HTTP 404（無いものとして続ける）
- HTTP 200 / text/html / 19,181 バイト
- title: ���ֻ��Ⱦ��� ����������ɥ����ӥ�
- a/link の href 96 本 ／ script などの src 9 本 ／ form 3 個
  - form: `<form name="nextform" method="post" action="_view_cities_wards.cgi">`
  - form: `<form name="nextform" method="post" action="_view_prefecturesmap.cgi">`
  - form: `<form name="nextform" method="post" action="_view_cities_wards.cgi">`
- href の拡張子: [('html', 83), ('（拡張子なし）', 6), ('cgi', 3), ('css', 2), ('pdf', 2)]
- 27／28 を含む href（拡張子を問わず）0 本:
- ページの実物を置いた → `ISJ-page.html`（金庫）
- **`.cgi` の実物 3 本**（数ではなく URL そのもの）:
  - `/cgi-bin/isj/dls/_choose_method.cgi`
  - `_view_cities_wards.cgi`
  - `_view_prefecturesmap.cgi`
- **script の src 6 本**（どれが URL を組み立てているか）:
  - `https://cdnjs.cloudflare.com/ajax/libs/materialize/1.0.0-rc.2/js/materialize.min.js`
  - `https://ajax.googleapis.com/ajax/libs/jquery/3.7.1/jquery.min.js`
  - `https://www.googletagmanager.com/gtag/js?id=G-3VVREG6PN8`
  - `https://tebot.jp/api/bot/1274/chat_embed_v8?lang=undefined&open_default=true&code=6eef28be8d4ae2512548634790c3a7c8`
  - `../../../ksj/js/gis.js`
  - `/__zenedge/assets/f.js?v=1674207422`
- **中に書かれた script 2 個、うち zip/download に触れるもの 0 個**
- **ページ全体（href に限らず）で、探している形に当たるもの 0 本**:
  - （無し。**配り方が変わった**と見てよい）
- ここでは見つからなかった。次のページも見る

## ISJ-1  https://nlftp.mlit.go.jp/isj/
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
- ここでは見つからなかった。次のページも見る

## ISJ-2  https://nlftp.mlit.go.jp/isj/index.html
- robots: robots.txt が HTTP 404（無いものとして続ける）
- HTTP 200 / text/html; charset=UTF-8 / 26,936 バイト
- title: 位置参照情報とは
- a/link の href 120 本 ／ script などの src 12 本 ／ form 1 個
  - form: `<form class="search-form" action="https://www.google.co.jp/cse" name="cse-search-box" target="_blank">`
- href の拡張子: [('html', 88), ('（拡張子なし）', 24), ('cgi', 4), ('css', 2), ('pdf', 2)]
- 27／28 を含む href（拡張子を問わず）0 本:
- ページの実物を置いた → `ISJ-2-page.html`（金庫）
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
