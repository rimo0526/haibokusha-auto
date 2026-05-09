"""WP公開記事のアビエス法律事務所バナーを A8 公式素材（300x250、5YZ75ペア）に統一する。

A8 公式素材は image+click URL のペアで A8 が impression/click 計測を行うので、
両方をセットで置換する。

検出・置換対象（image）：
  - https://www.abies-law.jp/img/img/co_favicon.webp  （旧 favicon、486で投稿）
  - https://www.abies-law.jp/img/img/co_logo.png      （404 broken）
  - https://www.abies-law.jp/img/img/co_logo.webp     （公式サイトロゴ、暫定使用）
   ↓
  - https://www27.a8.net/svt/bgt?aid=251021005499&wid=003&eno=01&mid=s00000027079001003000&mc=1
    （A8 公式 300x250 バナー）

検出・置換対象（click URL）：
  - https://px.a8.net/svt/ejp?a8mat=45G91P+893D6Q+5SXY+5YJRM （5YJRM、旧素材ID）
   ↓
  - https://px.a8.net/svt/ejp?a8mat=45G91P+893D6Q+5SXY+5YZ75 （5YZ75、A8 公式バナーとペア）

SiteGuard 対策で wp_update は POST + X-HTTP-Method-Override: PUT を使う。

使い方：
  python fix_abies_image.py            # dry-run（変更なし、検出のみ）
  python fix_abies_image.py --apply    # 実適用
  python fix_abies_image.py --apply --only-id 487
"""
import argparse
import base64
import html as html_lib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


WP_URL = os.environ.get("WP_URL", "").rstrip("/")
WP_USERNAME = os.environ.get("WP_USERNAME", "")
WP_APP_PASSWORD = os.environ.get("WP_APP_PASSWORD", "")

OLD_URLS = [
    # image URLs
    "https://www.abies-law.jp/img/img/co_favicon.webp",
    "https://www.abies-law.jp/img/img/co_logo.png",
    "https://www.abies-law.jp/img/img/co_logo.webp",
    # click URL（古い 5YJRM 素材ID。新しい 5YZ75 ペアに統一）
    "https://px.a8.net/svt/ejp?a8mat=45G91P+893D6Q+5SXY+5YJRM",
]
# 「URL 種別ごとに新しい URL が違う」点を扱うため、from→to のマッピング dict にする。
# OLD_URLS は後方互換用に残す。
URL_REPLACEMENTS = {
    "https://www.abies-law.jp/img/img/co_favicon.webp":
        "https://www27.a8.net/svt/bgt?aid=251021005499&wid=003&eno=01&mid=s00000027079001003000&mc=1",
    "https://www.abies-law.jp/img/img/co_logo.png":
        "https://www27.a8.net/svt/bgt?aid=251021005499&wid=003&eno=01&mid=s00000027079001003000&mc=1",
    "https://www.abies-law.jp/img/img/co_logo.webp":
        "https://www27.a8.net/svt/bgt?aid=251021005499&wid=003&eno=01&mid=s00000027079001003000&mc=1",
    "https://px.a8.net/svt/ejp?a8mat=45G91P+893D6Q+5SXY+5YJRM":
        "https://px.a8.net/svt/ejp?a8mat=45G91P+893D6Q+5SXY+5YZ75",
}
NEW_URL = "https://www27.a8.net/svt/bgt?aid=251021005499&wid=003&eno=01&mid=s00000027079001003000&mc=1"  # 後方互換


def auth_header():
    cred = f"{WP_USERNAME}:{WP_APP_PASSWORD}"
    return {
        "Authorization": "Basic " + base64.b64encode(cred.encode()).decode("ascii"),
        "User-Agent": "haibokusha-fix-abies/1.0",
    }


def http_get(path):
    req = urllib.request.Request(f"{WP_URL}{path}", headers=auth_header())
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def wp_update(post_id, payload):
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


def fix_content(html: str) -> tuple:
    """HTML エンティティを実体化してから URL_REPLACEMENTS の各エントリで置換。
    戻り値: (new_html, replacements_per_url_dict)"""
    new = html_lib.unescape(html)
    counts = {}
    for old_url, new_url in URL_REPLACEMENTS.items():
        n = new.count(old_url)
        if n > 0:
            new = new.replace(old_url, new_url)
            counts[old_url] = n
    return new, counts


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true", help="実際にWPを更新（無指定はdry-run）")
    p.add_argument("--only-id", type=int, default=0, help="特定のpost ID のみ処理")
    args = p.parse_args()

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
    print(f" Mode: {'APPLY' if args.apply else 'DRY-RUN'}  only_id={args.only_id}")
    print(f" 旧 → 新: {OLD_URLS} → {NEW_URL}")
    print("=" * 70)

    # 全 publish/future 記事を取得
    page = 1
    targets = []
    while True:
        try:
            posts = http_get(
                f"/wp-json/wp/v2/posts?per_page=50&page={page}"
                "&_fields=id,title,content,status&status=publish,future"
            )
        except urllib.error.HTTPError as e:
            if e.code == 400 and page > 1:
                break
            raise
        if not posts:
            break
        for post in posts:
            if args.only_id and post["id"] != args.only_id:
                continue
            content = post.get("content", {}).get("rendered", "")
            new_content, counts = fix_content(content)
            if not counts:
                continue
            targets.append((post, new_content, counts))
        if len(posts) < 50:
            break
        page += 1

    if not targets:
        print("対象記事なし。すでに正常URLに統一されているか、該当URLが存在しません。")
        return

    print(f"\n=== 対象 {len(targets)} 記事 ===")
    total_replacements = 0
    for post, _, counts in targets:
        title = post["title"]["rendered"][:50]
        replacements = sum(counts.values())
        total_replacements += replacements
        detail = " ".join(f"{u.split('/')[-1]}={n}" for u, n in counts.items())
        print(f"  id={post['id']} status={post['status']} replace={replacements} ({detail})")
        print(f"    title={title}")

    print(f"\n総置換回数: {total_replacements}")

    if not args.apply:
        print("\n(DRY-RUN — 何も変更していません。--apply を付けて再実行してください)")
        return

    # APPLY モード
    print("\n=== APPLY 中 ===")
    success, failure = 0, 0
    for post, new_content, counts in targets:
        pid = post["id"]
        try:
            res = wp_update(pid, {"content": new_content})
            updated_content = res.get("content", {}).get("rendered", "")
            still_old = sum(updated_content.count(u) for u in URL_REPLACEMENTS)
            print(f"  id={pid} ✓ PUT ok | still_old={still_old}", flush=True)

            time.sleep(0.3)
            check = http_get(f"/wp-json/wp/v2/posts/{pid}?_fields=content")
            check_content = check.get("content", {}).get("rendered", "")
            check_old = sum(check_content.count(u) for u in URL_REPLACEMENTS)
            ok = check_old == 0
            mark = "OK" if ok else "VERIFY-FAIL"
            print(f"  id={pid} verify: old_remaining={check_old} [{mark}]", flush=True)
            if ok:
                success += 1
            else:
                failure += 1
        except urllib.error.HTTPError as e:
            body = ""
            try: body = e.read().decode("utf-8")[:300]
            except Exception: pass
            print(f"  id={pid} ERR HTTP {e.code}: {body}", flush=True)
            failure += 1
        except Exception as e:
            print(f"  id={pid} ERR {type(e).__name__}: {e}", flush=True)
            failure += 1

    print("\n" + "=" * 70)
    print(f" Success: {success}  Failure: {failure}  Total: {len(targets)}")
    print("=" * 70)


if __name__ == "__main__":
    main()
