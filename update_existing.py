"""既存公開済み記事に対する画像（OGPアイキャッチ + H2前SVG）の遡及挿入スクリプト。

post.py で扱う `posts/*.md` のフロントマターをローカルから読み込み、
- WP REST GET で公開済み記事を一覧取得
- slug マッチで対象記事を特定
- featured_media が未設定（=0）なら eyecatch を生成 → /wp/v2/media に upload → 記事に紐付け
- 本文の H2 直前にイラスト SVG を挿入（既挿入は冪等でスキップ）
- POST /wp/v2/posts/{id} で記事を更新

実行:
  WP_URL, WP_USERNAME, WP_APP_PASSWORD を環境変数に設定して
  python update_existing.py            # ドライラン（変更なし、計画のみ表示）
  python update_existing.py --apply    # 実際に WP に反映

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
from typing import Dict, List, Optional, Tuple

import frontmatter

# 同じディレクトリの post.py 兄弟モジュール
from eyecatch import generate_eyecatch_png, category_to_label
from illustrations import inject_illustrations
from inject_ctas import inject_ctas


# ── 設定 ──
WP_URL = os.environ.get("WP_URL", "").rstrip("/")
WP_USERNAME = os.environ.get("WP_USERNAME", "")
WP_APP_PASSWORD = os.environ.get("WP_APP_PASSWORD", "")

POSTS_DIR = Path(__file__).parent / "posts"


def auth_header() -> Dict[str, str]:
    cred = f"{WP_USERNAME}:{WP_APP_PASSWORD}"
    token = base64.b64encode(cred.encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {token}"}


def public_header() -> Dict[str, str]:
    return {"User-Agent": "compass-haibokusha-updater/1.0"}


def http_get(url: str, with_auth: bool = False) -> dict:
    headers = auth_header() if with_auth else public_header()
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def http_post_json(url: str, payload: dict) -> dict:
    headers = {**auth_header(), "Content-Type": "application/json; charset=utf-8"}
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def http_post_binary(url: str, data: bytes, filename: str, mime: str) -> dict:
    headers = {
        **auth_header(),
        "Content-Type": mime,
        "Content-Disposition": f'attachment; filename="{filename}"',
    }
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_all_posts() -> List[dict]:
    """公開済み全記事を取得（ページネーション対応、最大100件）"""
    url = f"{WP_URL}/wp-json/wp/v2/posts?per_page=100&_fields=id,date,slug,title,featured_media,categories,status,content"
    return http_get(url, with_auth=False)


def upload_eyecatch_to_wp(title: str, category_label: str, subtitle: str, slug: str) -> Optional[int]:
    """eyecatch を生成→WP media にアップ→media_id を返す。失敗時 None。"""
    try:
        png = generate_eyecatch_png(
            title=title,
            category_label=category_label,
            subtitle=subtitle if subtitle else None,
        )
    except Exception as e:
        print(f"  ! eyecatch 生成失敗: {e}")
        return None
    try:
        url = f"{WP_URL}/wp-json/wp/v2/media"
        result = http_post_binary(url, png, f"{slug}-eyecatch.png", "image/png")
        return result.get("id")
    except Exception as e:
        print(f"  ! media upload 失敗: {e}")
        return None


def find_local_meta(slug_target: str) -> Optional[Tuple[Path, dict]]:
    """ローカル posts/*.md から slug マッチするものを探す。
    フロントマターに slug がない場合はファイル名 stem を slug として使う。"""
    for md in sorted(POSTS_DIR.glob("*.md")):
        if md.name.endswith(".tweets.md"):
            continue
        try:
            post = frontmatter.load(md)
        except Exception:
            continue
        local_slug = post.metadata.get("slug") or md.stem
        # WP slug は %エンコードされていることがあるので、デコード前後両方で照合
        decoded = urllib.parse.unquote(slug_target)
        if local_slug == slug_target or local_slug == decoded or md.stem == slug_target or md.stem == decoded:
            return md, post.metadata
        # タイトル一致でも候補にする
    return None


def determine_subtitle(meta: dict) -> str:
    """frontmatter からサブタイトルを得る。description / excerpt / 空文字"""
    return (meta.get("description") or meta.get("excerpt") or "")[:39]


def build_update_plan() -> List[Dict]:
    """更新計画を組み立てて返す（実行はしない）。"""
    posts = fetch_all_posts()
    plan = []
    for p in posts:
        post_id = p["id"]
        slug = p.get("slug", "")
        decoded_slug = urllib.parse.unquote(slug)
        title = p.get("title", {}).get("rendered", "")
        fm = p.get("featured_media", 0) or 0
        # 本文に既に cc-section-illust や hb-section-illust があればイラスト挿入をスキップ
        content_html = p.get("content", {}).get("rendered", "")
        has_illust = "hb-section-illust" in content_html or "cc-section-illust" in content_html
        # H2 数
        h2_count = len(re.findall(r"<h2", content_html))

        match = find_local_meta(decoded_slug)
        if not match:
            plan.append({
                "id": post_id, "slug": decoded_slug, "title": title,
                "action": "skip", "reason": "no local md match",
                "fm": fm, "h2_count": h2_count, "has_illust": has_illust,
            })
            continue

        md_path, meta = match
        actions = []
        if fm == 0:
            actions.append("upload_eyecatch")
        if h2_count >= 2 and not has_illust:
            actions.append("inject_illustrations")
        if not actions:
            actions = ["nothing"]
        plan.append({
            "id": post_id, "slug": decoded_slug, "title": title,
            "action": ",".join(actions), "fm": fm, "h2_count": h2_count,
            "has_illust": has_illust,
            "local_md": str(md_path),
            "meta": meta,
        })
    return plan


def apply_one(item: Dict) -> Dict:
    """1記事を更新する。戻り値は結果サマリ。"""
    post_id = item["id"]
    slug = item["slug"]
    actions_str = item["action"]
    meta = item.get("meta", {})
    title_full = item.get("title", "") or meta.get("title", "")
    if "&#8221;" in title_full or "&amp;" in title_full:
        # WP は title を HTMLエンティティでエスケープしているので、本来のtitleはmetaから優先
        title_full = meta.get("title", title_full)

    cats = meta.get("categories", [])
    category_label = category_to_label(cats if isinstance(cats, list) else [cats])
    subtitle = determine_subtitle(meta)

    payload = {}
    notes = []

    # 1. featured_media
    if "upload_eyecatch" in actions_str:
        media_id = upload_eyecatch_to_wp(title_full, category_label, subtitle, slug)
        if media_id:
            payload["featured_media"] = media_id
            notes.append(f"fm={media_id}")
        else:
            notes.append("fm=FAIL")

    # 2. inject_illustrations into content
    if "inject_illustrations" in actions_str:
        # 現在のWP本文を取得
        try:
            fresh = http_get(f"{WP_URL}/wp-json/wp/v2/posts/{post_id}?_fields=content", with_auth=False)
            cur_html = fresh.get("content", {}).get("rendered", "")
        except Exception as e:
            cur_html = ""
            notes.append(f"fetch_content_err={e}")
        # 注意: rendered は WordPress による加工後。元の raw を取りたい場合は context=edit が必要だが Basic 認証で利用可能
        try:
            edit_url = f"{WP_URL}/wp-json/wp/v2/posts/{post_id}?context=edit&_fields=content"
            req = urllib.request.Request(edit_url, headers=auth_header())
            with urllib.request.urlopen(req, timeout=30) as r:
                edit_data = json.loads(r.read().decode("utf-8"))
            raw_html = edit_data.get("content", {}).get("raw", cur_html)
        except Exception as e:
            raw_html = cur_html
            notes.append(f"raw_fetch_err={e}")
        if raw_html and "hb-section-illust" not in raw_html:
            new_html = inject_illustrations(raw_html, category=cats[0] if isinstance(cats, list) and cats else "")
            # CTAも未挿入なら入れる（idempotent）
            if "hb-cta-box" not in new_html:
                new_html = inject_ctas(new_html, categories=cats if isinstance(cats, list) else [cats], slug=slug)
                notes.append("cta_injected")
            payload["content"] = new_html
            notes.append(f"illust_h2={item['h2_count']}")
        else:
            # イラスト既挿入だがCTAはまだの可能性
            if raw_html and "hb-cta-box" not in raw_html:
                new_html = inject_ctas(raw_html, categories=cats if isinstance(cats, list) else [cats], slug=slug)
                payload["content"] = new_html
                notes.append("cta_only_injected")
            else:
                notes.append("illust_skip(already)")

    if not payload:
        return {"id": post_id, "slug": slug, "result": "no-change", "notes": notes}

    try:
        res = http_post_json(f"{WP_URL}/wp-json/wp/v2/posts/{post_id}", payload)
        return {"id": post_id, "slug": slug, "result": "updated", "fields": list(payload.keys()), "notes": notes}
    except Exception as e:
        return {"id": post_id, "slug": slug, "result": "error", "error": str(e), "notes": notes}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="実際に WP に反映する（未指定はドライラン）")
    parser.add_argument("--only", help="特定の slug のみ処理")
    args = parser.parse_args()

    if not (WP_URL and WP_USERNAME and WP_APP_PASSWORD):
        print("ERROR: WP_URL / WP_USERNAME / WP_APP_PASSWORD 未設定", file=sys.stderr)
        sys.exit(2)

    print(f"WP_URL: {WP_URL}")
    print(f"Mode: {'APPLY' if args.apply else 'DRY-RUN'}")
    print()

    plan = build_update_plan()
    if args.only:
        plan = [p for p in plan if p["slug"] == args.only or args.only in p["slug"]]

    print(f"対象記事: {len(plan)}件")
    print("─" * 80)
    for p in plan:
        print(f"ID={p['id']:3d}  fm={p['fm']:3d}  h2={p.get('h2_count',0):2d}  illust={p.get('has_illust',False)}  action={p['action']}")
        print(f"          slug={p['slug'][:60]}")
        print(f"          title={p['title'][:60]}")
    print("─" * 80)

    if not args.apply:
        print("\n--apply を付けると実行します。終了。")
        return

    print("\n実行開始...\n")
    results = []
    for item in plan:
        if item["action"] in ("skip", "nothing"):
            print(f"  SKIP ID={item['id']} ({item['action']})")
            continue
        print(f"  RUN  ID={item['id']} {item['slug'][:40]} ...")
        r = apply_one(item)
        results.append(r)
        print(f"       → {r['result']}  notes={r.get('notes', [])}")
        time.sleep(1.0)  # WP WAF への配慮

    ok = sum(1 for r in results if r["result"] == "updated")
    err = sum(1 for r in results if r["result"] == "error")
    print(f"\n完了: 更新={ok}, エラー={err}, 変更なし={len(results)-ok-err}")


if __name__ == "__main__":
    main()
