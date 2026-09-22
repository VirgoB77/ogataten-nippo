# 遅延証明書のページを取ってきた記録

**このファイルは `chien_get.py` が書く。** 手で直さない。

**行き先は1段目の記録（`chien-recon.md`）から読んだ。**
統括の記憶からは読んでいない。記録に無いものは取りに行かない。

**まだ1件も読み取っていない。** 中身は成果物（artifact）にある。

| | 会社数 |
|---|---:|
| **取れた** | 10 |
| robots が拒否 | 0 |
| 相手が「だめ」と答えた | 0 |
| **こちらが出られなかった** | 0 |
| 混んでいたので飛ばした | 0 |
| 記録にあった行き先 | 10 |

## 取れたもの

| 会社 | 形式 | 大きさ | 行き先 |
|---|---|---:|---|
| JR西日本 | `text/html` | 910 | http://delay.trafficinfo.westjr.co.jp/<br>↳ https://delay.trafficinfo.westjr.co.jp/ |
| 阪急電鉄 | `text/html` | 44,005 | https://www.hankyu.co.jp/railinfo/index.html |
| 阪急電鉄 | `text/html` | 54,820 | https://www.hankyu.co.jp/delay/index.html?link=hamburger |
| 阪神電気鉄道 | `text/html` | 72,204 | https://www.hanshin.co.jp/system/delay/ |
| 京阪電気鉄道 | `text/html` | 67,145 | https://www.keihan.co.jp/traffic/delay/ |
| 近畿日本鉄道 | `text/html` | 50,197 | https://www.kintetsu.co.jp/gyoumu/delay/ |
| 南海電気鉄道 | `text/html` | 20,885 | https://www.traffic.nankai.co.jp/delay |
| 大阪メトロ | `text/html` | 57,953 | https://subway.osakametro.co.jp/delay_list.php |
| 山陽電気鉄道 | `text/html` | 53,435 | https://www.sanyo-railway.co.jp/railway/delay/index.html |
| 神戸電鉄 | `text/html` | 125,087 | https://www.shintetsu.co.jp/railway/delay/ |

## 下見（**数えただけ。読み取っていない**）

**何日分残っているか**が、このサイトでいちばん効く数字。
実物を見ないと決められないので、まず形だけ数えた。

| 会社 | 日付の書き方 | 見つけた日付の例 | 表 | 「◯分」 | 文字数 |
|---|---|---|---:|---:|---:|
| JR西日本 | **無い** | — | 0 | 0 | 800 |
| 阪急電鉄 | **無い** | — | 0 | 1 | 40,019 |
| 阪急電鉄 | YYYY年M月D日 125・M月D日 126 | 1月1日 2026年7月16日 2026年7月17日 | 0 | 1 | 49,528 |
| 阪神電気鉄道 | YYYY年M月D日 1・M月D日 47 | 08月09日 08月10日 08月11日 | 4 | 8 | 68,430 |
| 京阪電気鉄道 | YYYY年M月D日 1・M月D日 1 | 2026年9月22日 9月22日 | 4 | 23 | 63,544 |
| 近畿日本鉄道 | YYYY年M月D日 1・M月D日 1 | 2026年9月22日 9月22日 | 14 | 31 | 47,815 |
| 南海電気鉄道 | YYYY年M月D日 1・M月D日 1 | 2026年9月22日 9月22日 | 1 | 5 | 18,556 |
| 大阪メトロ | YYYY年M月D日 2・M月D日 2・YYYY-MM-DD 1 | 09月22日 2026/09/22 2026年09月22日 | 1 | 5 | 52,056 |
| 山陽電気鉄道 | YYYY年M月D日 1・M月D日 1 | 2026年9月22日 9月22日 | 0 | 3 | 48,059 |
| 神戸電鉄 | M月D日 7・YYYY-MM-DD 4 | 2025-11-30 2026-09-21 2026-09-22 | 1 | 19 | 121,001 |

**この日付が遅延の日付とは限らない。** ページの更新日かもしれない。
**人が実物を1回見るまで、決めない。**

日付が「無い」のは、**中身が JavaScript で入る**か、
**別のページに飛ばしている**可能性がある（中身が小さい社に多い）。

## 次に見ること

`inbox/chien/*.bin` を**人が1つ開く。**
**何日分残っているか**、形式（HTMLの表／PDF／画像／JSON）、
**遅れた分数の書き方**を実物で見てから、読み取りを書く。
