# haibokusha-auto

`haibokusha.com`（WordPress）への記事自動投稿システム。

## 仕組み

```
posts/*.md を main ブランチに push
   ↓
GitHub Actions 起動
   ↓
WordPress REST API で記事公開
   ↓
posts/published/ に移動 (重複防止)
```

## 必要なシークレット

GitHub リポジトリ Settings → Secrets and variables → Actions に登録：

| 名前 | 内容 |
|------|------|
| `WP_URL` | `https://haibokusha.com` |
| `WP_USERNAME` | `ri.mo.950526@gmail.com` |
| `WP_APP_PASSWORD` | （WP管理画面で生成したアプリケーションパスワード） |

## 記事の書き方

`posts/2026-05-08-sample.md` のようなファイルを作成：

```markdown
---
title: "記事タイトル"
status: publish      # publish / draft / future（予約）
categories: [Money]
tags: [借金返済, 体験談]
excerpt: "記事冒頭の抜粋"
---

## 見出し1

本文ここから書き始め...

## 見出し2

**強調**や*斜体*、リスト等のMarkdown記法対応。
```

push すると自動で WordPress に投稿され、`posts/published/` に移動されます。

## ローカル動作確認（オプション）

```bash
pip install -r requirements.txt
export WP_URL="https://haibokusha.com"
export WP_USERNAME="your_username"
export WP_APP_PASSWORD="xxxx XXXX yyyy 1234 ZZZZ abcd"
python post.py
```

## トラブルシュート

- **401 Unauthorized**: ユーザー名 or パスワード間違い
- **403 Forbidden**: 該当ユーザーに投稿権限なし（管理者 or 編集者である必要）
- **404 Not Found**: REST API が無効化されている。`https://haibokusha.com/wp-json/` にアクセスして JSON が返るか確認
