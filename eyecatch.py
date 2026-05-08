"""
アイキャッチ画像（1200×630 PNG）を Pillow で直接描画するモジュール。
SVGテンプレート（haibokusha-design/svg/eyecatch-template.svg）の
ビジュアルを Pillow API で再現している。
依存ライブラリ: Pillow のみ。
日本語フォント: Ubuntu では fonts-noto-cjk、Windowsローカルでは Meiryo にフォールバック。
"""

from io import BytesIO
from typing import List, Optional

from PIL import Image, ImageDraw, ImageFont

# ── キャンバスサイズ ─────────────────────────────
W, H = 1200, 630

# ── ブランドカラー（design tokens 同期） ─────────
BG = (250, 247, 242)        # #FAF7F2 暖クリーム
NAVY = (30, 42, 61)         # #1E2A3D 深ネイビー
TERRA = (224, 119, 94)      # #E0775E テラコッタ
GRAY = (75, 85, 99)         # #4B5563
LIGHT = (156, 163, 175)     # #9CA3AF
WHITE = (255, 255, 255)

# ── フォント候補（先頭から見つかった順、(path, ttc_index) のタプル） ─────
# 重要：NotoSansCJK は OTC（OpenType Collection）で複数言語が同梱されている。
# デフォルト index=0 だと SC（簡体字中国語）扱いになり、日本語の漢字/仮名が
# 中華フォントの字形で出るか、豆腐化することがある。
# 通常 index 順は 0=SC, 1=TC, 2=HK, 3=JP, 4=KR ── JPは index=3 が標準。
# パッケージ依存で揺れる場合に備え、複数 index を試行する。
FONT_BOLD_PATHS = [
    # JP 専用フォント（最優先・index=0で確実）
    ("/usr/share/fonts/opentype/noto/NotoSansJP-Bold.otf", 0),
    ("/usr/share/fonts/truetype/noto/NotoSansJP-Bold.otf", 0),
    ("/usr/share/fonts/truetype/fonts-japanese-gothic.ttf", 0),
    ("/usr/share/fonts/opentype/ipafont-gothic/ipagp.ttf", 0),
    ("/usr/share/fonts/truetype/ipaexfont-gothic/ipaexg.ttf", 0),
    # NotoSansCJK の TTC（複数 index フォールバック）
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 3),
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 2),
    ("/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc", 3),
    ("/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc", 2),
    ("/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc", 3),
    ("/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc", 2),
    # Windows（ローカルプレビュー用）
    ("C:\\Windows\\Fonts\\YuGothB.ttc", 0),
    ("C:\\Windows\\Fonts\\meiryob.ttc", 0),
]
FONT_REGULAR_PATHS = [
    ("/usr/share/fonts/opentype/noto/NotoSansJP-Regular.otf", 0),
    ("/usr/share/fonts/truetype/noto/NotoSansJP-Regular.otf", 0),
    ("/usr/share/fonts/truetype/fonts-japanese-gothic.ttf", 0),
    ("/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf", 0),
    ("/usr/share/fonts/truetype/ipaexfont-gothic/ipaexg.ttf", 0),
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 3),
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 2),
    ("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", 3),
    ("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", 2),
    ("/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc", 3),
    ("/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc", 2),
    ("C:\\Windows\\Fonts\\YuGothR.ttc", 0),
    ("C:\\Windows\\Fonts\\meiryo.ttc", 0),
]


def _load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    paths = FONT_BOLD_PATHS if bold else FONT_REGULAR_PATHS
    for entry in paths:
        # 後方互換：旧形式（文字列）も受け付ける
        if isinstance(entry, str):
            path, idx = entry, 0
        else:
            path, idx = entry
        try:
            return ImageFont.truetype(path, size, index=idx)
        except (OSError, IOError, TypeError):
            continue
    # 最終フォールバック（ASCIIのみだが落とさない）
    return ImageFont.load_default()


_BREAK_CHARS = "、。！？!? 　・「」『』"


def _wrap_title(title: str, max_chars: int = 11, max_lines: int = 3) -> List[str]:
    """日本語タイトルの素朴な折り返し（文字数ベース）。
    句読点や記号で切るのを優先し、上限を超えたら強制改行。
    実フォント幅での折り返しが必要な場合は _wrap_title_by_width を使う。
    """
    title = title.strip()
    if not title:
        return [""]
    lines: List[str] = []
    current = ""
    n = len(title)
    for i, ch in enumerate(title):
        current += ch
        # 句読点に当たったら、ある程度長ければ改行
        if ch in _BREAK_CHARS and len(current) >= max(4, max_chars - 4):
            lines.append(current)
            current = ""
            if len(lines) >= max_lines:
                break
            continue
        # 上限到達 → 直後が句読点なら待つ、そうでなければ改行
        if len(current) >= max_chars:
            next_ch = title[i + 1] if i + 1 < n else ""
            if next_ch in _BREAK_CHARS:
                continue
            lines.append(current)
            current = ""
            if len(lines) >= max_lines:
                break
    if current and len(lines) < max_lines:
        lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        if len(lines[-1]) > max_chars:
            lines[-1] = lines[-1][:max_chars] + "…"
    return lines


def _wrap_title_by_width(title: str, draw, font, max_width: int,
                         max_lines: int = 3) -> List[str]:
    """実フォント幅でタイトルを折り返す堅牢版。
    各文字を1つずつ追加してテキスト幅を計測、超過したら直近の句読点まで戻って改行。
    """
    title = title.strip()
    if not title:
        return [""]
    lines: List[str] = []
    current = ""
    for ch in title:
        test = current + ch
        bbox = draw.textbbox((0, 0), test, font=font)
        width = bbox[2] - bbox[0]
        if width > max_width and current:
            # 直近5文字以内に句読点があれば、そこで切る
            cut = -1
            search_start = max(0, len(current) - 6)
            for i in range(len(current) - 1, search_start - 1, -1):
                if current[i] in _BREAK_CHARS:
                    cut = i + 1
                    break
            if 0 < cut < len(current):
                lines.append(current[:cut])
                current = current[cut:] + ch
            else:
                lines.append(current)
                current = ch
            if len(lines) >= max_lines:
                current = ""
                break
        else:
            current = test
    if current and len(lines) < max_lines:
        lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        if lines:
            lines[-1] = lines[-1].rstrip() + "…"
    return lines


def _draw_centered_text(draw, xy_box, text, font, fill):
    """xy_box=(x0,y0,x1,y1) の中央にテキストを描画"""
    x0, y0, x1, y1 = xy_box
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = x0 + (x1 - x0 - tw) / 2 - bbox[0]
    y = y0 + (y1 - y0 - th) / 2 - bbox[1]
    draw.text((x, y), text, font=font, fill=fill)


def generate_eyecatch_png(
    title: str,
    category_label: str,
    subtitle: Optional[str] = None,
) -> bytes:
    """記事のアイキャッチ画像を生成する。

    Args:
        title: 記事タイトル（日本語OK）
        category_label: カテゴリの英大文字表記（"MONEY" / "MENTAL" / "BUSINESS" / "ABOUT" / "BLOG"）
        subtitle: 任意のサブタイトル（最大40字程度推奨）

    Returns:
        PNG画像のバイト列。
    """
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img, "RGBA")

    # ── 左端のテラコッタ帯 ────────────────────────
    draw.rectangle([0, 0, 14, H], fill=TERRA)

    # ── 右上の山＋太陽（ロゴ意匠） ───────────────
    # 太陽 outer halo
    draw.ellipse([1030 - 70, 140 - 70, 1030 + 70, 140 + 70], fill=(224, 119, 94, 46))
    # 太陽 main
    draw.ellipse([1030 - 46, 140 - 46, 1030 + 46, 140 + 46], fill=TERRA)
    # 山（手前）
    draw.polygon(
        [(950, 200), (1006, 110), (1046, 156), (1094, 78), (1150, 200)],
        fill=NAVY,
    )

    # ── カテゴリバッジ ────────────────────────────
    badge_w, badge_h = 150, 36
    badge_x, badge_y = 70, 70
    draw.rounded_rectangle(
        [badge_x, badge_y, badge_x + badge_w, badge_y + badge_h],
        radius=6,
        fill=TERRA,
    )
    cat_font = _load_font(15, bold=True)
    _draw_centered_text(
        draw,
        (badge_x, badge_y, badge_x + badge_w, badge_y + badge_h),
        category_label.upper(),
        cat_font,
        WHITE,
    )

    # ── メインタイトル（最大3行、実フォント幅で折り返し） ──
    # タイトルが長いほどフォントを小さくする（自動フィット）
    title_size = 56 if len(title) <= 26 else (50 if len(title) <= 34 else 44)
    title_font = _load_font(title_size, bold=True)
    title_max_w = W - 70 - 110  # 左マージン70、右の山アートに被らないよう110確保
    lines = _wrap_title_by_width(title, draw, title_font, title_max_w, max_lines=3)
    y = 200
    line_h = int(title_size * 1.36)
    for line in lines:
        draw.text((70, y), line, font=title_font, fill=NAVY)
        y += line_h

    # ── サブタイトル ───────────────────────────
    if subtitle:
        sub_font = _load_font(22, bold=False)
        sub = subtitle.strip()
        if len(sub) > 40:
            sub = sub[:39] + "…"
        # メインタイトル末尾から少し下げて
        sub_y = max(y + 4, 430)
        draw.text((70, sub_y), sub, font=sub_font, fill=GRAY)

    # ── 装飾の階段（右下） ───────────────────────
    sx, sy = 900, 470
    pts = [(0, 100), (0, 80), (40, 80), (40, 60), (80, 60), (80, 40),
           (120, 40), (120, 20), (160, 20), (160, 0)]
    for i in range(len(pts) - 1):
        draw.line(
            [(sx + pts[i][0], sy + pts[i][1]),
             (sx + pts[i + 1][0], sy + pts[i + 1][1])],
            fill=TERRA, width=3,
        )

    # ── ブランド名（左下） ───────────────────────
    brand_y = 540
    draw.line([(70, brand_y - 12), (130, brand_y - 12)], fill=TERRA, width=3)
    brand_font = _load_font(24, bold=True)
    draw.text((70, brand_y - 4), "敗北者の大逆転", font=brand_font, fill=NAVY)

    # ── URL（右下隅） ─────────────────────────
    url_font = _load_font(13, bold=False)
    url_text = "haibokusha.com"
    bbox = draw.textbbox((0, 0), url_text, font=url_font)
    tw = bbox[2] - bbox[0]
    draw.text((W - 70 - tw, H - 36), url_text, font=url_font, fill=LIGHT)

    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# ── カテゴリ表記のマッピング ──────────────────────
CATEGORY_LABEL_MAP = {
    "Money": "MONEY",
    "money": "MONEY",
    "お金": "MONEY",
    "Mental": "MENTAL",
    "mental": "MENTAL",
    "メンタル": "MENTAL",
    "Business": "BUSINESS",
    "business": "BUSINESS",
    "副業": "BUSINESS",
    "About": "ABOUT",
    "About Me": "ABOUT",
    "プロフィール": "ABOUT",
}


def category_to_label(categories: List[str]) -> str:
    """記事のカテゴリリストから、アイキャッチに表示する英大文字ラベルを決定する。"""
    if not categories:
        return "BLOG"
    for cat in categories:
        if cat in CATEGORY_LABEL_MAP:
            return CATEGORY_LABEL_MAP[cat]
    # 不明なら大文字化のみ
    return categories[0].upper()[:10]


if __name__ == "__main__":
    # ローカルプレビュー用
    sample = generate_eyecatch_png(
        title="家計簿は何のためにつける？借金300万返済中に気づいた真実",
        category_label="MONEY",
        subtitle="3冊変えてやっとたどり着いた家計簿の本当の役割",
    )
    out = "preview-eyecatch.png"
    with open(out, "wb") as f:
        f.write(sample)
    print(f"Wrote {out} ({len(sample)} bytes)")
