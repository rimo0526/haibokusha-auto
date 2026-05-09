"""assets/cta-images/ の画像を WP メディアライブラリにアップロードし、
URL を _docs/cta-image-urls.json に保存する。
"""

import base64
import json
import os
import sys
import urllib.request
from pathlib import Path

WP_URL = os.environ.get("WP_URL", "").rstrip("/")
WP_USERNAME = os.environ.get("WP_USERNAME", "")
WP_APP_PASSWORD = os.environ.get("WP_APP_PASSWORD", "")

THIS_DIR = Path(__file__).resolve().parent
IMG_DIR = THIS_DIR / "assets" / "cta-images"
OUT_JSON = THIS_DIR / "cta-image-urls.json"


def auth_header(content_type="application/json"):
    cred = f"{WP_USERNAME}:{WP_APP_PASSWORD}"
    return {
        "Authorization": "Basic " + base64.b64encode(cred.encode()).decode("ascii"),
        "Content-Type": content_type,
        "User-Agent": "haibokusha-cta-upload/1.0",
    }


def upload_to_media(filepath: Path):
    ext = filepath.suffix.lstrip(".").lower()
    mime = {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "webp": "image/webp",
        "svg": "image/svg+xml",
        "ico": "image/x-icon",
    }.get(ext, "application/octet-stream")
    headers = auth_header(content_type=mime)
    headers["Content-Disposition"] = f'attachment; filename="{filepath.name}"'
    data = filepath.read_bytes()
    req = urllib.request.Request(
        f"{WP_URL}/wp-json/wp/v2/media", data=data, headers=headers
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    if not (WP_URL and WP_USERNAME and WP_APP_PASSWORD):
        print("env missing", file=sys.stderr); sys.exit(2)
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    existing = {}
    if OUT_JSON.exists():
        try:
            existing = json.loads(OUT_JSON.read_text(encoding="utf-8"))
        except Exception:
            pass
    print(f" img dir: {IMG_DIR}")
    files = sorted(IMG_DIR.glob("*"))
    print(f" files: {len(files)}")
    for f in files:
        slug = f.stem.replace("-og", "")
        if slug in existing.get("urls", {}):
            print(f"  skip {slug} (already uploaded)")
            continue
        try:
            res = upload_to_media(f)
            url = res.get("source_url", "")
            mid = res.get("id")
            existing.setdefault("urls", {})[slug] = url
            existing.setdefault("ids", {})[slug] = mid
            print(f"  ✓ {slug}: id={mid} {url}")
        except Exception as e:
            print(f"  X {slug}: {e}")
    OUT_JSON.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f" -> {OUT_JSON}")


if __name__ == "__main__":
    main()
