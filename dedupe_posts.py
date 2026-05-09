"""WP重複投稿の検出・削除"""
import argparse, base64, html as html_lib, json, os, re, sys, time
import urllib.error, urllib.request
from collections import defaultdict

WP_URL = os.environ.get("WP_URL", "").rstrip("/")
WP_USERNAME = os.environ.get("WP_USERNAME", "")
WP_APP_PASSWORD = os.environ.get("WP_APP_PASSWORD", "")


def auth_header():
    cred = f"{WP_USERNAME}:{WP_APP_PASSWORD}"
    return {"Authorization": "Basic " + base64.b64encode(cred.encode()).decode("ascii"),
            "User-Agent": "haibokusha-dedupe/1.0"}


def http_get(path):
    req = urllib.request.Request(f"{WP_URL}{path}", headers=auth_header())
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def http_delete(post_id, force=True):
    url = f"{WP_URL}/wp-json/wp/v2/posts/{post_id}"
    if force: url += "?force=true"
    req = urllib.request.Request(url, headers=auth_header(), method="DELETE")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def fetch_all():
    posts = []
    for status in ("publish", "future"):
        page = 1
        while True:
            try:
                data = http_get(f"/wp-json/wp/v2/posts?per_page=100&page={page}&_fields=id,date,date_gmt,modified,slug,title,status&status={status}")
            except urllib.error.HTTPError as e:
                if e.code == 400 and page > 1: break
                print(f"err status={status} page={page}: {e}")
                break
            if not data or not isinstance(data, list): break
            posts.extend(data)
            if len(data) < 100: break
            page += 1
    return posts


def normalize_title(t):
    t = html_lib.unescape(t or "")
    return re.sub(r"\s+", " ", t).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    if not (WP_URL and WP_USERNAME and WP_APP_PASSWORD):
        print("env missing", file=sys.stderr); sys.exit(2)

    print("=" * 70)
    print(f" Mode: {'APPLY (FORCE DELETE)' if args.apply else 'DRY-RUN'}")
    print("=" * 70)

    posts = fetch_all()
    print(f"\nTotal posts (publish + future): {len(posts)}")

    by_title = defaultdict(list)
    for p in posts:
        t = normalize_title(p.get("title", {}).get("rendered", ""))
        by_title[t].append(p)

    duplicates = {t: ps for t, ps in by_title.items() if len(ps) > 1}
    print(f"重複タイトル: {len(duplicates)} グループ")

    delete_targets = []
    for t, ps in sorted(duplicates.items()):
        ps_sorted = sorted(ps, key=lambda x: (0 if x["status"] == "publish" else 1, x["id"]))
        keep = ps_sorted[0]
        dels = ps_sorted[1:]
        print(f"\n[Title] {t[:80]}")
        print(f"  KEEP: id={keep['id']} status={keep['status']} date={keep['date']}")
        for d in dels:
            print(f"  DEL : id={d['id']} status={d['status']} date={d['date']}")
            delete_targets.append(d)

    print("\n" + "=" * 70)
    print(f" 削除対象: {len(delete_targets)} 件")
    print("=" * 70)

    if not args.apply:
        print(" --apply で確定実行")
        return

    print("\n[DELETE 実行]")
    success = 0
    failed = []
    for d in delete_targets:
        try:
            res = http_delete(d["id"], force=True)
            print(f"  OK id={d['id']} deleted={res.get('deleted', False)}")
            success += 1
            time.sleep(0.25)
        except urllib.error.HTTPError as e:
            body = ""
            try: body = e.read().decode()[:200]
            except: pass
            print(f"  FAIL id={d['id']}: HTTP {e.code} {body}")
            failed.append((d['id'], e.code))
        except Exception as e:
            print(f"  FAIL id={d['id']}: {type(e).__name__} {e}")
            failed.append((d['id'], str(e)))

    print(f"\n削除成功: {success} / {len(delete_targets)}")
    if failed: print(f"失敗: {failed}")

    print("\n[VERIFY] 再取得")
    posts2 = fetch_all()
    by_title2 = defaultdict(list)
    for p in posts2:
        by_title2[normalize_title(p["title"]["rendered"])].append(p)
    dups2 = {t: ps for t, ps in by_title2.items() if len(ps) > 1}
    print(f"  total: {len(posts2)}, 残存重複: {len(dups2)} グループ")
    for t, ps in dups2.items():
        print(f"  STILL DUP [{t[:60]}]: {[p['id'] for p in ps]}")


if __name__ == "__main__":
    main()

