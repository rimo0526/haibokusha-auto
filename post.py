"""
WordPress Auto Post Script
posts/ 配下の未公開 .md ファイルを WordPress REST API で公開し、
posts/published/ に移動する。
"""

import os
import sys
import base64
import json
from pathlib import Path

import requests
import frontmatter
import markdown

WP_URL = os.environ['WP_URL'].rstrip('/')
WP_USERNAME = os.environ['WP_USERNAME']
WP_APP_PASSWORD = os.environ['WP_APP_PASSWORD']

POSTS_DIR = Path('posts')
PUBLISHED_DIR = POSTS_DIR / 'published'
PUBLISHED_DIR.mkdir(parents=True, exist_ok=True)


def auth_header():
    token = base64.b64encode(f'{WP_USERNAME}:{WP_APP_PASSWORD}'.encode()).decode()
    return {'Authorization': f'Basic {token}', 'Content-Type': 'application/json'}


def resolve_terms(taxonomy, names):
    """カテゴリー or タグ名のリストを ID リストに変換。なければ新規作成。"""
    if not names:
        return []
    ids = []
    headers = auth_header()
    for name in names:
        r = requests.get(f'{WP_URL}/wp-json/wp/v2/{taxonomy}',
                         params={'search': name}, headers=headers, timeout=30)
        r.raise_for_status()
        existing = next((t for t in r.json() if t['name'] == name), None)
        if existing:
            ids.append(existing['id'])
        else:
            r = requests.post(f'{WP_URL}/wp-json/wp/v2/{taxonomy}',
                              json={'name': name}, headers=headers, timeout=30)
            r.raise_for_status()
            ids.append(r.json()['id'])
            print(f'  + Created {taxonomy}: {name}')
    return ids


def post_article(path: Path):
    post = frontmatter.load(path)
    title = post.metadata.get('title', path.stem)
    status = post.metadata.get('status', 'publish')  # publish / draft / future
    excerpt = post.metadata.get('excerpt', '')
    cats = post.metadata.get('categories', [])
    tags = post.metadata.get('tags', [])

    # Markdown → HTML
    html = markdown.markdown(post.content,
                             extensions=['extra', 'tables', 'fenced_code'])

    # Resolve taxonomies
    cat_ids = resolve_terms('categories', cats)
    tag_ids = resolve_terms('tags', tags)

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

    r = requests.post(f'{WP_URL}/wp-json/wp/v2/posts',
                      json=payload, headers=auth_header(), timeout=60)
    r.raise_for_status()
    data = r.json()
    print(f'✓ Posted: {title}')
    print(f'  ID:  {data["id"]}')
    print(f'  URL: {data["link"]}')
    return data


def main():
    # *.md は対象、ただし *.tweets.md（X投稿用ドラフト）は除外
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
