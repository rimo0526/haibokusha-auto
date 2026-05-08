"""haibokusha + Compass 全記事のアフィリリンク踏破確認＆分類スクリプト。

出力:
  _docs/2026-05-09-link-extraction.csv  : (source, slug/path, anchor_text, href, kind)
  _docs/2026-05-09-link-status.csv      : (source, slug/path, href, status, redirect_chain, error)
"""

import argparse
import base64
import csv
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

WP_URL = os.environ.get("WP_URL", "https://haibokusha.com").rstrip("/")
WP_USERNAME = os.environ.get("WP_USERNAME", "")
WP_APP_PASSWORD = os.environ.get("WP_APP_PASSWORD", "")

REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOY_DIR = REPO_ROOT / "_deploy"
DOCS_DIR = REPO_ROOT / "_docs"

HREF_RE = re.compile(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>([^<]*)</a>', re.IGNORECASE)
PLACEHOLDER_RE = re.compile(
    r'^(?:#REPLACE_[A-Z_]+_URL|\{\{[^}]+\}\}|about:blank|https?://example\.com.*|)$'
)


def auth_header():
    cred = f"{WP_USERNAME}:{WP_APP_PASSWORD}"
    return {"Authorization": "Basic " + base64.b64encode(cred.encode()).decode("ascii")}


def fetch_wp_posts():
    posts = []
    has_auth = bool(WP_USERNAME and WP_APP_PASSWORD)
    status_param = "publish,future" if has_auth else "publish"
    page = 1
    while True:
        url = (
            f"{WP_URL}/wp-json/wp/v2/posts?per_page=100&page={page}"
            f"&_fields=id,slug,title,content,status&status={status_param}"
        )
        try:
            headers = auth_header() if has_auth else {"User-Agent": "haibokusha-audit/1.0"}
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.loads(r.read().decode("utf-8"))
        except Exception as e:
            if page == 1:
                print(f"  ! WP fetch err: {e}", file=sys.stderr)
            break
        if not data or not isinstance(data, list):
            break
        posts.extend(data)
        if len(data) < 100:
            break
        page += 1
    return posts


def classify_href(href):
    if not href or PLACEHOLDER_RE.match(href):
        return "placeholder"
    if href.startswith(("/", "#", "mailto:", "tel:", "javascript:")):
        return "internal"
    if href.startswith(("http://", "https://")):
        return "external"
    if href.startswith(("./", "../")) or href.endswith((".html", ".htm")):
        return "internal"
    if "/" in href:
        first = href.split("/", 1)[0]
        # ドット2つ以上 = 完全ドメインっぽい → 外部に書くべき typo
        if first.count(".") >= 2:
            return "typo"
        return "internal"
    return "typo"


def extract_links(text, source_label, slug):
    rows = []
    for href, anchor in HREF_RE.findall(text):
        href = href.strip()
        anchor = anchor.strip()[:80]
        kind = classify_href(href)
        rows.append((source_label, slug, anchor, href, kind))
    return rows


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def http_error_301(self, req, fp, code, msg, headers):
        infourl = urllib.request.HTTPError(req.full_url, code, msg, headers, fp)
        infourl.status = code
        return infourl
    http_error_302 = http_error_301
    http_error_303 = http_error_301
    http_error_307 = http_error_301
    http_error_308 = http_error_301


def http_check(href, timeout=12):
    chain = []
    if not href.startswith(("http://", "https://")):
        return {"final": "skip", "chain": [], "error": "non-http"}
    current = href
    seen = set()
    opener = urllib.request.build_opener(NoRedirectHandler)
    try:
        for hop in range(10):
            if current in seen:
                return {"final": "err:loop", "chain": chain, "error": "redirect loop"}
            seen.add(current)
            method = "HEAD"
            req = urllib.request.Request(
                current,
                method=method,
                headers={"User-Agent": "Mozilla/5.0 (haibokusha-audit/1.0)"},
            )
            try:
                resp = opener.open(req, timeout=timeout)
                status = resp.status
                chain.append(f"{status} {current[:70]}")
                if status < 300 or status >= 400:
                    return {"final": status, "chain": chain, "error": ""}
                loc = resp.headers.get("Location")
                if not loc:
                    return {"final": status, "chain": chain, "error": "no-loc"}
                current = urllib.parse.urljoin(current, loc)
            except urllib.error.HTTPError as e:
                chain.append(f"{e.code} {current[:70]}")
                if e.code in (403, 405):
                    # HEAD blocked, try GET
                    try:
                        req2 = urllib.request.Request(
                            current, method="GET",
                            headers={"User-Agent": "Mozilla/5.0 (haibokusha-audit/1.0)"})
                        resp2 = opener.open(req2, timeout=timeout)
                        status = resp2.status
                        chain[-1] = f"GET={status} {current[:70]}"
                        if status < 300 or status >= 400:
                            return {"final": status, "chain": chain, "error": ""}
                        loc = resp2.headers.get("Location")
                        if not loc:
                            return {"final": status, "chain": chain, "error": "no-loc"}
                        current = urllib.parse.urljoin(current, loc)
                        continue
                    except urllib.error.HTTPError as e2:
                        return {"final": e2.code, "chain": chain, "error": str(e2)[:80]}
                    except Exception as e2:
                        return {"final": f"err:{type(e2).__name__}", "chain": chain, "error": str(e2)[:80]}
                return {"final": e.code, "chain": chain, "error": str(e)[:80]}
            except Exception as e:
                return {"final": f"err:{type(e).__name__}", "chain": chain, "error": str(e)[:80]}
        return {"final": "err:too-many-hops", "chain": chain, "error": "many hops"}
    except Exception as e:
        return {"final": f"err:{type(e).__name__}", "chain": chain, "error": str(e)[:80]}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--no-http", action="store_true")
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--limit", type=int, default=0)
    args = p.parse_args()

    DOCS_DIR.mkdir(exist_ok=True)
    extraction_csv = DOCS_DIR / "2026-05-09-link-extraction.csv"
    status_csv = DOCS_DIR / "2026-05-09-link-status.csv"

    print("[1/3] 抽出開始")
    rows = []

    posts = fetch_wp_posts()
    print(f"  WP posts: {len(posts)} (auth={'yes' if WP_USERNAME and WP_APP_PASSWORD else 'no'})")
    for p_ in posts:
        slug = p_.get("slug", "")[:60]
        content = p_.get("content", {}).get("rendered", "")
        rows.extend(extract_links(content, f"wp:{p_['id']}", slug))

    if DEPLOY_DIR.exists():
        htmls = sorted(DEPLOY_DIR.rglob("*.html"))
        print(f"  Compass HTML: {len(htmls)}")
        for path in htmls:
            try:
                text = path.read_text(encoding="utf-8")
            except Exception:
                continue
            rel = str(path.relative_to(REPO_ROOT))
            rows.extend(extract_links(text, "compass", rel))

    print(f"  抽出済リンク: {len(rows)}")
    with extraction_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["source", "slug_or_path", "anchor_text", "href", "kind"])
        for r in rows:
            w.writerow(r)
    print(f"  → {extraction_csv}")

    if args.no_http:
        print("\n[2/3] HTTP skip")
        return

    print("\n[2/3] HTTP")
    unique_external = sorted({r[3] for r in rows if r[4] == "external"})
    print(f"  unique external: {len(unique_external)}")
    if args.limit:
        unique_external = unique_external[: args.limit]

    results = {}
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(http_check, h): h for h in unique_external}
        done = 0
        for fut in as_completed(futures):
            h = futures[fut]
            try:
                results[h] = fut.result()
            except Exception as e:
                results[h] = {"final": f"err:{type(e).__name__}", "chain": [], "error": str(e)[:80]}
            done += 1
            if done % 10 == 0:
                print(f"    {done}/{len(unique_external)}")
    print(f"  done: {done}/{len(unique_external)}")

    with status_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["source", "slug_or_path", "href", "kind", "final_status", "chain", "error"])
        for src, slug, _a, href, kind in rows:
            if kind != "external":
                w.writerow([src, slug, href, kind, "", "", ""])
                continue
            res = results.get(href, {"final": "?", "chain": [], "error": ""})
            w.writerow([src, slug, href, kind, res["final"], " | ".join(res["chain"]), res["error"]])
    print(f"  → {status_csv}")

    print("\n[3/3] 集計")
    cc = Counter()
    bad = []
    for src, slug, _a, href, kind in rows:
        if kind == "placeholder":
            cc["placeholder"] += 1
            bad.append((src, slug, href, "placeholder", ""))
        elif kind == "typo":
            cc["typo"] += 1
            bad.append((src, slug, href, "typo", ""))
        elif kind != "external":
            cc[kind] += 1
        else:
            res = results.get(href, {"final": "?", "chain": [], "error": ""})
            st = res["final"]
            if isinstance(st, int) and 200 <= st < 400:
                cc["ok"] += 1
            elif isinstance(st, int) and 400 <= st < 500:
                cc["4xx"] += 1
                bad.append((src, slug, href, f"4xx({st})", res["error"]))
            elif isinstance(st, int) and st >= 500:
                cc["5xx"] += 1
                bad.append((src, slug, href, f"5xx({st})", res["error"]))
            else:
                cc[str(st)] += 1
                bad.append((src, slug, href, str(st), res["error"]))

    print(f"  total: {len(rows)}")
    for k, v in sorted(cc.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")

    print(f"\n  bad: {len(bad)}")
    for r in bad[:40]:
        print(f"  [{r[3]}] {r[0]:18} {r[1][:25]:25} | {r[2][:90]}")
    if len(bad) > 40:
        print(f"  ... +{len(bad)-40} more")


if __name__ == "__main__":
    main()
