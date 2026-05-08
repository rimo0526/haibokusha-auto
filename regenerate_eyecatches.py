"""既存公開記事のアイキャッチ画像を再生成して WP に再アップロードするスクリプト。

使い方：
  WP_URL=https://haibokusha.com WP_USERNAME=xxx WP_APP_PASSWORD=xxx \
    python regenerate_eyecatches.py            # ドライラン（一覧のみ表示）
  python regenerate_eyecatches.py --apply      # 実際に再生成 + アップロード

処理フロー：
  1. WP REST GET /posts?per_page=100  → 全公開記事
  2. 各記事の title + categories[] + frontmatter（取れる範囲）
  3. eyecatch.py の generate_eyecatch_png() で再生成
  4. /wp-json/wp/v2/media に POST（multipart/form-data）→ 新メディアID取得
  5. /wp-json/wp/v2/posts/{id} を POST で featured_media を新IDに更新
  6. 旧メディアは残す（削除はユーザー手動）

GitHub Actions から workflow_dispatch で走らせる用途を想定。
"""

import argparse
import base64
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from typing import Dict, List, Optional

# eyecatch.py 同梱
from eyecatch import generate_eyecatch_png, category_to_label

WP_URL = os.environ.get("WP_URL", "").rstrip("/")
WP_USERNAME = os.environ.get("WP_USERNAME", "")
WP_APP_PASSWORD = os.environ.get("WP_APP_PASSWORD", "")


def auth_header() -> Dict[str, str]:
    cred = f"{WP_USERNAME}:{WP_APP_PASSWORD}"
    token = base64.b64encode(cred.encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {token}"}


def http_get(path: str, with_auth: bool = True) -> dict:
    url = f"{WP_URL}{path}"
    headers = auth_header() if with_auth else {}
    headers["User-Agent"] = "haibokusha-eyecatch-regen/1.0"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def http_post_json(path: str, payload: dict, method: str = "POST") -> dict:
    url = f"{WP_URL}{path}"
    headers = {**auth_header(), "Content-Type": "application/json; charset=utf-8"}
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def upload_media(filename: str, png_bytes: bytes, alt_text: str = "") -> int:
    """multipart/form-data 不要で、Content-Disposition + ファイル名指定で直接POST"""
    url = f"{WP_URL}/wp-json/wp/v2/media"
    headers = {
        **auth_header(),
        "Content-Type": "image/png",
        "Content-Disposition": f'attachment; filename="{filename}"',
        "User-Agent": "haibokusha-eyecatch-regen/1.0",
    }
    req = urllib.request.Request(url, data=png_bytes, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=120) as r:
        result = json.loads(r.read().decode("utf-8"))
    media_id = result.get("id")
    # alt_text を別リクエストで設定
    if alt_text and media_id:
        try:
            http_post_json(f"/wp-json/wp/v2/media/{media_id}", {"alt_text": alt_text})
        except Exception:
            pass
    return media_id


def list_all_posts(per_page: int = 100) -> List[dict]:
    out = []
    page = 1
    while True:
        try:
            results = http_get(
                f"/wp-json/wp/v2/posts?per_page={per_page}&page={page}"
                "&_fields=id,slug,title,categories,featured_media,date,status&status=publish,future"
            )
        except urllib.error.HTTPError as e:
            if e.code == 400 and page > 1:
                break
            raise
        if not results:
            break
        out.extend(results)
        if len(results) < per_page:
            break
        page += 1
    return out


def get_category_names(cat_ids: List[int]) -> List[str]:
    """カテゴリIDのリストから日本語名を取得"""
    names = []
    for cid in cat_ids[:3]:  # 最大3つ
        try:
            cat = http_get(f"/wp-json/wp/v2/categories/{cid}?_fields=name,slug")
            names.append(cat.get("name", ""))
        except Exception:
            pass
    return names


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="実際に再生成 + アップロード")
    parser.add_argument("--only", help="特定の slug のみ処理")
    parser.add_argument("--limit", type=int, default=0, help="処理件数上限（デバッグ用）")
    args = parser.parse_args()

    if args.apply and not (WP_URL and WP_USERNAME and WP_APP_PASSWORD):
        print("ERROR: WP_URL / WP_USERNAME / WP_APP_PASSWORD 未設定", file=sys.stderr)
        sys.exit(2)

    print("=" * 60)
    print(f" Mode: {'APPLY' if args.apply else 'DRY-RUN'}")
    print(f" WP_URL: {WP_URL}")
    print("=" * 60)

    posts = list_all_posts()
    print(f"\n対象記事: {len(posts)}件")
    if args.only:
        posts = [p for p in posts if args.only in p.get("slug", "")]
        print(f"  → slug filter で {len(posts)}件に絞り込み")
    if args.limit:
        posts = posts[: args.limit]
        print(f"  → 上限 {args.limit}件")

    success = 0
    failed = 0
    for i, p in enumerate(posts, 1):
        post_id = p["id"]
        slug = p.get("slug", "")
        title = p.get("title", {}).get("rendered", "")
        # HTMLエンティティを軽く解除
        title = title.replace("&#8217;", "'").replace("&#8211;", "-").replace("&amp;", "&")
        title = title.replace("&#8230;", "…").replace("&#12300;", "「").replace("&#12301;", "」")
        cat_ids = p.get("categories", [])

        try:
            cat_names = get_category_names(cat_ids) if args.apply else []
            label = category_to_label(cat_names)

            print(f"\n[{i}/{len(posts)}] ID={post_id} slug={slug}")
            print(f"   title={title[:50]}")
            print(f"   cats={cat_names}  label={label}")

            if not args.apply:
                continue

            # 1. 再生成
            png_bytes = generate_eyecatch_png(title=title, category_label=label)
            print(f"   ✓ 再生成 ({len(png_bytes)} bytes)")

            # 2. アップロード
            filename = f"{slug or post_id}-eyecatch-v2.png"
            new_media_id = upload_media(filename, png_bytes, alt_text=title)
            print(f"   ✓ media POST: id={new_media_id}")

            # 3. 記事の featured_media を更新
            http_post_json(f"/wp-json/wp/v2/posts/{post_id}", {"featured_media": new_media_id})
            print(f"   ✓ post.featured_media 更新")

            success += 1
            time.sleep(0.5)  # rate limit avoidance

        except Exception as e:
            failed += 1
            print(f"   ✗ ERROR: {e}", file=sys.stderr)

    print("\n" + "=" * 60)
    if args.apply:
        print(f" 完了: 成功={success}件, 失敗={failed}件")
    else:
        print(f" --apply を付けると実行します")
    print("=" * 60)


if __name__ == "__main__":
    main()
