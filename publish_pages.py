"""WordPress 固定ページ自動投稿スクリプト。

`wp-pages/*.md` の Markdown を WP REST API 経由で 固定ページとして公開する。

特徴：
- 既存の同 slug ページがあれば更新、なければ新規作成（idempotent）
- type="page", status="publish"
- メニュー登録は WP 側で手動（外観 → メニュー）

使用：
  WP_URL, WP_USERNAME, WP_APP_PASSWORD を環境変数に設定して
  python publish_pages.py            # ドライラン
  python publish_pages.py --apply    # 実適用

GitHub Actions から走らせる用途を想定（既存 secret 流用）。
"""

import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional

import frontmatter
import markdown


WP_URL = os.environ.get("WP_URL", "").rstrip("/")
WP_USERNAME = os.environ.get("WP_USERNAME", "")
WP_APP_PASSWORD = os.environ.get("WP_APP_PASSWORD", "")

# wp-pages/ ディレクトリは _work/haibokusha-design/wp-pages/ にある想定
# このスクリプトは _work/haibokusha-auto-template/ から実行されるが、
# GitHub Actions では posts/ と並びで wp-pages/ を置く構成にする
PAGES_DIR_CANDIDATES = [
    Path(__file__).parent / "wp-pages",
    Path(__file__).parent.parent / "haibokusha-design" / "wp-pages",
]


def find_pages_dir() -> Optional[Path]:
    for p in PAGES_DIR_CANDIDATES:
        if p.exists():
            return p
    return None


def auth_header() -> Dict[str, str]:
    cred = f"{WP_USERNAME}:{WP_APP_PASSWORD}"
    token = base64.b64encode(cred.encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {token}"}


def public_header() -> Dict[str, str]:
    return {"User-Agent": "compass-haibokusha-pages-publisher/1.0"}


def http_get(url: str, with_auth: bool = False) -> dict:
    headers = auth_header() if with_auth else public_header()
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def http_post_json(url: str, payload: dict, method: str = "POST") -> dict:
    headers = {**auth_header(), "Content-Type": "application/json; charset=utf-8"}
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def find_existing_page(slug: str) -> Optional[dict]:
    """同じ slug の固定ページが既存なら取得"""
    url = f"{WP_URL}/wp-json/wp/v2/pages?slug={urllib.parse.quote(slug)}&_fields=id,slug,title,status"
    try:
        results = http_get(url, with_auth=True)
        return results[0] if results else None
    except Exception as e:
        print(f"  ! find_existing_page error: {e}")
        return None


def md_to_html(content: str) -> str:
    return markdown.markdown(
        content,
        extensions=['extra', 'tables', 'fenced_code', 'sane_lists'],
    )


def process_page(md_path: Path, dry_run: bool = True) -> dict:
    post = frontmatter.load(md_path)
    title = post.metadata.get("title", "").strip()
    slug = post.metadata.get("slug", md_path.stem).strip()

    if not title:
        return {"slug": slug, "skipped": True, "reason": "no title"}

    html_content = md_to_html(post.content)

    payload = {
        "title": title,
        "slug": slug,
        "status": "publish",
        "content": html_content,
        "excerpt": post.metadata.get("description", "")[:200],
    }

    existing = find_existing_page(slug) if not dry_run else None

    if existing:
        # 更新
        if dry_run:
            return {"slug": slug, "title": title, "action": "would_update", "id": existing["id"]}
        try:
            res = http_post_json(f"{WP_URL}/wp-json/wp/v2/pages/{existing['id']}", payload)
            return {"slug": slug, "title": title, "action": "updated", "id": res.get("id")}
        except Exception as e:
            return {"slug": slug, "title": title, "action": "update_error", "error": str(e)}
    else:
        # 新規
        if dry_run:
            return {"slug": slug, "title": title, "action": "would_create"}
        try:
            res = http_post_json(f"{WP_URL}/wp-json/wp/v2/pages", payload)
            return {"slug": slug, "title": title, "action": "created", "id": res.get("id")}
        except Exception as e:
            return {"slug": slug, "title": title, "action": "create_error", "error": str(e)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="実際に WP に反映する")
    parser.add_argument("--only", help="特定の slug のみ")
    args = parser.parse_args()

    if args.apply and not (WP_URL and WP_USERNAME and WP_APP_PASSWORD):
        print("ERROR: WP_URL / WP_USERNAME / WP_APP_PASSWORD 未設定", file=sys.stderr)
        sys.exit(2)

    pages_dir = find_pages_dir()
    if not pages_dir:
        print("ERROR: wp-pages/ ディレクトリが見つかりません", file=sys.stderr)
        sys.exit(2)

    print(f"Pages dir: {pages_dir}")
    print(f"WP_URL: {WP_URL}")
    print(f"Mode: {'APPLY' if args.apply else 'DRY-RUN'}")
    print()

    md_files = sorted(pages_dir.glob("*.md"))
    if args.only:
        md_files = [p for p in md_files if args.only in p.stem]

    print(f"対象ファイル: {len(md_files)}件")
    print("─" * 80)

    results = []
    for md in md_files:
        try:
            r = process_page(md, dry_run=not args.apply)
            results.append(r)
            print(f"  {r.get('action','?'):16s} {r.get('slug',''):20s} {r.get('title','')[:40]}")
        except Exception as e:
            import traceback; traceback.print_exc()
            print(f"  ERROR  {md.name}: {e}")
            results.append({"slug": md.stem, "error": str(e)})
        if args.apply:
            time.sleep(1.0)

    print()
    if args.apply:
        ok = sum(1 for r in results if r.get("action") in ("created", "updated"))
        err = sum(1 for r in results if "error" in r.get("action", ""))
        print(f"完了: 適用={ok}, エラー={err}")
    else:
        print("--apply を付けると実行します")


if __name__ == "__main__":
    main()
