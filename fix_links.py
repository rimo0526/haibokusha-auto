"""WP公開済み記事 + Compass HTML の placeholder URL を一括 fix する緊急対応スクリプト。

問題：WP上に残った `#REPLACE_*_URL` （未承認キーが空文字のまま）→ クリックしても飛べない。
解決：未承認キーには **fallback URL（カテゴリ整合の確定済みアフィ）** を割り当てて、
       placeholder ゼロを保証する。

使い方：
  WP_URL=https://haibokusha.com WP_USERNAME=xxx WP_APP_PASSWORD=xxx \
    python fix_links.py            # ドライラン（修正候補を表示）
  python fix_links.py --apply      # WP REST 更新 + Compass HTML 書換
  python fix_links.py --apply --wp-only        # WPのみ
  python fix_links.py --apply --compass-only   # Compass HTMLのみ
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
from typing import Dict, List, Tuple

try:
    from inject_affiliate_links import AFFILIATE_LINKS
except ImportError:
    AFFILIATE_LINKS = {}

# ── Fallback URL Map（未承認キーをカテゴリ整合の確定済URLにマッピング） ──
# 値が空のキーが本文に残ると placeholder が露出するため、必ず確定URLにfallbackする。
FALLBACK_MAP = {
    # 弁護士系：アビエス（カテゴリ：借金・債務整理）
    "BENGOSHI_ADIRE":   "BENGOSHI_ABIES",
    # NISA系：DMM株（カテゴリ：投資）
    "RAKUTEN_SHOKEN":   "DMM_KABU",
    "SBI_SHOKEN":       "DMM_KABU",
    # デビカ系：Nexus Card（カテゴリ：クレカ）
    "RAKUTEN_DEBIT":    "KASHIKINE_NEXUS",
    # 家計簿：ココナラ副業へ→ 整合性微妙だがリンク切れよりマシ
    "MFW":              "COCONALA",
    # 資格学習：資格スクエア
    "STUDYING":         "GAKUSHU_SQUARE",
    # Amazon書籍：Audible（カテゴリ：書籍コンテンツ）
    "AMAZON_BOOK":      "AUDIBLE",
}

# 環境変数
WP_URL = os.environ.get("WP_URL", "").rstrip("/")
WP_USERNAME = os.environ.get("WP_USERNAME", "")
WP_APP_PASSWORD = os.environ.get("WP_APP_PASSWORD", "")

REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOY_DIR = REPO_ROOT / "_deploy"

PLACEHOLDER_RE = re.compile(r"#REPLACE_([A-Z_]+)_URL")


def auth_header():
    cred = f"{WP_USERNAME}:{WP_APP_PASSWORD}"
    return {"Authorization": "Basic " + base64.b64encode(cred.encode()).decode("ascii"),
            "User-Agent": "haibokusha-fix-links/1.0"}


def http_get(path: str) -> dict:
    req = urllib.request.Request(f"{WP_URL}{path}", headers=auth_header())
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def wp_update(post_id: int, payload: dict) -> dict:
    headers = {**auth_header(), "Content-Type": "application/json; charset=utf-8"}
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(f"{WP_URL}/wp-json/wp/v2/posts/{post_id}",
                                 data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def resolve_url(key: str) -> Tuple[str, str]:
    """
    placeholder key → 実 URL を解決。
    1. AFFILIATE_LINKS[key] が非空 → そのまま使う
    2. 空 → FALLBACK_MAP[key] を見て、その先のキーで再帰解決
    3. 解決できなければ `#` （但しこのケースは設計上発生しないはず）
    戻り値: (URL, 由来) 由来は "direct" / "fallback:XYZ" / "broken"
    """
    direct = AFFILIATE_LINKS.get(key, "")
    if direct:
        return direct, "direct"
    fb_key = FALLBACK_MAP.get(key)
    if fb_key:
        fb_url = AFFILIATE_LINKS.get(fb_key, "")
        if fb_url:
            return fb_url, f"fallback:{fb_key}"
    return "https://haibokusha.com/", "broken→ホームへ"


def fix_text(text: str) -> Tuple[str, Dict[str, int]]:
    """テキスト内の #REPLACE_KEY_URL を全て解決する。
    戻り値: (修正後テキスト, key→置換回数)
    """
    counter: Dict[str, int] = {}
    new_text = text
    keys_in_text = set(PLACEHOLDER_RE.findall(text))
    for key in keys_in_text:
        ph = f"#REPLACE_{key}_URL"
        url, origin = resolve_url(key)
        cnt = new_text.count(ph)
        if cnt > 0:
            new_text = new_text.replace(ph, url)
            counter[f"{key}→{origin}"] = cnt
    return new_text, counter


def fix_wp(dry_run: bool = True) -> List[dict]:
    results = []
    page = 1
    while True:
        try:
            posts = http_get(
                f"/wp-json/wp/v2/posts?per_page=50&page={page}"
                "&_fields=id,slug,title,content,status&status=publish,future"
            )
        except urllib.error.HTTPError as e:
            if e.code == 400 and page > 1:
                break
            raise
        if not posts:
            break
        for p in posts:
            content = p.get("content", {}).get("rendered", "")
            new_content, counter = fix_text(content)
            if counter:
                row = {"id": p["id"], "slug": p.get("slug", ""),
                       "title": p.get("title", {}).get("rendered", "")[:50],
                       "fixes": counter, "applied": False}
                results.append(row)
                if not dry_run:
                    try:
                        wp_update(p["id"], {"content": new_content})
                        row["applied"] = True
                        time.sleep(0.4)
                    except Exception as e:
                        row["error"] = str(e)
        if len(posts) < 50:
            break
        page += 1
    return results


def fix_compass(dry_run: bool = True) -> List[dict]:
    """Compass _deploy/*.html の placeholder を一括書換"""
    results = []
    if not DEPLOY_DIR.exists():
        print(f"  ! _deploy not found at {DEPLOY_DIR}", file=sys.stderr)
        return results
    htmls = sorted(DEPLOY_DIR.glob("*.html")) + sorted(DEPLOY_DIR.glob("**/*.html"))
    seen = set()
    for path in htmls:
        if path in seen:
            continue
        seen.add(path)
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        new_text, counter = fix_text(text)
        if counter:
            row = {"path": str(path.relative_to(REPO_ROOT)), "fixes": counter, "applied": False}
            results.append(row)
            if not dry_run:
                path.write_text(new_text, encoding="utf-8")
                row["applied"] = True
    return results


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    p.add_argument("--wp-only", action="store_true")
    p.add_argument("--compass-only", action="store_true")
    args = p.parse_args()

    print("=" * 70)
    print(f" Mode: {'APPLY' if args.apply else 'DRY-RUN'}")
    print(f" AFFILIATE_LINKS dict: {len(AFFILIATE_LINKS)} keys "
          f"({sum(1 for v in AFFILIATE_LINKS.values() if v)} non-empty)")
    print(f" FALLBACK_MAP: {len(FALLBACK_MAP)} mappings")
    print("=" * 70)

    if not args.compass_only:
        if not (WP_URL and WP_USERNAME and WP_APP_PASSWORD):
            print("\n[WP] 環境変数未設定 → スキップ")
        else:
            print("\n[WP] 公開記事チェック中...")
            wp_results = fix_wp(dry_run=not args.apply)
            print(f"  対象: {len(wp_results)} 記事")
            for r in wp_results:
                mark = "✓" if r.get("applied") else ("ERR" if r.get("error") else "·")
                print(f"  {mark} ID={r['id']:4d} slug={r['slug'][:40]}")
                for fix, n in r["fixes"].items():
                    print(f"      ×{n:2d}  {fix}")
                if r.get("error"):
                    print(f"      err: {r['error']}")

    if not args.wp_only:
        print("\n[Compass] _deploy/*.html チェック中...")
        cp_results = fix_compass(dry_run=not args.apply)
        print(f"  対象: {len(cp_results)} ファイル")
        for r in cp_results:
            mark = "✓" if r.get("applied") else "·"
            print(f"  {mark} {r['path']}")
            for fix, n in r["fixes"].items():
                print(f"      ×{n:2d}  {fix}")

    print()
    if not args.apply:
        print("--apply で確定実行")


if __name__ == "__main__":
    main()
