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
| 阪急電鉄 | `text/html` | 54,897 | https://www.hankyu.co.jp/delay/index.html?link=hamburger |
| 阪神電気鉄道 | `text/html` | 71,936 | https://www.hanshin.co.jp/system/delay/ |
| 京阪電気鉄道 | `text/html` | 67,010 | https://www.keihan.co.jp/traffic/delay/ |
| 近畿日本鉄道 | `text/html` | 47,109 | https://www.kintetsu.co.jp/gyoumu/delay/ |
| 南海電気鉄道 | `text/html` | 20,721 | https://www.traffic.nankai.co.jp/delay |
| 大阪メトロ | `text/html` | 59,015 | https://subway.osakametro.co.jp/delay_list.php |
| 山陽電気鉄道 | `text/html` | 54,043 | https://www.sanyo-railway.co.jp/railway/delay/index.html |
| 神戸電鉄 | `text/html` | 125,197 | https://www.shintetsu.co.jp/railway/delay/ |

## 下見（**数えただけ。読み取っていない**）

**何日分残っているか**が、このサイトでいちばん効く数字。
実物を見ないと決められないので、まず形だけ数えた。

| 会社 | 日付の書き方 | 見つけた日付の例 | 表 | 「◯分」 | 文字数 |
|---|---|---|---:|---:|---:|
| JR西日本 | **無い** | — | 0 | 0 | 800 |
| 阪急電鉄 | **無い** | — | 0 | 1 | 40,019 |
| 阪急電鉄 | YYYY年M月D日 126・M月D日 127 | 1月1日 2026年7月16日 2026年7月17日 | 0 | 1 | 49,599 |
| 阪神電気鉄道 | YYYY年M月D日 1・M月D日 47 | 08月11日 08月12日 08月13日 | 4 | 8 | 68,162 |
| 京阪電気鉄道 | YYYY年M月D日 1・M月D日 1 | 2026年9月24日 9月24日 | 4 | 22 | 63,411 |
| 近畿日本鉄道 | YYYY年M月D日 1・M月D日 1 | 2026年9月24日 9月24日 | 14 | 15 | 44,759 |
| 南海電気鉄道 | YYYY年M月D日 1・M月D日 1 | 2026年9月24日 9月24日 | 1 | 4 | 18,392 |
| 大阪メトロ | YYYY年M月D日 2・M月D日 2・YYYY-MM-DD 1 | 09月24日 2026/09/24 2026年09月24日 | 1 | 11 | 53,202 |
| 山陽電気鉄道 | YYYY年M月D日 1・M月D日 1 | 2026年9月24日 9月24日 | 0 | 5 | 48,675 |
| 神戸電鉄 | M月D日 7・YYYY-MM-DD 5 | 2025-11-30 2026-09-21 2026-09-23 | 1 | 20 | 121,109 |

**この日付が遅延の日付とは限らない。** ページの更新日かもしれない。
**人が実物を1回見るまで、決めない。**

日付が「無い」のは、**中身が JavaScript で入る**か、
**別のページに飛ばしている**可能性がある（中身が小さい社に多い）。

## 次に見ること

`inbox/chien/*.bin` を**人が1つ開く。**
**何日分残っているか**、形式（HTMLの表／PDF／画像／JSON）、
**遅れた分数の書き方**を実物で見てから、読み取りを書く。
