"""アフィリエイト URL 一括反映スクリプト。

提携承認後、CTA テンプレ内の `#REPLACE_*_URL` placeholder を実際の A8/もしも アフィ URL に
置換する。対象は：

  1. `_work/haibokusha-design/posts/*.md`（ローカル原稿）
  2. `_work/haibokusha-auto-template/wp-pages/*.md`（固定ページ）
  3. WordPress の既存公開記事（REST API 経由、type=post + page）
  4. Cloudflare Pages 上の compass blog HTML（直接 placeholder を含むものがあれば）

URL マッピングは `_docs/affiliate-links-master.md` の表から読まず、本ファイル冒頭の
`AFFILIATE_LINKS` dict を編集する形（mdは可読ドキュメント、py は実行設定）。
変更時は両方更新するルール。

使用：
  # ドライラン（差分プレビュー）
  python inject_affiliate_links.py

  # ローカル md / wp-pages md のみ書き換え
  python inject_affiliate_links.py --apply --local-only

  # WP REST API 経由で公開済み投稿も更新
  WP_URL=https://haibokusha.com WP_USERNAME=xxx WP_APP_PASSWORD=xxx \\
    python inject_affiliate_links.py --apply --wp

  # 特定 placeholder のみ
  python inject_affiliate_links.py --apply --only DMM_KABU
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ───────────────────────────────────────────────────────────
# AFFILIATE LINK マスタ（このファイルが Source of Truth）
# `#REPLACE_<KEY>_URL` placeholder → 実 URL の対応
# 未承認のキーは値を空文字 or "" のまま残しておく（置換時にスキップされる）
# ───────────────────────────────────────────────────────────

AFFILIATE_LINKS: Dict[str, str] = {
    # ── 確定済（A8 提携承認後） ──
    # 投資・FX・暗号通貨
    "DMM_KABU":       "https://px.a8.net/svt/ejp?a8mat=4B3LMU+759KY+1WP2+15QHIA",
    "LIGHT_FX":       "https://px.a8.net/svt/ejp?a8mat=3BDWT8+FDP656+46VO+5YJRM",
    "GMO_COIN":       "https://px.a8.net/svt/ejp?a8mat=2Z8PJU+AY50SI+3VI8+5YRHE",
    "FUJITOMI_SYSTRE": "https://px.a8.net/svt/ejp?a8mat=2Z8PJU+BLCXDU+34QW+BX3J6",

    # 弁護士・司法書士・債務整理
    "BENGOSHI_HIRAYANAGI": "https://px.a8.net/svt/ejp?a8mat=4B3LMT+FPLV0I+4IB2+614CY",  # 平柳司法書士事務所
    "BENGOSHI_ABIES":      "https://px.a8.net/svt/ejp?a8mat=45G91P+893D6Q+5SXY+5YJRM",  # アビエス法律事務所
    "BENGOSHI_SAKURA":     "https://px.a8.net/svt/ejp?a8mat=45G91P+8AA8EA+5T5G+5YJRM",  # さくら中央法律事務所
    "BENGOSHI_KOUKAI":     "https://px.a8.net/svt/ejp?a8mat=45G91P+89OSSI+4FR4+5YRHE",  # 後悔しない任意整理
    "BENGOSHI_LADIES":     "https://px.a8.net/svt/ejp?a8mat=4B3LMT+FNTK76+38S6+61C2Q",  # レディースフタバ

    # キャッシング・自社ローン（"最後の手段" 注釈必須・ペルソナと整合させる）
    "KASHIKINE_FUKUHO":    "https://px.a8.net/svt/ejp?a8mat=45G91P+8KELOI+39OE+5YJRM",  # フクホー
    "KASHIKINE_NEXUS":     "https://px.a8.net/svt/ejp?a8mat=45G6PM+9ZLVPE+4T5W+5YJRM",  # Nexus Card
    "KASHIKINE_CENTRAL":   "https://px.a8.net/svt/ejp?a8mat=45G91P+8LLGW2+363I+699KI",  # セントラル
    "KASHIKINE_ARROW":     "https://px.a8.net/svt/ejp?a8mat=45G91P+8JT62Q+2SHI+5YRHE",  # 株式会社アロー
    "KASHIKINE_SOKUJITSU": "https://px.a8.net/svt/ejp?a8mat=45G91P+8BH3LU+2EBI+62U36",  # 即日ご融資サービス
    "KASHIKINE_NICHIDEN":  "https://px.a8.net/svt/ejp?a8mat=45G91P+8C2J7M+2J9A+60H7M",  # クレジットのニチデン
    "KASHIKINE_DAILY":     "https://px.a8.net/svt/ejp?a8mat=45G91P+7N2BSY+4WSG+5YJRM",  # デイリーキャッシング
    "KASHIKINE_GENKI":     "https://px.a8.net/svt/ejp?a8mat=45G91P+6W9TKY+5JBK+5YJRM",  # げんき自動車の自社ローン

    # 保険
    "HOKEN_BANG":          "https://px.a8.net/svt/ejp?a8mat=3B9J6A+FDP656+3RU+C1LKI",  # 保険スクエアbang!

    # 弁護士・司法書士（追加）
    "BENGOSHI_EARTH":      "https://px.a8.net/svt/ejp?a8mat=45G91P+8AVO02+4LX2+5YRHE",  # アース司法書士事務所

    # ウェブサービス
    "COCONALA":            "https://px.a8.net/svt/ejp?a8mat=4B3LMU+18NKOY+2PEO+OECDE",  # ココナラ
    "ONAMAE":              "https://px.a8.net/svt/ejp?a8mat=2ZCO12+6PQ1XE+50+3SZMKY",   # お名前.com プレミアムドメイン
    "RAKUTEN_ICHIBA_A8":   "https://rpx.a8.net/svt/ejp?a8mat=2Z8NZ9+AOM342+2HOM+686ZL", # 楽天市場（A8予備、メインはもしも）
    "A8_SELF":             "https://px.a8.net/svt/ejp?a8mat=2Z8NZ9+AO0NIA+0K+10FXXU",   # A8.net 自身

    # ライフスタイル／ダイエット
    "RIZAP":               "https://px.a8.net/svt/ejp?a8mat=2Z8PJT+E6TZCY+3D3Q+62ENM",  # ライザップ

    # 書籍・コンテンツ
    "AUDIBLE":             "https://px.a8.net/svt/ejp?a8mat=45G6PM+8D9EF6+5TB0+5YRHE",  # Audible
    "DMM_BOOKS":           "https://px.a8.net/svt/ejp?a8mat=3BBR56+71MP96+6HW+3SY4KI",  # DMMブックス
    "AUDIOBOOK_JP":        "https://px.a8.net/svt/ejp?a8mat=3BBLME+57JL3U+3CJQ+64C3M",  # audiobook.jp

    # 学習・資格（13件、すべて A8）
    "GAKUSHU_SQUARE":      "https://px.a8.net/svt/ejp?a8mat=4B3LMU+1KK8SI+373C+79HKY",  # 資格スクエア（弁理士試験）
    "GAKUSHU_UKEHODAI":    "https://px.a8.net/svt/ejp?a8mat=4B3LMU+1I6IDE+408S+60WN6",  # ウケホーダイ
    "GAKUSHU_GENBA":       "https://px.a8.net/svt/ejp?a8mat=4B3LMU+1JDDKY+5TRO+5YJRM",  # eラーニング現場系・国家資格
    "GAKUSHU_SARA":        "https://px.a8.net/svt/ejp?a8mat=4B3LMU+1CTLXE+4N6C+7C9W2",  # SARAスクール
    "GAKUSHU_RYOSEKKEI":   "https://px.a8.net/svt/ejp?a8mat=4B3LMU+1DF1J6+4N6C+BWVTE",  # 諒設計アーキテクトラーニング
    "GAKUSHU_NOSEN":       "https://px.a8.net/svt/ejp?a8mat=4B3LMU+1BMQPU+5TS8+5YJRM",  # 能セン
    "GAKUSHU_BIYO":        "https://px.a8.net/svt/ejp?a8mat=4B3LMU+13W3UQ+22BU+614CY",  # 美容・ビューティ業界専門学校
    "GAKUSHU_ONLINE_TEST": "https://px.a8.net/svt/ejp?a8mat=4B3LMU+12P8N6+4LOQ+5YJRM",  # オンライン試験対策講座
    "GAKUSHU_KENKO":       "https://px.a8.net/svt/ejp?a8mat=4B3LMU+16V9VM+4N8K+1ZG8B6",  # 健康長寿栄養学
    "GAKUSHU_SKINCARE_S":  "https://px.a8.net/svt/ejp?a8mat=4B3LMU+Z4N0I+321O+64Z8Y",   # スキンケアスペシャリスト
    "GAKUSHU_FREE":        "https://px.a8.net/svt/ejp?a8mat=4B3LMU+11IDFM+4K7E+C4LLE",  # 自由テキスト（案件名不明）
    "GAKUSHU_SKINCARE_A":  "https://px.a8.net/svt/ejp?a8mat=4B3LMU+T6AYQ+2P6M+61C2Q",   # スキンケアアドバイザー
    "GAKUSHU_TENNENSEKI":  "https://px.a8.net/svt/ejp?a8mat=4B3LMU+RE05E+3OVW+6P4K2",   # 天然石アクセサリー認定講師

    # 食品・グルメ（11件）
    "FOOD_MUEN":           "https://px.a8.net/svt/ejp?a8mat=4B3LMU+6QBHJ6+46NM+NVWSI",  # 無塩ドットコム
    "FOOD_KINENBI":        "https://px.a8.net/svt/ejp?a8mat=4B3LMU+6RICQQ+1OK+NX736",   # 記念日レストラン予約
    "FOOD_SHIRODASHI":     "https://px.a8.net/svt/ejp?a8mat=4B3LMU+6TW35U+253U+5YJRM",  # 四季の彩（白だし）
    "FOOD_YOSHIKEI":       "https://px.a8.net/svt/ejp?a8mat=4B3LMU+6VODZ6+1QM6+5YRHE",  # ヨシケイ
    "FOOD_RETTY":          "https://px.a8.net/svt/ejp?a8mat=4B3LMU+6W9TKY+4EI4+BWVTE",  # Retty
    "FOOD_YUWAERU":        "https://px.a8.net/svt/ejp?a8mat=4B3LMU+6WV96Q+4VW8+5YJRM",  # 結わえる（寝かせ玄米）
    "FOOD_AMAMI_NIGARI":   "https://px.a8.net/svt/ejp?a8mat=4B3LMU+6XGOSI+300M+BWVTE",  # 天海のにがり
    "FOOD_YUKIMURA_SOBA":  "https://px.a8.net/svt/ejp?a8mat=4B3LMU+6ZUF7M+25GM+61Z82",  # 雪村そば
    "FOOD_NISHIDA_TSUKE":  "https://px.a8.net/svt/ejp?a8mat=4B3LMU+70FUTE+4O0M+5YJRM",  # 京つけものニシダや
    "FOOD_EIYOSHI":        "https://px.a8.net/svt/ejp?a8mat=4B3LMU+71MQ0Y+1QM6+HZAGY",  # 栄養士献立（働くママ向け）
    "FOOD_FREE":           "https://px.a8.net/svt/ejp?a8mat=4B3LMU+6QWX4Y+4KUG+64Z8Y",  # 自由テキスト（食品系・案件名不明）

    # ウォーターサーバー＆水（13件）
    "WATER_LOCCA":         "https://px.a8.net/svt/ejp?a8mat=4B3LMU+7LVGLE+4M36+5YRHE",  # Locca
    "WATER_STILIS":        "https://px.a8.net/svt/ejp?a8mat=4B3LMU+7N2BSY+5SIY+5YJRM",  # STILIS
    "WATER_AQUASELECT":    "https://px.a8.net/svt/ejp?a8mat=4B3LMU+7O970I+1A4U+5ZU2A",  # アクアセレクト天然水
    "WATER_DOKOYORI":      "https://px.a8.net/svt/ejp?a8mat=4B3LMU+7OUMMA+3SPO+3SXWUQ", # どこよりもウォーター
    "WATER_AQUABANK_H":    "https://px.a8.net/svt/ejp?a8mat=4B3LMU+7Q1HTU+4NAI+60H7M",  # 水素水アクアバンク
    "WATER_AQUABANK":      "https://px.a8.net/svt/ejp?a8mat=4B3LMU+7RTSN6+4K9C+TS3OI",  # アクアバンク（定額）
    "TOKKEN":              "https://px.a8.net/svt/ejp?a8mat=4B3LMU+7TM3GI+5U6O+5YJRM",  # TOKKEN（地域体験）
    "WATER_ONE":           "https://px.a8.net/svt/ejp?a8mat=4B3LMU+7USYO2+4K9C+5YJRM",  # ウォーターワン
    "WATER_PREMIUM":       "https://px.a8.net/svt/ejp?a8mat=4B3LMU+7VEE9U+2NB4+5ZEMQ",  # プレミアムウォーター
    "WATER_NEYFEEL":       "https://px.a8.net/svt/ejp?a8mat=4B3LMU+7WL9HE+2O5E+5YJRM",  # ネイフィールウォーター
    "WATER_OKEN":          "https://px.a8.net/svt/ejp?a8mat=4B3LMU+7X6P36+1LOO+5YRHE",  # オーケンウォーター
    "WATER_RAKUSUI":       "https://px.a8.net/svt/ejp?a8mat=4B3LMU+7XS4OY+4IHG+61RIA",  # 楽水（浄水型）
    "WATER_FREE":          "https://px.a8.net/svt/ejp?a8mat=4B3LMU+7MGW76+51J0+67JUA",  # 自由テキスト2

    # 通信・モバイル・WiFi（5件）
    "TSUSHIN_MONSTER":     "https://px.a8.net/svt/ejp?a8mat=4B3LMU+8QCXQA+348K+3YW8WI",  # モンスターモバイル
    "TSUSHIN_DAREDEMO":    "https://px.a8.net/svt/ejp?a8mat=4B3LMU+8TC3R6+4G6O+1ZG8B6",  # 誰でもWi-Fi
    "TSUSHIN_JVC":         "https://px.a8.net/svt/ejp?a8mat=4B3LMU+8TXJCY+5V4K+5YJRM",   # JVC Powered by Litheli
    "TSUSHIN_BBEXCITE":    "https://px.a8.net/svt/ejp?a8mat=4B3LMU+8V4EKI+7JY+2BCWEQ",   # BB.exciteモバイル
    "TSUSHIN_PREMIUM_WIFI": "https://px.a8.net/svt/ejp?a8mat=4B3LMU+8VPU6A+4SIK+HVFKY",  # プレミアムチャージWiFi

    # 光回線・固定インターネット（8件）
    "HIKARI_BIGLOBE":      "https://px.a8.net/svt/ejp?a8mat=4B3LMU+98TDHE+3SPO+7LVLZM",  # BIGLOBE光
    "HIKARI_COMMUFA":      "https://px.a8.net/svt/ejp?a8mat=4B3LMU+99ET36+3SPO+BQPZ82",  # コミュファ光
    "HIKARI_SOFTBANK_AIR": "https://px.a8.net/svt/ejp?a8mat=4B3LMU+9A08OY+3SPO+3MZKSY",  # SoftbankAir
    "HIKARI_AU":           "https://px.a8.net/svt/ejp?a8mat=4B3LMU+9ALOAQ+348K+3H18R6",  # auひかり
    "HIKARI_FAMILY_GIGA":  "https://px.a8.net/svt/ejp?a8mat=4B3LMU+9B73WI+53SE+5YRHE",   # ファミリーギガ
    "HIKARI_COMMUFA_ALT":  "https://px.a8.net/svt/ejp?a8mat=4B3LMU+9CDZ42+42Y0+BX3J6",   # コミュファ光（別案件）
    "HIKARI_AU_ALT":       "https://px.a8.net/svt/ejp?a8mat=4B3LMU+9CZEPU+42Y0+5YJRM",   # auひかり（別案件）
    "HIKARI_FREE":         "https://px.a8.net/svt/ejp?a8mat=4B3LMU+987XVM+4JGG+BWVTE",   # 自由テキスト（光系・案件名不明）

    # 光回線（追加3件）
    "HIKARI_TCOM":         "https://px.a8.net/svt/ejp?a8mat=4B3LMU+A5K7R6+348K+3SXWUQ",  # @T COMヒカリ
    "HIKARI_ITSUKI":       "https://px.a8.net/svt/ejp?a8mat=4B3LMU+A94TDU+4VXM+60OXE",   # イツキ光（v6プラス対応）
    "HIKARI_DTI":          "https://px.a8.net/svt/ejp?a8mat=4B3LMU+A9Q8ZM+1QFI+354KNM",  # DTI光

    # ポケットWiFi／クラウドWiFi（4件）
    "WIFI_BIGLOBE_WIMAX":  "https://px.a8.net/svt/ejp?a8mat=4B3LMU+9T241U+B4+2BKM6Q",   # BIGLOBE WiMAX +5G
    "WIFI_RECHARGE":       "https://px.a8.net/svt/ejp?a8mat=4B3LMU+A65NCY+57FS+5YJRM",   # リチャージWiFi
    "WIFI_100GB_CLOUD":    "https://px.a8.net/svt/ejp?a8mat=4B3LMU+A7CIKI+3MKA+HV7V6",   # 100GBクラウドWi-Fi
    "WIFI_NEOCHARGE":      "https://px.a8.net/svt/ejp?a8mat=4B3LMU+A7XY6A+57X0+5YRHE",   # ネオチャージWiFi

    # SIM／レンタル系（3件・敗北者ペルソナ直撃）
    "SIM_SUNCISCON":       "https://px.a8.net/svt/ejp?a8mat=4B3LMU+9RV8UA+5B5E+5YRHE",   # サンシスコン
    "SIM_REN":             "https://px.a8.net/svt/ejp?a8mat=4B3LMU+A8JDS2+57X0+HV7V6",   # REN SIM
    "SIM_LYPRIMO":         "https://px.a8.net/svt/ejp?a8mat=4B3LMU+AAX476+529Y+60H7M",   # Lyprimo（審査なし）

    # その他
    "POINT_20K_FREE":      "https://px.a8.net/svt/ejp?a8mat=4B3LMU+9R9T8I+4TIO+626XU",   # 20,000ポイント自由案件

    # 通信・SIM 追加（5件、特に DAREDEMO_MOBILE は敗北者ペルソナど真ん中）
    "TSUSHIN_FAST_SIM_WIFI": "https://px.a8.net/svt/ejp?a8mat=4B3LMU+AHGVUQ+4ATM+BWVTE", # ファストSIM-WiFi
    "TSUSHIN_KAIGAI_WIFI":   "https://px.a8.net/svt/ejp?a8mat=4B3LMU+AJUM9U+2W74+5ZMCI", # 200カ国対応海外WiFi
    "TSUSHIN_GIGASET":       "https://px.a8.net/svt/ejp?a8mat=4B3LMU+AKG1VM+4SIK+BX3J6", # ギガセットWiFi
    "SIM_DAREDEMO_MOBILE":   "https://px.a8.net/svt/ejp?a8mat=4B3LMU+AM8COY+4G6O+1THW9E", # だれでもモバイル
    "SIM_LIBMO":             "https://px.a8.net/svt/ejp?a8mat=4B3LMU+AMTSAQ+3UM0+5YRHE", # LIBMO

    # ふるさと納税（3件、もしも経由のふるさと納税ニッポンとは別）
    "FURUSATO_AUPAY":      "https://px.a8.net/svt/ejp?a8mat=4B3LMU+A4YS5E+54OC+5YRHE",  # au PAY ふるさと納税
    "FURUSATO_WHISKY":     "https://px.a8.net/svt/ejp?a8mat=4B3LMU+AV5URM+5U6O+BX3J6",  # ウイスキーふるさと納税
    "FURUSATO_HONPO":      "https://px.a8.net/svt/ejp?a8mat=4B3LMU+AWCPZ6+5IMU+5YRHE",  # ふるさと本舗

    # サプリメント
    "SUPPLEMENT_MPN":      "https://px.a8.net/svt/ejp?a8mat=4B3LMU+ATDJYA+586Q+5YJRM",  # MPNサプリメント

    # 資金調達・ファクタリング（B2B、3件）
    "B2B_SHIKIN":          "https://px.a8.net/svt/ejp?a8mat=4B3LMU+B9G9AA+4JGG+5YJRM",  # 資金調達（無料見積30分）
    "B2B_NISHINIHON":      "https://px.a8.net/svt/ejp?a8mat=4B3LMU+BB8K3M+3XT0+5YJRM",  # 西日本ファクター
    "B2B_URIKAKE":         "https://px.a8.net/svt/ejp?a8mat=4B3LMU+BCFFB6+4S8A+5YJRM",  # うりかけ堂

    # 投資・FX 追加（3件）
    "INVEST_KABU_INFO":    "https://px.a8.net/svt/ejp?a8mat=4B3LMU+BAN4HU+ONS+TXW0I",   # 株式投資情報源
    "INVEST_FX_SCHOOL":    "https://px.a8.net/svt/ejp?a8mat=4B3LMU+BBTZPE+5J1A+BX3J6",  # 国の免許登録FXスクール
    "INVEST_MENDAN":       "https://px.a8.net/svt/ejp?a8mat=4B3LMU+BG00XU+40OC+BWVTE",  # 投資個人面談

    # フィットネス・ボディメイク・美容（4件）
    # 5/9 ペルソナ判定 v2（Compass を「生活改善ハブ」に拡張、health-beauty カテゴリ新設）：
    # FITNESS_BCONCEPT / BIYO_DATSUMO は Compass 専用で再採用
    # FITNESS_HABIT は高級・東京限定でROI不確定 → 保留（コメントアウト維持）
    # "FITNESS_HABIT":     "...",  # 保留：高級・東京限定。後続案件次第で再評価
    "FITNESS_BCONCEPT":    "https://px.a8.net/svt/ejp?a8mat=4B3LMU+BUAFGI+3UK2+5YJRM",  # B-CONCEPT 女性向けボディメイク（Compass 女性向け記事限定）
    "BIYO_DATSUMO":        "https://px.a8.net/svt/ejp?a8mat=4B3LMU+BVHAO2+1OGO+HV7V6",  # 脱毛体験（Compass 美容記事専用）
    "FITNESS_CLOUD_GYM":   "https://px.a8.net/svt/ejp?a8mat=4B3LMU+BTOZUQ+4RUO+5YJRM",  # CLOUD GYM（Compass 採用）

    # ── 5/9 新規追加：電気・ガス（kounetsuhi 4社） ──
    "DENKI_ARCANA":        "https://px.a8.net/svt/ejp?a8mat=4B3MEQ+1NJETE+5HNU+5YJRM",  # アルカナでんき
    "DENKI_ELPIO":         "https://px.a8.net/svt/ejp?a8mat=4B3MEQ+1OQA0Y+4AXS+5YJRM",  # エルピオでんき
    "DENKI_SUSTAIN":       "https://px.a8.net/svt/ejp?a8mat=4B3MEQ+1VVHAA+4RKE+5YJRM",  # サステナブルでんき
    "DENKI_CHOICE":        "https://px.a8.net/svt/ejp?a8mat=4B3MEQ+1WGWW2+3SPO+TRVYQ",  # 電気チョイス（比較サイト）

    # ── 5/9 新規追加：転職・フリーランス（tenshoku/fukugyo 1社） ──
    "IT_KYUJIN_FREELANCE": "https://px.a8.net/svt/ejp?a8mat=4B3MEQ+1SD4Y+4LXM+5YJRM",  # IT求人ナビ フリーランス

    # ── 5/9 新規追加：もしも EC・汎用（3社、両サイト共通利用） ──
    "MOSHIMO_RAKUTEN_ICHIBA":  "https://af.moshimo.com/af/c/click?a_id=5542698&p_id=54&pc_id=54&pl_id=621",       # 楽天市場（マルチカテゴリ汎用）
    "MOSHIMO_YAHOO_SHOPPING":  "https://af.moshimo.com/af/c/click?a_id=5542704&p_id=1225&pc_id=1925&pl_id=18502",  # Yahoo!ショッピング
    "MOSHIMO_FURUSATO_NIPPON": "https://af.moshimo.com/af/c/click?a_id=5542709&p_id=3172&pc_id=7409&pl_id=41472",  # ふるさと納税ニッポン

    # ── 提携承認待ち（URL 来るまで空のまま、placeholder 残留） ──
    "BENGOSHI_ADIRE": "",   # アディーレ（A8 該当案件なし、他の弁護士で代替）
    "RAKUTEN_SHOKEN": "",
    "SBI_SHOKEN": "",
    "RAKUTEN_DEBIT": "",
    "MFW": "",            # マネーフォワード ME
    "STUDYING": "",       # スタディング
    "AMAZON_BOOK": "",    # Amazonアソシエイト（審査中：5/12〜）
}

# ───────────────────────────────────────────────────────────
# サイト振り分け（usable_sites）
# どのアフィキーがどのサイトで使えるかを宣言する。
# 未指定キーは _DEFAULT_USABLE_SITES が適用される＝両サイト OK の広めデフォルト。
# 採点しながら絞り込んでいく運用：誤った組み合わせが見えたら override に追記。
# ───────────────────────────────────────────────────────────

_DEFAULT_USABLE_SITES: List[str] = ["haibokusha", "compass"]

USABLE_SITES_OVERRIDE: Dict[str, List[str]] = {
    # ── haibokusha 専用（敗北者・債務整理ペルソナ向け、compass FIRE層には合わない）
    "BENGOSHI_HIRAYANAGI": ["haibokusha"],
    "BENGOSHI_ABIES":      ["haibokusha"],
    "BENGOSHI_SAKURA":     ["haibokusha"],
    "BENGOSHI_KOUKAI":     ["haibokusha"],
    "BENGOSHI_LADIES":     ["haibokusha"],
    "BENGOSHI_EARTH":      ["haibokusha"],
    "BENGOSHI_ADIRE":      ["haibokusha"],
    # キャッシング・自社ローン（"最後の手段"枠、compass の人生改善文脈には不適）
    "KASHIKINE_FUKUHO":    ["haibokusha"],
    "KASHIKINE_NEXUS":     ["haibokusha"],
    "KASHIKINE_CENTRAL":   ["haibokusha"],
    "KASHIKINE_ARROW":     ["haibokusha"],
    "KASHIKINE_SOKUJITSU": ["haibokusha"],
    "KASHIKINE_NICHIDEN":  ["haibokusha"],
    "KASHIKINE_DAILY":     ["haibokusha"],
    "KASHIKINE_GENKI":     ["haibokusha"],
    "RAKUTEN_DEBIT":       ["haibokusha"],
    "SIM_DAREDEMO_MOBILE": ["haibokusha"],  # 審査なしSIMは敗北者ペルソナ直撃、FIRE層には不要
    "SIM_LYPRIMO":         ["haibokusha"],

    # ── compass 専用（生活改善ハブ向け、haibokusha 敗北者ペルソナとは温度差）
    "RIZAP":                ["compass"],
    "FITNESS_BCONCEPT":     ["compass"],
    "FITNESS_CLOUD_GYM":    ["compass"],
    "BIYO_DATSUMO":         ["compass"],
    "GAKUSHU_KENKO":        ["compass"],
    "GAKUSHU_BIYO":         ["compass"],
    "GAKUSHU_SKINCARE_S":   ["compass"],
    "GAKUSHU_SKINCARE_A":   ["compass"],
    "GAKUSHU_TENNENSEKI":   ["compass"],

    # ── B2B（事業者向け、両サイトのペルソナいずれにも近くないが文脈次第で使える）
    # ここでは "両OK" デフォルトのまま放置。記事側で文脈合えば使う／なければ使わない。
}


def usable_sites_of(key: str) -> List[str]:
    """指定キーが使えるサイト名リストを返す。未指定キーはデフォルト適用。"""
    return USABLE_SITES_OVERRIDE.get(key, _DEFAULT_USABLE_SITES)


def links_for_site(site: str) -> Dict[str, str]:
    """指定サイト向けに有効な KEY→URL の単純 dict を返す（apply_replacements 互換）。

    - URL が空のキー（提携承認待ち）は除外
    - usable_sites に site を含まないキーは除外
    """
    out = {}
    for key, url in AFFILIATE_LINKS.items():
        if not url:
            continue
        if site in usable_sites_of(key):
            out[key] = url
    return out


# 対象ディレクトリ
REPO_ROOT = Path(__file__).resolve().parents[2]    # 企業案/
WORK_DIR = Path(__file__).resolve().parents[1]      # _work/

LOCAL_DIRS_TO_PROCESS = [
    WORK_DIR / "haibokusha-design" / "posts",
    WORK_DIR / "haibokusha-design" / "posts-monetization",
    WORK_DIR / "haibokusha-design" / "wp-pages",
    WORK_DIR / "haibokusha-auto-template" / "wp-pages",
]

# Cloudflare Pages 配下の compass HTML（placeholder が含まれる場合のみ）
COMPASS_HTML_DIRS = [REPO_ROOT, REPO_ROOT / "_deploy"]


PLACEHOLDER_RE = re.compile(r"#REPLACE_([A-Z_]+)_URL")


# ───────────────────────────────────────────────────────────
# WP REST API
# ───────────────────────────────────────────────────────────

WP_URL = os.environ.get("WP_URL", "").rstrip("/")
WP_USERNAME = os.environ.get("WP_USERNAME", "")
WP_APP_PASSWORD = os.environ.get("WP_APP_PASSWORD", "")


def wp_auth_header() -> Dict[str, str]:
    cred = f"{WP_USERNAME}:{WP_APP_PASSWORD}"
    return {"Authorization": "Basic " + base64.b64encode(cred.encode()).decode("ascii")}


def wp_get(path: str) -> dict:
    url = f"{WP_URL}{path}"
    req = urllib.request.Request(url, headers=wp_auth_header())
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def wp_update(post_id: int, payload: dict, post_type: str = "posts") -> dict:
    url = f"{WP_URL}/wp-json/wp/v2/{post_type}/{post_id}"
    headers = {**wp_auth_header(), "Content-Type": "application/json; charset=utf-8"}
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def wp_list(post_type: str = "posts", per_page: int = 100) -> List[dict]:
    """全記事を取得（簡易ページング）"""
    out = []
    page = 1
    while True:
        try:
            results = wp_get(f"/wp-json/wp/v2/{post_type}?per_page={per_page}&page={page}&_fields=id,slug,title,content,status")
        except Exception as e:
            print(f"  ! wp_list page={page} error: {e}", file=sys.stderr)
            break
        if not results:
            break
        out.extend(results)
        if len(results) < per_page:
            break
        page += 1
    return out


# ───────────────────────────────────────────────────────────
# 置換ロジック
# ───────────────────────────────────────────────────────────

def apply_replacements(text: str, links: Dict[str, str], only: Optional[str] = None) -> Tuple[str, int]:
    """テキスト中の #REPLACE_KEY_URL を links[KEY] で置換。

    - 値が空文字のキーはスキップ（placeholder のまま残す）
    - only 指定があればそのキーのみ処理
    戻り値: (新テキスト, 置換回数)
    """
    count = 0
    new_text = text
    for key, url in links.items():
        if not url:
            continue
        if only and key != only:
            continue
        placeholder = f"#REPLACE_{key}_URL"
        before = new_text.count(placeholder)
        if before > 0:
            new_text = new_text.replace(placeholder, url)
            count += before
    return new_text, count


# ───────────────────────────────────────────────────────────
# ローカルファイル処理
# ───────────────────────────────────────────────────────────

def process_local_files(only: Optional[str], dry_run: bool) -> List[dict]:
    results = []
    targets: List[Path] = []
    for d in LOCAL_DIRS_TO_PROCESS:
        if d.exists():
            targets.extend(d.glob("*.md"))
    # compass の HTML
    for d in COMPASS_HTML_DIRS:
        if d.exists():
            targets.extend(d.glob("*.html"))
            targets.extend(d.glob("blog-*.html"))

    seen = set()
    for path in targets:
        if path in seen:
            continue
        seen.add(path)
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        new_text, count = apply_replacements(text, AFFILIATE_LINKS, only=only)
        if count > 0:
            results.append({"path": str(path.relative_to(REPO_ROOT)), "replacements": count, "applied": False})
            if not dry_run:
                path.write_text(new_text, encoding="utf-8")
                results[-1]["applied"] = True
    return results


# ───────────────────────────────────────────────────────────
# WP 反映
# ───────────────────────────────────────────────────────────

def process_wp(only: Optional[str], dry_run: bool) -> List[dict]:
    results = []
    if not (WP_URL and WP_USERNAME and WP_APP_PASSWORD):
        print("  ! WP_URL/WP_USERNAME/WP_APP_PASSWORD 未設定。WP更新をスキップ", file=sys.stderr)
        return results

    for ptype in ("posts", "pages"):
        items = wp_list(ptype, per_page=100)
        for it in items:
            content = (it.get("content") or {}).get("rendered") or ""
            new_content, count = apply_replacements(content, AFFILIATE_LINKS, only=only)
            if count > 0:
                row = {
                    "wp_type": ptype,
                    "id": it["id"],
                    "slug": it.get("slug"),
                    "title": (it.get("title") or {}).get("rendered", ""),
                    "replacements": count,
                    "applied": False,
                }
                results.append(row)
                if not dry_run:
                    try:
                        wp_update(it["id"], {"content": new_content}, post_type=ptype)
                        row["applied"] = True
                        time.sleep(0.5)  # rate limit avoidance
                    except Exception as e:
                        row["error"] = str(e)
    return results


# ───────────────────────────────────────────────────────────
# CLI
# ───────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true", help="実際に書き換え／POST を行う")
    p.add_argument("--local-only", action="store_true", help="ローカルファイルのみ処理（WPスキップ）")
    p.add_argument("--wp", action="store_true", help="WP REST API 経由でも更新する")
    p.add_argument("--only", help="特定の placeholder キー（例: DMM_KABU）のみ処理")
    args = p.parse_args()

    print("─" * 80)
    print("Affiliate Link Injection")
    print(f"  Mode: {'APPLY' if args.apply else 'DRY-RUN'}")
    print(f"  Targets: local{' + WP' if args.wp else ''}{' (only=' + args.only + ')' if args.only else ''}")
    print(f"  Defined links: {sum(1 for v in AFFILIATE_LINKS.values() if v)}/{len(AFFILIATE_LINKS)}")
    print("─" * 80)

    print("\n[1/2] Local files:")
    local = process_local_files(args.only, dry_run=not args.apply)
    if not local:
        print("  no replacements needed")
    for r in local:
        mark = "✓" if r["applied"] else "·"
        print(f"  {mark} {r['path']}  (×{r['replacements']})")

    print("\n[2/2] WordPress:")
    if args.wp and not args.local_only:
        wp = process_wp(args.only, dry_run=not args.apply)
        if not wp:
            print("  no WP replacements needed (or unauthorized)")
        for r in wp:
            mark = "✓" if r.get("applied") else ("ERR" if r.get("error") else "·")
            print(f"  {mark} [{r['wp_type']}] id={r['id']:4d} slug={r['slug']:30s} ×{r['replacements']}{(' err='+r['error']) if r.get('error') else ''}")
    else:
        print("  --wp 未指定のためスキップ")

    print()
    if not args.apply:
        print("--apply を付けて再実行すると確定します。")


if __name__ == "__main__":
    main()
