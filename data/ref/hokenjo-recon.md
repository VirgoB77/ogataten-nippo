# 保健所の営業許可を探した記録

**このファイルは `hokenjo_recon.py` が書く。** 手で直さない。

ここは**探しただけ**で、まだ1件も読み取っていない。
**URL は作文していない。** 既に収集先に在る兵庫県のオープンデータ目録を、
キーワードで引いて、向こうが書いたリンクを拾った。

**なぜ急ぐか**：兵庫県は**毎月20日頃に上書き**（ファイル名固定）。
いま始めないと、過去は取り返せない。

| | 語の数 |
|---|---:|
| **当たった** | 0 |
| 0本だった | 0 |
| 相手が「だめ」と答えた | 0 |
| **こちらが出られなかった** | 0 |
| 引いた語 | 3 |

## 西宮市について（2026-09-21・**まだ開いていない**）

**確認済み2施設がどちらも西宮市なので、ここは後で要る。**

玄関（`/opendata/`）を開いたら、**拾えたのは利用規約のPDF 1本だけ**だった。
検索で出た形は次のとおり（**検索エンジンの結果。こちらは開いていない**）——

    ResultList.php          詳細検索（一覧）
    ResultDetail.php?id=N   データ詳細（1件ごと）
    results.php             検索結果

**どの id が食品営業許可施設かは分かっていない。**
検索結果では**更新日が 2026-05-15** と出たが、**こちらは確かめていない。**

**「過去版を見つけられなかった」と「過去版が無い」は別。** いまは前者。

## 人が渡した入口（種）

**目録には無かった。** 2026-09-20 に3語で引いて3語とも0本だったが、
調べ直したら**食品衛生課のページに直に置かれていた**（2026-09-21）。
**「0本」は「無い」ではなく、探し方が当たっていなかった。**

**URLは検索で出たものをこちらが並べた。公的資料で確かめていない。**

**表は入口ごとの「最後の1回」。** この回で見ていない入口も残る。
**「見ていない」と「0本だった」を、記録の上でも分けるため。**

| 入口 | 見た日 | この回 | ファイル | 但し書き | 覚書 |
|---|---|---|---:|---:|---|
| [兵庫県（神戸・姫路・尼崎・明石・西宮を除く）](https://web.pref.hyogo.lg.jp/kf14/shokuhineigyoushisetsu_list.html) | 2026-09-21 | **見た** | 4 | 1 |  |
| [神戸市](https://www.city.kobe.lg.jp/a99427/kenko/health/hygiene/dataset.html) | 2026-09-21 | **見た** | 26 | 2 |  |
| [姫路市](https://city.himeji.gkan.jp/gkan/dataset/shokuhinn) | 2026-09-21 | **見た** | 0 | 0 | robots が分からない：robots.txt が HTTP 403（**確かめられなかった**） |
| [尼崎市](https://www.city.amagasaki.hyogo.jp/op_data/1000922/1001025.html) | 2026-09-21 | **見た** | 2 | 0 |  |
| [明石市](https://www.city.akashi.lg.jp/soumu/j_kanri_ka/opendata/hokensyo.html) | 2026-09-21 | **見た** | 35 | 1 |  |
| [西宮市](https://opendata.nishi.or.jp/opendata/ResultList.php) | 2026-09-21 | **見た** | 0 | 0 | ファイルへのリンクが0本。**無いとは限らない** |

### 兵庫県（神戸・姫路・尼崎・明石・西宮を除く）

- [許可営業施設（エクセル：4,403KB）（別ウィンドウで開きます）](https://web.pref.hyogo.lg.jp/kf14/documents/000028_food_business_lisence_all.xlsx)
- [許可営業施設（PDF：6,365KB）（別ウィンドウで開きます）](https://web.pref.hyogo.lg.jp/kf14/documents/000028_food_business_lisence_all.pdf)
- [届出営業施設（エクセル：6,831KB）（別ウィンドウで開きます）](https://web.pref.hyogo.lg.jp/kf14/documents/000028_food_business_notification_all.xlsx)
- [届出営業施設（PDF：3,274KB）（別ウィンドウで開きます）](https://web.pref.hyogo.lg.jp/kf14/documents/000028_food_business_notification_all.pdf)

> 食品関係営業施設リストの閲覧 兵庫県下（神戸市・姫路市・尼崎市・明石市・西宮市を除く


**このページの形**（0本だったときに、理由を見るため）

- JS を落とす前 1,458 文字 → 落とした後 **1,458 文字**
- 同じ形のリンク 8 本（形：`/＊/＊`）
- リンクの形の種類 44

- 更新のしかた？：更新は毎月20日頃です

### 神戸市

- [全ての許可施設（2026年3月末現在。同時点で許可満了日を過ぎている施設を除く。）（CSV：3,](https://www.city.kobe.lg.jp/documents/6359/20260407150739.csv)
- [2026年4月新規許可施設（CSV：60KB）](https://www.city.kobe.lg.jp/documents/6359/0804_syokuhin.csv)
- [2026年5月新規許可施設（CSV：86KB）](https://www.city.kobe.lg.jp/documents/6359/r0805shokuhin.csv)
- [2026年6月新規許可施設（CSV：61KB）](https://www.city.kobe.lg.jp/documents/6359/r0806shokuhin.csv)
- [2026年7月新規許可施設（CSV：63KB）](https://www.city.kobe.lg.jp/documents/6359/r0807shokuhin.csv)
- [2026年8月新規許可施設（CSV：73KB）](https://www.city.kobe.lg.jp/documents/6359/r0808shokuhin.csv)
- [全ての許可施設（2021年5月末現在。同時点で許可満了日を過ぎている施設を除く。）（CSV：5,](https://www.city.kobe.lg.jp/documents/6359/r30531_all_.csv)
- [理容所施設一覧（2026年3月末現在)（CSV：135KB）](https://www.city.kobe.lg.jp/documents/6359/r7_riyousho.csv)
- [美容所施設一覧（2026年3月末現在）（CSV：554KB）](https://www.city.kobe.lg.jp/documents/6359/r7_biyousho.csv)
- [クリーニング所施設一覧（2026年3月末現在）（CSV：175KB）](https://www.city.kobe.lg.jp/documents/6359/r7_cleaning.csv)
- [旅館業施設一覧（2026年3月末現在）（CSV：58KB）](https://www.city.kobe.lg.jp/documents/6359/r7_ryokan.csv)
- [理容所（2026年4月新規確認施設）（CSV：1KB）](https://www.city.kobe.lg.jp/documents/6359/r0804_riyousho.csv)
- [美容所（2026年4月新規確認施設）（CSV：2KB）](https://www.city.kobe.lg.jp/documents/6359/r0804_biyousho.csv)
- [旅館業（2026年4月新規許可施設）（CSV：1KB）](https://www.city.kobe.lg.jp/documents/6359/r0804_ryokan.csv)
- [美容所（2026年5月新規確認施設）（CSV：2KB）](https://www.city.kobe.lg.jp/documents/6359/r0805_biyousho.csv)
- [旅館業（2026年5月新規許可施設）（CSV：1KB）](https://www.city.kobe.lg.jp/documents/6359/r0805_ryokan.csv)
- [理容所（2026年6月新規確認施設）（CSV：1KB）](https://www.city.kobe.lg.jp/documents/6359/r0806_riyousho.csv)
- [美容所（2026年6月新規確認施設）（CSV：3KB）](https://www.city.kobe.lg.jp/documents/6359/r0806_biyousho.csv)
- [クリーニング所（2026年6月新規確認施設）（CSV：1KB）](https://www.city.kobe.lg.jp/documents/6359/r0806_cleaning.csv)
- [旅館業（2026年6月新規許可施設）（CSV：1KB）](https://www.city.kobe.lg.jp/documents/6359/r0806_ryokan.csv)
- [理容所（2026年7月新規確認施設）（CSV：1KB）](https://www.city.kobe.lg.jp/documents/6359/r0807_riyousho.csv)
- [美容所（2026年7月新規確認施設）（CSV：3KB）](https://www.city.kobe.lg.jp/documents/6359/r0807_biyousho.csv)
- [クリーニング所（2026年7月新規確認施設）（CSV：1KB）](https://www.city.kobe.lg.jp/documents/6359/r0807_cleaning.csv)
- [美容所（2026年8月新規確認施設）（CSV：2KB）](https://www.city.kobe.lg.jp/documents/6359/r0808_biyousho.csv)
- [旅館業（2026年8月新規許可施設）（CSV：1KB）](https://www.city.kobe.lg.jp/documents/6359/r0808_ryokan.csv)
- [外字コード表（PDF：276KB）](https://www.city.kobe.lg.jp/documents/6359/gaizi.pdf)

> 同時点で許可満了日を過ぎている施設を除く
> 同時点で許可満了日を過ぎている施設を除く


**このページの形**（0本だったときに、理由を見るため）

- JS を落とす前 2,740 文字 → 落とした後 **2,740 文字**
- 同じ形のリンク 23 本（形：`/documents/＊/＊`）
- リンクの形の種類 19

- 更新のしかた？：営業許可制度の再編と営業届出制度の創設について このページでは、飲食店営業をはじめとする許可施設の一覧を掲載いたします
- 更新のしかた？：厚生労働省から「施行日以前に取得した営業許可の期間の終了に伴い、営業者が引き続き従前の営業を継続する場合は、食品衛生法施行令第35条が全面的に改正されていることを踏まえ、営業許可の更新ではなく、新規の許可申請として取り扱うこと
- 更新のしかた？：本市要綱の廃止により、食品製造業等の届出制度が廃止されたことから、施設一覧の掲載を削除しました
- 更新のしかた？：厚生労働省のオープンデータ掲載ページ（外部リンク） 改正前の食品衛生法に基づく許可施設の一覧を掲載します
- 更新のしかた？：）（CSV：5,840KB） 環境衛生関係施設（理容所、美容所、クリーニング所、旅館業） 理容所、美容所、クリーニング所、旅館業の施設一覧を掲載します
- 更新のしかた？：掲載時点で休業を届出済みの施設は含まれません

### 尼崎市

- [食品営業許可施設【令和8年(2026年）8月31日現在】 （CSV 1.7MB）](https://www.city.amagasaki.hyogo.jp/_res/projects/default_project/_page_/001/001/025/kyoka202608.csv)
- [食品営業届出施設【令和8年(2026年）8月31日現在】 （CSV 456.2KB）](https://www.city.amagasaki.hyogo.jp/_res/projects/default_project/_page_/001/001/025/todoke202608.csv)


**このページの形**（0本だったときに、理由を見るため）

- JS を落とす前 3,735 文字 → 落とした後 **2,510 文字**
- 同じ形のリンク 10 本（形：`/op_data/＊/＊`）
- リンクの形の種類 95

- 更新のしかた？：食品関係営業施設 印刷 ページ番号1001025 更新日 2026年9月8日 オープンデータ 食品関係営業施設 この 作品 は クリエイティブ・コモンズ 表示 4.0 国際 ライセンスの下に提供されています

### 明石市

- [新規食品営業許可施設一覧（令和8年7月分）（2026年8月31日）（CSV：8KB）](https://www.city.akashi.lg.jp/documents/30025/282031_food_business_new_20260701_20260731.csv)
- [新規食品営業許可施設一覧（令和8年6月分）（2026年7月31日）（CSV：6KB）](https://www.city.akashi.lg.jp/documents/30025/282031_food_business_new_20260601_20260630.csv)
- [新規食品営業許可施設一覧（令和8年5月分）（2026年6月30日）（CSV：2KB）](https://www.city.akashi.lg.jp/documents/30025/282031_food_business_new_20260501_20260531.csv)
- [新規食品営業許可施設一覧（令和8年4月分）（2026年5月28日）（CSV：5KB）](https://www.city.akashi.lg.jp/documents/30025/282031_food_business_new_20260401_20260430.csv)
- [新規食品営業許可施設一覧（令和8年3月分）（2026年4月28日）（CSV：4KB）](https://www.city.akashi.lg.jp/documents/30025/282031_food_business_new_20260301_20260331.csv)
- [新規食品営業許可施設一覧（令和8年2月分）（2026年3月30日）（CSV：4KB）](https://www.city.akashi.lg.jp/documents/30025/282031_food_business_new_20260201_20260228.csv)
- [新規食品営業許可施設一覧（令和8年1月分）（2026年2月24日）（CSV：4KB）](https://www.city.akashi.lg.jp/documents/30025/282031_food_business_new_20260101_20260131.csv)
- [新規食品営業許可施設一覧（令和7年12月分）（2026年1月27日）（CSV：4KB）](https://www.city.akashi.lg.jp/documents/30025/282031_food_business_new_20251201_20251231.csv)
- [新規食品営業許可施設一覧（令和7年11月分）（2025年12月18日）（CSV：5KB）](https://www.city.akashi.lg.jp/documents/30025/282031_food_business_new_20251101_20251130.csv)
- [新規食品営業許可施設一覧（令和7年10月分）（2025年11月25日）（CSV：3KB）](https://www.city.akashi.lg.jp/documents/30025/282031_food_business_new_20251001_20251031.csv)
- [新規食品営業許可施設一覧（令和7年9月分）（2025年10月29日）（CSV：4KB）](https://www.city.akashi.lg.jp/documents/30025/282031_food_business_new_20250901_20250930.csv)
- [新規食品営業許可施設一覧（令和7年8月分）（2025年9月29日）（CSV：2KB）](https://www.city.akashi.lg.jp/documents/30025/282031_food_business_new_20250801_20250831.csv)
- [新規食品営業許可施設一覧（令和7年7月分）（2025年8月25日）（CSV：6KB）](https://www.city.akashi.lg.jp/documents/30025/282031_food_business_new_20250701_20250731.csv)
- [新規食品営業許可施設一覧（令和7年6月分）（2025年7月22日）（CSV：5KB）](https://www.city.akashi.lg.jp/documents/30025/282031_food_business_new_20250601_20250630.csv)
- [新規食品営業許可施設一覧（令和7年5月分）（2025年6月27日）（CSV：4KB）](https://www.city.akashi.lg.jp/documents/30025/282031_food_business_new_20250501_20250531.csv)
- [新規食品営業許可施設一覧（令和7年4月分）（2025年5月23日）（CSV：4KB）](https://www.city.akashi.lg.jp/documents/30025/282031_food_business_new_20250401_20250430.csv)
- [新規美容所開設施設一覧（令和8年7月分）(2026年8月31日)（CSV：2KB）](https://www.city.akashi.lg.jp/documents/30025/282031_beauty_salon_new_20260701_20260731.csv)
- [新規美容所開設施設一覧（令和8年6月分）(2026年7月31日)（CSV：1KB）](https://www.city.akashi.lg.jp/documents/30025/282031_beauty_salon_new_20260601_20260630.csv)
- [新規美容所開設施設一覧（令和8年4月分）(2026年5月28日)（CSV：2KB）](https://www.city.akashi.lg.jp/documents/30025/282031_beauty_salon_new_20260401_20260430.csv)
- [新規美容所開設施設一覧（令和8年2月分）(2026年3月30日)（CSV：1KB）](https://www.city.akashi.lg.jp/documents/30025/282031_beauty_salon_new_20260201_20260228.csv)
- [新規美容所開設施設一覧（令和8年1月分）(2026年2月24日)（CSV：1KB）](https://www.city.akashi.lg.jp/documents/30025/282031_beauty_salon_new_20260101_20260131.csv)
- [新規美容所開設施設一覧（令和7年12月分）(2026年1月27日)（CSV：1KB）](https://www.city.akashi.lg.jp/documents/30025/282031_beauty_salon_new_20251201_20251231.csv)
- [新規美容所開設施設一覧（令和7年11月分）(2025年12月18日)（CSV：1KB）](https://www.city.akashi.lg.jp/documents/30025/282031_beauty_salon_new_20251101_20251130.csv)
- [新規美容所開設施設一覧（令和7年10月分）(2025年11月25日)（CSV：1KB）](https://www.city.akashi.lg.jp/documents/30025/282031_beauty_salon_new_20251001_20251031.csv)
- [新規美容所開設施設一覧（令和7年9月分）(2025年10月29日)（CSV：2KB）](https://www.city.akashi.lg.jp/documents/30025/282031_beauty_salon_new_20250901_20250930.csv)
- [新規美容所開設施設一覧（令和7年8月分）(2025年9月29日)（CSV：1KB）](https://www.city.akashi.lg.jp/documents/30025/282031_beauty_salon_new_20250801_20250831.csv)
- [新規美容所開設施設一覧（令和7年7月分）(2025年8月25日)（CSV：1KB）](https://www.city.akashi.lg.jp/documents/30025/282031_beauty_salon_new_20250701_20250731.csv)
- [新規美容所開設施設一覧（令和7年6月分）(2025年7月22日)（CSV：2KB）](https://www.city.akashi.lg.jp/documents/30025/282031_beauty_salon_new_20250601_20250630.csv)
- [新規美容所開設施設一覧（令和7年5月分）(2025年6月27日)（CSV：1KB）](https://www.city.akashi.lg.jp/documents/30025/282031_beauty_salon_new_20250501_20250531.csv)
- [新規美容所開設施設一覧（令和7年4月分）(2025年5月23日)（CSV：2KB）](https://www.city.akashi.lg.jp/documents/30025/282031_beauty_salon_new_20250401_20250430.csv)
- [新規理容所開設施設一覧（令和8年6月分）（2026年7月31日）（CSV：1KB）](https://www.city.akashi.lg.jp/documents/30025/282031_barbar_shop_new_20260601_20260630.csv)
- [新規理容所開設施設一覧（令和8年3月分）（2026年4月28日）（CSV：1KB）](https://www.city.akashi.lg.jp/documents/30025/282031_barbar_shop_new_20260301_20260331.csv)
- [新規理容所開設施設一覧（令和8年2月分）（2026年3月30日）（CSV：1KB）](https://www.city.akashi.lg.jp/documents/30025/282031_barbar_shop_new_20260201_20260228.csv)
- [新規理容所開設施設一覧（令和7年6月分）（2025年7月22日）（CSV：1KB）](https://www.city.akashi.lg.jp/documents/30025/282031_barbar_shop_new_20250601_20250630.csv)
- [新規理容所開設施設一覧（令和7年4月分）（2025年5月23日）（CSV：1KB）](https://www.city.akashi.lg.jp/documents/30025/282031_barbar_shop_new_20250401_20250430.csv)

> あかし保健所に関するオープンデータ 食品営業許可施設 自動販売機、自動車営業、露店営業を除く固定店舗のみ 既に廃業している施設が含まれる場合があります


**このページの形**（0本だったときに、理由を見るため）

- JS を落とす前 3,511 文字 → 落とした後 **3,511 文字**
- 同じ形のリンク 3 本（形：`/soumu/j_kanri_ka/opendata/hokensyo.html`）
- リンクの形の種類 61

- 更新のしかた？：令和8年6月分以降の掲載については、デジタル庁が公開を推奨している「自治体標準オープンデータセット」に基づく形式に変更いたします

### 西宮市


**このページの形**（0本だったときに、理由を見るため）

- JS を落とす前 4,262 文字 → 落とした後 **4,236 文字**
- 同じ形のリンク 0 本（形：`—`）
- リンクの形の種類 0

**入口は6つとも見つけた**（県＋5市）。
**ただし「見つけた」は「開いた」ではない。** 開くのはこの段が走ったとき

## ⚠️ 対象区域の但し書きを必ず読む

案出しが2つの題材で同じ形を踏んだ（2026-09-19）。

    兵庫県の保健所の営業許可     **神戸市・姫路市・尼崎市・明石市・西宮市を除く**
    兵庫県の空き家活用支援事業   同じ構造

**政令市・中核市は自分で持っている。**
読まずに「兵庫県全部」と名乗ると、人口の多いところがまるごと抜ける。

## 氏名が入っている

**営業者氏名の欄がある**（案出しの調査）。個人事業主が多いはず。
金庫に入れる分は問題ないが、**公開するときは 3.1 と 5節を通す。**
**法人だと分かったときだけ出す**（向きを逆にしない）。

## 次に見ること

`inbox/hokenjo/*.html` を**人が1つ開く。**
**一覧の形式・更新の頻度・対象区域の但し書き**を実物で見てから、
毎月の取得を書く。
