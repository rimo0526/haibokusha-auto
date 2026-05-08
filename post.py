"""
WordPress Auto Post Script (haibokusha.com)

posts/ 配下の未公開 .md ファイルを WordPress REST API で公開し、
posts/published/ に移動する。

機能:
  - フロントマターから title / status / categories / tags / excerpt を読み取り
  - Markdown → HTML 変換
  - H2 セクションごとにインラインSVG挿絵を自動注入（illustrations.py）
  - アイキャッチPNGを自動生成 → /wp/v2/media へアップロード（eyecatch.py）
  - featured_media を投稿に紐付け
  - 投稿成功後、ファイルを posts/published/ に退避

WAF 対策:
  - GET（カテゴリ等の読み取り）は無認証で叩く（ConoHa WAF が認証付きGETを弾くケースに対応）
  - POST/UPLOAD のみ Basic 認証（Application Password）
"""

import base64
import json
import mimetypes
import os
import re
import sys
from pathlib import Path

import frontmatter
import markdown
import requests

from eyecatch import generate_eyecatch_png, category_to_label
from illustrations import inject_illustrations
from inject_ctas import inject_ctas
try:
    from inject_affiliate_links import AFFILIATE_LINKS, apply_replacements
except ImportError:
    AFFILIATE_LINKS = {}
    def apply_replacements(text, links, only=None):
        return text, 0

# ── 環境変数 ────────────────────────────────────
WP_URL = os.environ['WP_URL'].rstrip('/')
WP_USERNAME = os.environ['WP_USERNAME']
WP_APP_PASSWORD = os.environ['WP_APP_PASSWORD']

# ── パス ────────────────────────────────────────
POSTS_DIR = Path('posts')
PUBLISHED_DIR = POSTS_DIR / 'published'
PUBLISHED_DIR.mkdir(parents=True, exist_ok=True)


# ── 共通ヘッダ ──────────────────────────────────
def auth_header(content_type: str = 'application/json') -> dict:
    token = base64.b64encode(f'{WP_USERNAME}:{WP_APP_PASSWORD}'.encode()).decode()
    return {
        'Authorization': f'Basic {token}',
        'Content-Type': content_type,
        'Accept': 'application/json',
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 '
                      'haibokusha-auto/1.0',
    }


def public_header() -> dict:
    return {
        'Accept': 'application/json',
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }


# ── タクソノミー解決（カテゴリ・タグ） ─────────────
def resolve_terms(taxonomy: str, names: list) -> list:
    """名前のリストを ID リストに変換。GET は無認証、POST(新規) は認証付き。"""
    if not names:
        return []

    r = requests.get(f'{WP_URL}/wp-json/wp/v2/{taxonomy}',
                     params={'per_page': 100}, headers=public_header(), timeout=30)
    r.raise_for_status()
    all_terms = r.json()

    ids = []
    for name in names:
        existing = next((t for t in all_terms if t['name'] == name), None)
        if existing:
            ids.append(existing['id'])
        else:
            r = requests.post(f'{WP_URL}/wp-json/wp/v2/{taxonomy}',
                              json={'name': name}, headers=auth_header(), timeout=30)
            r.raise_for_status()
            ids.append(r.json()['id'])
            print(f'  + Created {taxonomy}: {name}')
    return ids


# ── アイキャッチアップロード ───────────────────────
def _slugify(text: str) -> str:
    """ファイル名用の素朴なスラッグ化（英数字・ハイフン以外は -）"""
    s = re.sub(r'[^A-Za-z0-9\-]+', '-', text)
    s = re.sub(r'-+', '-', s).strip('-')
    return s.lower() or 'eyecatch'


def upload_eyecatch(title: str, categories: list, excerpt: str,
                    file_stem: str) -> int | None:
    """アイキャッチPNGを生成 → /wp/v2/media にアップロード → media_id を返す。"""
    try:
        category_label = category_to_label(categories)
        png_bytes = generate_eyecatch_png(
            title=title,
            category_label=category_label,
            subtitle=(excerpt or '')[:40],
        )
    except Exception as e:
        print(f'  ⚠ アイキャッチ生成失敗（投稿は続行）: {e}', file=sys.stderr)
        return None

    # ファイル名は記事スラッグ＋日付
    filename = f'{_slugify(file_stem)}-eyecatch.png'

    headers = auth_header(content_type='image/png')
    headers['Content-Disposition'] = f'attachment; filename="{filename}"'

    try:
        r = requests.post(
            f'{WP_URL}/wp-json/wp/v2/media',
            data=png_bytes,
            headers=headers,
            timeout=120,
        )
        r.raise_for_status()
    except requests.HTTPError as e:
        print(f'  ⚠ アイキャッチアップロード失敗: {e} / body={r.text[:200]}',
              file=sys.stderr)
        return None
    except Exception as e:
        print(f'  ⚠ アイキャッチアップロード例外: {e}', file=sys.stderr)
        return None

    media = r.json()
    media_id = media.get('id')
    media_url = media.get('source_url', '')
    print(f'  📷 アイキャッチ uploaded: id={media_id} url={media_url}')
    return media_id


# ── 投稿本体 ──────────────────────────────────
def post_article(path: Path) -> dict:
    post = frontmatter.load(path)
    title = post.metadata.get('title', path.stem)
    status = post.metadata.get('status', 'publish')
    excerpt = post.metadata.get('excerpt', '')
    cats = post.metadata.get('categories', [])
    tags = post.metadata.get('tags', [])
    # 予約公開対応: フロントマター `date` を ISO8601 文字列として受け取る
    # 例: date: 2026-05-08T07:00:00+09:00
    # status: future かつ未来日時なら、WordPress 側で予約公開される
    scheduled_date = post.metadata.get('date')
    # Python の datetime オブジェクトとして読まれる場合は ISO 文字列に変換
    if scheduled_date is not None and not isinstance(scheduled_date, str):
        try:
            scheduled_date = scheduled_date.isoformat()
        except AttributeError:
            scheduled_date = str(scheduled_date)

    # Markdown → HTML
    html = markdown.markdown(
        post.content,
        extensions=['extra', 'tables', 'fenced_code', 'sane_lists'],
    )

    # 段落画像（H2 挿絵）を注入
    primary_cat = cats[0] if cats else ''
    html = inject_illustrations(html, category=primary_cat)

    # CTAボックスを注入（収益化用）
    cta_slug = post.metadata.get('slug') or path.stem
    html = inject_ctas(html, categories=cats, slug=cta_slug)

    # アフィリエイト URL を実 URL に置換（#REPLACE_*_URL → 本URL）
    # 未承認キーは値が空のまま、placeholder が残る（後で承認後に再公開で置換）
    if AFFILIATE_LINKS:
        html, _affi_count = apply_replacements(html, AFFILIATE_LINKS)

    # タクソノミー解決
    cat_ids = resolve_terms('categories', cats)
    tag_ids = resolve_terms('tags', tags)

    # アイキャッチをアップロード
    media_id = upload_eyecatch(
        title=title,
        categories=cats,
        excerpt=excerpt,
        file_stem=path.stem,
    )

    payload = {
        'title': title,
        'content': html,
        'status': status,
        'excerpt': excerpt,
    }
    if cat_ids:
        payload['categories'] = cat_ids
    if tag_ids:
        payload['tags'] = tag_ids
    if media_id:
        payload['featured_media'] = media_id
    if scheduled_date:
        # WordPress は date / date_gmt の両方を受けるが、date のみで十分（サーバ側でGMT変換）
        payload['date'] = scheduled_date

    r = requests.post(f'{WP_URL}/wp-json/wp/v2/posts',
                      json=payload, headers=auth_header(), timeout=60)
    r.raise_for_status()
    data = r.json()
    schedule_note = f' (scheduled: {scheduled_date})' if scheduled_date and status == 'future' else ''
    print(f'✓ Posted: {title}{schedule_note}')
    print(f'  ID:  {data["id"]}')
    print(f'  URL: {data["link"]}')
    return data


# ── メインループ ────────────────────────────────
def main():
    new_posts = sorted(
        p for p in POSTS_DIR.glob('*.md')
        if p.is_file() and not p.name.endswith('.tweets.md')
    )
    if not new_posts:
        print('No new posts to publish.')
        return

    failed = False
    for path in new_posts:
        try:
            post_article(path)
            target = PUBLISHED_DIR / path.name
            path.rename(target)
            print(f'  Moved to {target}')
        except Exception as e:
            print(f'✗ Failed: {path}: {e}', file=sys.stderr)
            failed = True

    if failed:
        sys.exit(1)


if __name__ == '__main__':
    main()
