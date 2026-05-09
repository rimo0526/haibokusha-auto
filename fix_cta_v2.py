"""WP公開記事の旧CTAボックスを 画像付き新CTA(v2) に総入れ替えするスクリプト。

戦略:
  1. 旧 CTA `<h3 class="hb-cta-title">XXX...</h3> ... <small class="hb-cta-disclosure">...</small>` を
     ブランド別キーで識別（XXX = 「DMM株」「Nexus Card」「アビエス」「ココナラ」「マネーフォワード」「楽天」など）
  2. 該当範囲を 同ブランドの **タイプB(Card)** で置換 ← 「中盤の自然訴求」用
  3. 加えて記事冒頭に **タイプA(Hero)** を1つ、末尾に **タイプD(Bottom)** を1つ追加（カテゴリに応じて）
  4. 共通 <style> ブロックは記事冒頭に1度だけ挿入（重複検出して二重挿入回避）

注意:
  - WP は <div> 内に <p> を強制注入する → アンカー範囲を h3〜small に限定して柔軟に
  - 重複適用防止: 既に hb-cta-v2 クラスを含む CTA があれば skip
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

from cta_templates_v2 import (
    CTA_STYLE_BLOCK,
    BRAND_IMAGES,
    BRAND_URLS,
    PRESETS,
    make_cta,
)

WP_URL = os.environ.get("WP_URL", "").rstrip("/")
WP_USERNAME = os.environ.get("WP_USERNAME", "")
WP_APP_PASSWORD = os.environ.get("WP_APP_PASSWORD", "")


def auth_header():
    cred = f"{WP_USERNAME}:{WP_APP_PASSWORD}"
    return {
        "Authorization": "Basic " + base64.b64encode(cred.encode()).decode("ascii"),
        "User-Agent": "haibokusha-cta-v2/1.0",
    }


def http_get(path):
    req = urllib.request.Request(f"{WP_URL}{path}", headers=auth_header())
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def wp_update(post_id, payload):
    headers = {**auth_header(), "Content-Type": "application/json; charset=utf-8"}
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{WP_URL}/wp-json/wp/v2/posts/{post_id}",
        data=data, headers=headers, method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


# ── 旧CTA識別パターン ──
# h3.hb-cta-title 〜 small.hb-cta-disclosure までの範囲を検出
# WPのTOC生成プラグインが <h3> 内に <span id="tocN"> を注入することがあるため、
# h3 内側はワイルドカードで吸収する。
def _h3_pat(brand_keyword: str):
    """h3 class="hb-cta-title" に brand_keyword を含み、
    その後の最初の <small class="hb-cta-disclosure">...</small> までを範囲とする。
    h3内側に <span id="tocN">...</span> 等が注入されていても拾えるよう、
    h3を開いてから brand_keyword に到達するまで何でも許可する。"""
    return re.compile(
        r'<h3 class="hb-cta-title">[^<]*(?:<[^>]+>[^<]*)*?'
        + re.escape(brand_keyword)
        + r'.*?<small class="hb-cta-disclosure">[^<]*</small>',
        re.DOTALL,
    )


PATTERN_TO_BRAND = [
    (_h3_pat("DMM株"),               "DMM_KABU"),
    (_h3_pat("Nexus Card"),          "KASHIKINE_NEXUS"),
    (_h3_pat("アビエス"),             "BENGOSHI_ABIES"),
    (_h3_pat("借金の悩み"),           "BENGOSHI_ABIES"),  # 旧 CTA_BENGOSHI_PRIMARY
    (_h3_pat("ココナラ"),             "COCONALA"),
    (_h3_pat("LIGHT FX"),            "LIGHT_FX"),
    # 旧（fix_cta_mismatch 前に取り残された場合の保険）
    (_h3_pat("楽天証券"),             "DMM_KABU"),
    (_h3_pat("楽天銀行デビット"),      "KASHIKINE_NEXUS"),
    (_h3_pat("マネーフォワード"),      "COCONALA"),
]


def fix_content(html: str, categories: list = None) -> tuple:
    """旧CTAを v2 (Card型) に置換。先頭にスタイル挿入＆Hero追加。
    戻り値: (新HTML, 統計)"""
    counts = {"replaced_card": 0, "skip_already_v2": 0, "added_style": False, "added_hero": False, "added_bottom": False}

    # 既に v2 が入っているなら処理スキップ（多重処理防止）
    if "hb-cta-v2" in html:
        counts["skip_already_v2"] = 1
        return html, counts

    new = html
    used_brands = set()

    # 1. 既存CTA を Card型 に置換
    for pat, brand in PATTERN_TO_BRAND:
        def _repl(m):
            counts["replaced_card"] += 1
            used_brands.add(brand)
            return make_cta(brand, "card")
        new = pat.sub(_repl, new)

    if counts["replaced_card"] == 0:
        # 既存CTAが見つからない場合でも Hero/Bottom は追加してよい（強訴求のため）
        # ただし誤適用回避のため既存に hb-cta-box が含まれている場合のみ
        if "hb-cta-box" not in html:
            return new, counts

    # 2. 記事冒頭にHero（カテゴリに応じてブランド選択）
    primary_cat = (categories[0] if categories else "Money").lower()
    hero_brand = _pick_hero_brand(primary_cat, used_brands)
    if hero_brand:
        hero_html = make_cta(hero_brand, "hero")
        new = hero_html + "\n" + new
        counts["added_hero"] = True
        used_brands.add(hero_brand)

    # 3. 記事末尾にBottom（同上）
    bottom_brand = _pick_bottom_brand(primary_cat, used_brands)
    if bottom_brand:
        bottom_html = make_cta(bottom_brand, "bottom")
        new = new + "\n" + bottom_html
        counts["added_bottom"] = True

    return new, counts


def _pick_hero_brand(primary_cat: str, used: set) -> str:
    """カテゴリと既使用ブランドから Hero に置くブランドを選ぶ。"""
    # 優先順位（カテゴリ別）
    if primary_cat in ("money", "お金"):
        order = ["BENGOSHI_ABIES", "DMM_KABU", "KASHIKINE_NEXUS", "COCONALA"]
    elif primary_cat in ("mental",):
        order = ["BENGOSHI_ABIES", "COCONALA", "DMM_KABU"]
    elif primary_cat in ("business", "副業"):
        order = ["COCONALA", "DMM_KABU", "BENGOSHI_ABIES"]
    else:
        order = ["BENGOSHI_ABIES", "DMM_KABU", "COCONALA"]
    for b in order:
        if b not in used:
            return b
    return None


def _pick_bottom_brand(primary_cat: str, used: set) -> str:
    """末尾は記事の主題と相性の良い最も訴求力のあるブランドを選ぶ。"""
    if primary_cat in ("money", "お金", "mental"):
        order = ["BENGOSHI_ABIES", "DMM_KABU", "COCONALA", "KASHIKINE_NEXUS"]
    elif primary_cat in ("business", "副業"):
        order = ["COCONALA", "DMM_KABU", "BENGOSHI_ABIES"]
    else:
        order = ["BENGOSHI_ABIES", "COCONALA", "DMM_KABU"]
    for b in order:
        if b not in used:
            return b
    return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    p.add_argument("--limit", type=int, default=0)
    args = p.parse_args()

    if not (WP_URL and WP_USERNAME and WP_APP_PASSWORD):
        print("env missing", file=sys.stderr); sys.exit(2)

    print("=" * 70)
    print(f" Mode: {'APPLY' if args.apply else 'DRY-RUN'}")
    print(f" 旧CTA → 画像付き4タイプv2 へ全件アップグレード")
    print("=" * 70)

    page = 1
    total_posts = 0
    total_updated = 0
    while True:
        try:
            posts = http_get(
                f"/wp-json/wp/v2/posts?per_page=50&page={page}"
                "&_fields=id,slug,title,content,status,categories&status=publish,future"
            )
        except urllib.error.HTTPError as e:
            if e.code == 400 and page > 1:
                break
            raise
        if not posts:
            break

        # カテゴリID→名前マップを取得
        cat_map = {}
        if posts and any(p_.get("categories") for p_ in posts):
            try:
                cats = http_get("/wp-json/wp/v2/categories?per_page=100&_fields=id,name,slug")
                for c in cats:
                    cat_map[c["id"]] = c.get("slug", c.get("name", ""))
            except Exception:
                pass

        for p_ in posts:
            total_posts += 1
            if args.limit and total_posts > args.limit:
                break
            content = p_.get("content", {}).get("rendered", "")
            cat_slugs = [cat_map.get(cid, "") for cid in p_.get("categories", [])]
            new_content, counts = fix_content(content, categories=cat_slugs)
            if counts["replaced_card"] > 0:
                title = p_.get("title", {}).get("rendered", "")[:50]
                print(f"\n  [{p_['status']}] id={p_['id']} {title}")
                print(f"      replaced_card={counts['replaced_card']} added_hero={counts['added_hero']} added_bottom={counts['added_bottom']}")
                if args.apply:
                    try:
                        res = wp_update(p_["id"], {"content": new_content})
                        # WP の sanitize でどう変わったか確認
                        ret_content = res.get("content", {}).get("rendered", "")
                        kept_v2 = "hb-cta-v2" in ret_content
                        print(f"      ✓ updated (v2 kept by WP={kept_v2})")
                        total_updated += 1
                        time.sleep(0.5)
                    except urllib.error.HTTPError as e:
                        body = ""
                        try:
                            body = e.read().decode("utf-8")[:200]
                        except Exception:
                            pass
                        print(f"      ERR HTTP {e.code}: {body}")
                    except Exception as e:
                        print(f"      ERR: {type(e).__name__}: {e}")
            elif counts["skip_already_v2"]:
                print(f"  · id={p_['id']} already v2, skipped")
        if len(posts) < 50:
            break
        page += 1

    print("\n" + "=" * 70)
    print(f" 対象: {total_posts}  更新済: {total_updated}")
    print("=" * 70)
    if not args.apply:
        print(" --apply で確定実行")


if __name__ == "__main__":
    main()
