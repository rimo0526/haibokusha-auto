"""WP公開記事の旧CTAを 画像付き v2 (Card+Hero+Bottom) に総入れ替え。

処方箋（5/9 ユーザー指示）：
  1. 記事ごとにマッチ回数を必ずログに出す
  2. html.unescape() で &amp; / &#8211; を実体化してから regex
  3. PUT 後に GET し直して置換後の文字列が含まれているか verify
  4. ローカルで完全テスト後に Actions push

戦略：旧 `<h3 class="hb-cta-title">[brandKW]...` を発見したら
   旧CTA区間（h3〜small.disclosure）を v2 Card に置換し、
   さらに記事冒頭に Hero / 末尾に Bottom を追加する。
"""

import argparse
import base64
import html as html_lib
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

from cta_templates_v2 import (
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
    # SiteGuard Lite が PUT/DELETE を弾くので、POST + X-HTTP-Method-Override で
    # PUT 意図を伝える。WP REST API はどちらの形式でも更新として処理する。
    headers = {
        **auth_header(),
        "Content-Type": "application/json; charset=utf-8",
        "X-HTTP-Method-Override": "PUT",
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{WP_URL}/wp-json/wp/v2/posts/{post_id}",
        data=data, headers=headers, method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


# ── 旧CTA識別パターン ──
# WP の content.rendered は <p> 自動挿入や span#tocN 注入があるため、
# 「特定のアンカーテキスト」「ブランド名 h3」「ブランドのアフィURL」のいずれかで識別する。
def _h3_pat(brand_keyword: str):
    """h3.hb-cta-title に brand_keyword を含み、その後の最初の <small.hb-cta-disclosure> までを範囲とする。"""
    return re.compile(
        r'<h3 class="hb-cta-title">[^<]*(?:<[^>]+>[^<]*)*?'
        + re.escape(brand_keyword)
        + r'.*?<small class="hb-cta-disclosure">[^<]*</small>',
        re.DOTALL,
    )


# 同じパターンを「アンカーテキスト全パターン」でも作る（保険）
def _anchor_pat(anchor_text: str):
    """anchor_text を含む <a class="hb-cta-btn"> を見つけ、
    その所属 div.hb-cta-box の最後（<small class="hb-cta-disclosure">..</small>）までを範囲とする。
    所属を確実に取るため、上にさかのぼって<h3 class="hb-cta-title">までを開始点にする。"""
    return re.compile(
        r'<h3 class="hb-cta-title">.*?'
        + re.escape(anchor_text)
        + r'.*?<small class="hb-cta-disclosure">[^<]*</small>',
        re.DOTALL,
    )


PATTERN_TO_BRAND = [
    # 旧CTA識別 - h3 に含まれるキーワード
    (_h3_pat("DMM株"),               "DMM_KABU", "h3:DMM株"),
    (_h3_pat("Nexus Card"),          "KASHIKINE_NEXUS", "h3:Nexus Card"),
    (_h3_pat("アビエス"),             "BENGOSHI_ABIES", "h3:アビエス"),
    (_h3_pat("借金の悩み"),           "BENGOSHI_ABIES", "h3:借金の悩み"),
    (_h3_pat("ココナラ"),             "COCONALA", "h3:ココナラ"),
    (_h3_pat("LIGHT FX"),            "LIGHT_FX", "h3:LIGHT FX"),
    # 旧（fix_cta_mismatch 前のパターン、保険）
    (_h3_pat("楽天証券"),             "DMM_KABU", "h3:楽天証券"),
    (_h3_pat("楽天銀行デビット"),      "KASHIKINE_NEXUS", "h3:楽天銀行デビット"),
    (_h3_pat("マネーフォワード"),      "COCONALA", "h3:マネーフォワード"),
    # 念のためアンカーテキスト識別
    (_anchor_pat("DMM株で口座開設"),   "DMM_KABU", "anchor:DMM株で口座開設"),
    (_anchor_pat("ココナラに登録する"),"COCONALA", "anchor:ココナラに登録する"),
    (_anchor_pat("Nexus Card の詳細"),"KASHIKINE_NEXUS", "anchor:Nexus Card の詳細"),
]


def fix_content(html: str, categories=None) -> tuple:
    counts = {"replaced_card": 0, "skip_already_v2": 0, "added_hero": False, "added_bottom": False, "match_log": []}

    if "hb-cta-v2" in html:
        counts["skip_already_v2"] = 1
        return html, counts

    # HTMLエンティティを実体化（regex の失敗を防ぐ）
    new = html_lib.unescape(html)
    used_brands = set()

    for pat, brand, label in PATTERN_TO_BRAND:
        matches_count = 0
        def _repl(m):
            nonlocal matches_count
            matches_count += 1
            return make_cta(brand, "card")
        new = pat.sub(_repl, new)
        if matches_count > 0:
            counts["replaced_card"] += matches_count
            counts["match_log"].append(f"{label}={matches_count}")
            used_brands.add(brand)

    if counts["replaced_card"] == 0:
        if "hb-cta-box" not in html:
            return new, counts

    # Hero (記事冒頭)
    primary_cat = (categories[0] if categories else "money").lower()
    hero_brand = _pick_hero_brand(primary_cat, used_brands)
    if hero_brand:
        new = make_cta(hero_brand, "hero") + "\n\n" + new
        counts["added_hero"] = True
        used_brands.add(hero_brand)

    # Bottom (記事末尾)
    bottom_brand = _pick_bottom_brand(primary_cat, used_brands)
    if bottom_brand:
        new = new + "\n\n" + make_cta(bottom_brand, "bottom")
        counts["added_bottom"] = True

    return new, counts


def _pick_hero_brand(primary_cat, used):
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


def _pick_bottom_brand(primary_cat, used):
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
    p.add_argument("--only-id", type=int, default=0, help="特定のpost ID のみ処理")
    args = p.parse_args()

    # 起動時診断（GitHub Actions のログから原因切り分けするため）
    print(f"[startup] argv={sys.argv}", flush=True)
    print(f"[startup] env WP_URL set={bool(WP_URL)} len={len(WP_URL)}", flush=True)
    print(f"[startup] env WP_USERNAME set={bool(WP_USERNAME)} len={len(WP_USERNAME)}", flush=True)
    print(f"[startup] env WP_APP_PASSWORD set={bool(WP_APP_PASSWORD)} len={len(WP_APP_PASSWORD)}", flush=True)

    if not (WP_URL and WP_USERNAME and WP_APP_PASSWORD):
        missing = [n for n, v in [('WP_URL', WP_URL),
                                  ('WP_USERNAME', WP_USERNAME),
                                  ('WP_APP_PASSWORD', WP_APP_PASSWORD)] if not v]
        print(f"env missing: {missing}", file=sys.stderr)
        sys.exit(2)

    print("=" * 70)
    print(f" Mode: {'APPLY' if args.apply else 'DRY-RUN'}  limit={args.limit} only_id={args.only_id}")
    print(f" 旧CTA → v2 (Hero+Card+Bottom 画像付き)")
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

        cat_map = {}
        try:
            cats = http_get("/wp-json/wp/v2/categories?per_page=100&_fields=id,name,slug")
            for c in cats:
                cat_map[c["id"]] = c.get("slug", c.get("name", ""))
        except Exception:
            pass

        for p_ in posts:
            if args.only_id and p_["id"] != args.only_id:
                continue
            total_posts += 1
            if args.limit and total_posts > args.limit:
                break
            content = p_.get("content", {}).get("rendered", "")
            cat_slugs = [cat_map.get(cid, "") for cid in p_.get("categories", [])]
            new_content, counts = fix_content(content, categories=cat_slugs)
            title = p_.get("title", {}).get("rendered", "")[:50]
            print(f"\n[post {p_['id']} status={p_['status']}] {title}")
            print(f"  cat={cat_slugs}  content_len={len(content)}")
            print(f"  matches: replaced_card={counts['replaced_card']} hero={counts['added_hero']} bottom={counts['added_bottom']} skip={counts['skip_already_v2']}")
            if counts["match_log"]:
                print(f"  match detail: {counts['match_log']}")

            # 0マッチで非v2 → 内容のスナップショット
            if counts["replaced_card"] == 0 and not counts["skip_already_v2"]:
                snippet_idx = content.find('hb-cta-title')
                if snippet_idx >= 0:
                    print(f"  [DEBUG] hb-cta-title found at idx={snippet_idx}, surrounding 500 chars:")
                    print(f"  >>> {content[max(0,snippet_idx-50):snippet_idx+450]}")
                else:
                    print(f"  [DEBUG] no hb-cta-title in content; first 300 chars:")
                    print(f"  >>> {content[:300]}")

            # 適用判定
            if not args.apply:
                continue
            if counts["replaced_card"] == 0 and not (counts["added_hero"] or counts["added_bottom"]):
                continue

            try:
                res = wp_update(p_["id"], {"content": new_content})
                ret_content = res.get("content", {}).get("rendered", "")
                kept_v2 = "hb-cta-v2" in ret_content
                kept_hero = "hb-cta-hero" in ret_content
                kept_card = "hb-cta-card" in ret_content
                kept_bottom = "hb-cta-bottom" in ret_content
                print(f"  ✓ PUT ok | WP returned: v2={kept_v2} hero={kept_hero} card={kept_card} bottom={kept_bottom}")
                total_updated += 1
                # Verify by re-fetching
                time.sleep(0.3)
                check = http_get(f"/wp-json/wp/v2/posts/{p_['id']}?_fields=content&t=verify")
                check_content = check.get("content", {}).get("rendered", "")
                check_v2 = "hb-cta-v2" in check_content
                print(f"  verify: v2 in re-fetched content = {check_v2}")
                if not check_v2:
                    # サンプル出力
                    idx = check_content.find('hb-cta-title')
                    if idx >= 0:
                        print(f"  [VERIFY-FAIL] hb-cta-title still present at idx={idx}")
                        print(f"  >>> {check_content[max(0,idx-30):idx+300]}")
            except urllib.error.HTTPError as e:
                body = ""
                try: body = e.read().decode("utf-8")[:300]
                except Exception: pass
                print(f"  ERR HTTP {e.code}: {body}")
            except Exception as e:
                print(f"  ERR {type(e).__name__}: {e}")

        if args.only_id and total_posts >= 1:
            break
        if len(posts) < 50:
            break
        page += 1

    print("\n" + "=" * 70)
    print(f" 対象: {total_posts}  更新済: {total_updated}")
    print("=" * 70)


if __name__ == "__main__":
    main()
