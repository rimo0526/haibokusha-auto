"""ブログ全体の placeholder 残存・リンク切れを監査するスクリプト。

- WP REST API で `haibokusha.com` の公開・予約記事を全部走査
- Compass `_deploy/*.html` も走査
- `#REPLACE_*_URL` の placeholder 残存をカウント
- href の HTTP HEAD で 200/404/その他 を集計（重複は1回だけ）

使い方:
  WP_URL=https://haibokusha.com WP_USERNAME=xxx WP_APP_PASSWORD=xxx \
    python audit_links.py             # placeholder のみ全件チェック（HTTPは省略）
  python audit_links.py --http        # placeholder + 外部リンクの HTTP 監査
  python audit_links.py --wp-only     # WP のみ
  python audit_links.py --compass-only# Compass のみ
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
from collections import Counter
from pathlib import Path

WP_URL = os.environ.get("WP_URL", "https://haibokusha.com").rstrip("/")
WP_USERNAME = os.environ.get("WP_USERNAME", "")
WP_APP_PASSWORD = os.environ.get("WP_APP_PASSWORD", "")

REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOY_DIR = REPO_ROOT / "_deploy"

PLACEHOLDER_RE = re.compile(r"#REPLACE_([A-Z_]+)_URL")
HREF_RE = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)


def auth_header():
    cred = f"{WP_USERNAME}:{WP_APP_PASSWORD}"
    return {
        "Authorization": "Basic " + base64.b64encode(cred.encode()).decode("ascii"),
        "User-Agent": "haibokusha-audit-links/1.0",
    }


def fetch_wp_posts():
    posts = []
    page = 1
    while True:
        url = (
            f"{WP_URL}/wp-json/wp/v2/posts?per_page=50&page={page}"
            "&_fields=id,slug,title,content,status&status=publish,future"
        )
        try:
            req = urllib.request.Request(url, headers=auth_header())
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 400 and page > 1:
                break
            print(f"  ! WP fetch err page={page}: {e}", file=sys.stderr)
            break
        if not data:
            break
        posts.extend(data)
        if len(data) < 50:
            break
        page += 1
    return posts


def head_status(url, timeout=8):
    """HEAD し、ダメなら GET にフォールバック。HTTP ステータス整数 or エラー文字列を返す。"""
    try:
        req = urllib.request.Request(url, method="HEAD",
                                     headers={"User-Agent": "Mozilla/5.0 (audit)"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status
    except urllib.error.HTTPError as e:
        if e.code in (403, 405):
            try:
                req = urllib.request.Request(url, method="GET",
                                             headers={"User-Agent": "Mozilla/5.0 (audit)"})
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    return r.status
            except Exception as e2:
                return f"err:{e2.__class__.__name__}"
        return e.code
    except Exception as e:
        return f"err:{e.__class__.__name__}"


def audit_text(text, source_label, http_check=False):
    """テキストから placeholder + href を抽出し、サマリを返す。"""
    summary = {
        "source": source_label,
        "placeholders": dict(Counter(PLACEHOLDER_RE.findall(text))),
        "hrefs": list(set(HREF_RE.findall(text))),
        "http_status": {},
    }
    if http_check:
        for href in summary["hrefs"]:
            if not href.startswith(("http://", "https://")):
                continue
            if href.startswith("https://haibokusha.com") or href.startswith(
                "https://compound-compass.mc-apps.workers.dev"
            ):
                # 自サイトはスキップ（WP側でだけテストする方が良い）
                continue
            status = head_status(href)
            summary["http_status"][href] = status
            time.sleep(0.2)
    return summary


def audit_wp(http_check=False):
    if not (WP_USERNAME and WP_APP_PASSWORD):
        print("  ! WP creds missing → skipping WP audit", file=sys.stderr)
        return []
    posts = fetch_wp_posts()
    print(f"  WP posts loaded: {len(posts)}")
    rows = []
    for p in posts:
        content = p.get("content", {}).get("rendered", "")
        s = audit_text(
            content,
            f"WP id={p['id']} slug={p.get('slug','')[:40]}",
            http_check=http_check,
        )
        s["id"] = p["id"]
        rows.append(s)
    return rows


def audit_compass(http_check=False):
    if not DEPLOY_DIR.exists():
        print(f"  ! _deploy not found at {DEPLOY_DIR}", file=sys.stderr)
        return []
    rows = []
    htmls = sorted({p for p in DEPLOY_DIR.rglob("*.html")})
    for path in htmls:
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        rel = str(path.relative_to(REPO_ROOT))
        rows.append(audit_text(text, f"compass {rel}", http_check=http_check))
    return rows


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--http", action="store_true", help="外部リンクHTTP監査も行う")
    p.add_argument("--wp-only", action="store_true")
    p.add_argument("--compass-only", action="store_true")
    p.add_argument("--json", action="store_true",
                   help="サマリを JSON で stdout に出力")
    args = p.parse_args()

    print("=" * 70)
    print(f" audit_links  http_check={args.http}")
    print("=" * 70)

    rows = []
    if not args.compass_only:
        print("\n[WP]")
        rows.extend(audit_wp(http_check=args.http))
    if not args.wp_only:
        print("\n[Compass]")
        rows.extend(audit_compass(http_check=args.http))

    # 集計
    total_ph = Counter()
    total_404 = Counter()
    sources_with_ph = []
    sources_with_404 = []
    for r in rows:
        if r["placeholders"]:
            sources_with_ph.append((r["source"], r["placeholders"]))
            for k, v in r["placeholders"].items():
                total_ph[k] += v
        for href, st in r["http_status"].items():
            if isinstance(st, int) and st >= 400:
                total_404[href] += 1
                sources_with_404.append((r["source"], href, st))

    print("\n" + "=" * 70)
    print(" 集計")
    print("=" * 70)
    print(f"  対象: {len(rows)} sources")
    print(f"  placeholder 残存: {len(sources_with_ph)} sources, "
          f"{sum(total_ph.values())} 件 / {len(total_ph)} keys")
    if total_ph:
        for k, v in sorted(total_ph.items(), key=lambda x: -x[1]):
            print(f"    {k}: {v}")
    if args.http:
        print(f"  4xx以上: {len(sources_with_404)} 件 / {len(total_404)} unique URL")
        for href, n in sorted(total_404.items(), key=lambda x: -x[1])[:20]:
            print(f"    ×{n}  {href}")
    print()
    if args.json:
        print(json.dumps({
            "sources": len(rows),
            "placeholder_total": dict(total_ph),
            "broken_external": dict(total_404),
        }, ensure_ascii=False, indent=2))

    # exit code: placeholder が残ってる場合 1
    if total_ph:
        sys.exit(1)


if __name__ == "__main__":
    main()
