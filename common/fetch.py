# -*- coding: utf-8 -*-
"""取りに行くときの名乗りと間隔。4つの取得スクリプトが同じ値を使う（共通仕様 3.4）。

書式は仕様どおり：kujiraya archive bot (+<aboutページ>; <連絡フォーム>)
- about ページはサイト公開後なので 200 が返る。公開前なら404になるURLは入れない
- 連絡フォームは Google フォーム。ドメインに依存しないので、サイトを移しても変わらない
- ここ以外に UA の文字列を直書きしない（監査で4ファイルに重複していた）
"""

ABOUT_URL = "https://ogataten-nippo.com/about.html"
CONTACT_FORM_URL = "https://forms.gle/pp93tSJ5p8SAMEMk8"

UA = f"kujiraya archive bot (+{ABOUT_URL}; {CONTACT_FORM_URL})"

# リクエスト間隔（秒）。同時接続は1本。仕様の「5秒以上」
WAIT = 5
