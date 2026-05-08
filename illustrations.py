"""
H2セクション挿絵（インラインSVG）。
- 依存ライブラリ不要。記事HTMLの <h2> タグの直前に SVG を挿入する。
- カテゴリ + 見出しキーワード（部分一致）でアイコンを選別。
- 各 SVG は 80×80 ぐらいの軽量な線画 / 幾何アイコン。

設計方針:
  - すべてオリジナル（他者著作物のコピーなし）
  - ブランドカラー（#1E2A3D ネイビー、#E0775E テラコッタ、#95B89A セージ）のみ使用
  - aria-hidden + role=img で alt は親 figure に書く
  - 一画像 ≒ 1 KB 以下（軽量）
"""

import re
from typing import Tuple

# ── ベースSVG共通スタイル（80×80, viewBox=100×100） ──────
def _wrap_svg(inner: str, label: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" '
        f'width="80" height="80" role="img" aria-label="{label}" '
        f'class="hb-section-icon">{inner}</svg>'
    )


# ── アイコンライブラリ ────────────────────────────
# それぞれ「インナーSVG」のみ持つ。_wrap_svg() で囲んで配信。

ICON_MONEY = _wrap_svg(
    # 円マーク + 通帳の意匠
    '<circle cx="50" cy="50" r="42" fill="none" stroke="#1E2A3D" stroke-width="3"/>'
    '<path d="M35 35 L50 55 L65 35 M40 55 H60 M40 65 H60 M50 55 V75" '
    'stroke="#E0775E" stroke-width="3.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
    "お金のアイコン",
)

ICON_GROWTH = _wrap_svg(
    # 右肩上がりの折れ線グラフ + 矢印
    '<path d="M15 80 L15 20" stroke="#1E2A3D" stroke-width="2.5" stroke-linecap="round"/>'
    '<path d="M15 80 L85 80" stroke="#1E2A3D" stroke-width="2.5" stroke-linecap="round"/>'
    '<path d="M22 70 L40 50 L55 60 L78 25" stroke="#E0775E" stroke-width="3.5" '
    'fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
    '<path d="M70 25 L78 25 L78 33" stroke="#E0775E" stroke-width="3.5" '
    'fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
    "成長のアイコン",
)

ICON_MENTAL = _wrap_svg(
    # 顔の輪郭 + 心臓の表現
    '<circle cx="50" cy="44" r="28" fill="none" stroke="#1E2A3D" stroke-width="3"/>'
    '<path d="M50 60 C42 50 32 52 32 62 C32 72 50 80 50 80 C50 80 68 72 68 62 C68 52 58 50 50 60 Z" '
    'fill="#E0775E" opacity="0.85"/>',
    "メンタルのアイコン",
)

ICON_BUSINESS = _wrap_svg(
    # ブリーフケース
    '<rect x="20" y="30" width="60" height="48" rx="4" fill="none" stroke="#1E2A3D" stroke-width="3"/>'
    '<path d="M40 30 V22 H60 V30" stroke="#1E2A3D" stroke-width="3" fill="none" stroke-linejoin="round"/>'
    '<rect x="20" y="48" width="60" height="6" fill="#E0775E"/>'
    '<rect x="46" y="44" width="8" height="14" rx="1" fill="#1E2A3D"/>',
    "ビジネスのアイコン",
)

ICON_WARNING = _wrap_svg(
    # 三角警告
    '<path d="M50 16 L86 78 L14 78 Z" fill="none" stroke="#E0775E" stroke-width="3.5" stroke-linejoin="round"/>'
    '<line x1="50" y1="38" x2="50" y2="58" stroke="#1E2A3D" stroke-width="4" stroke-linecap="round"/>'
    '<circle cx="50" cy="68" r="3" fill="#1E2A3D"/>',
    "注意のアイコン",
)

ICON_CHECK = _wrap_svg(
    # チェックマーク
    '<circle cx="50" cy="50" r="38" fill="none" stroke="#95B89A" stroke-width="3"/>'
    '<path d="M30 52 L45 66 L72 38" stroke="#1E2A3D" stroke-width="5" '
    'fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
    "達成のアイコン",
)

ICON_THINK = _wrap_svg(
    # 電球（気づき・学び）
    '<path d="M50 18 C36 18 26 28 26 42 C26 52 32 58 36 64 V72 H64 V64 C68 58 74 52 74 42 C74 28 64 18 50 18 Z" '
    'fill="none" stroke="#1E2A3D" stroke-width="3" stroke-linejoin="round"/>'
    '<rect x="38" y="74" width="24" height="6" rx="2" fill="#1E2A3D"/>'
    '<rect x="42" y="82" width="16" height="4" rx="2" fill="#1E2A3D"/>'
    '<path d="M44 50 L48 56 L52 46 L56 56 L60 50" stroke="#E0775E" '
    'stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
    "気づきのアイコン",
)

ICON_LIST = _wrap_svg(
    # 箇条書き（ノート）
    '<rect x="22" y="18" width="56" height="64" rx="4" fill="none" stroke="#1E2A3D" stroke-width="3"/>'
    '<line x1="34" y1="36" x2="46" y2="36" stroke="#E0775E" stroke-width="3" stroke-linecap="round"/>'
    '<line x1="50" y1="36" x2="68" y2="36" stroke="#1E2A3D" stroke-width="2.5" stroke-linecap="round"/>'
    '<line x1="34" y1="50" x2="46" y2="50" stroke="#E0775E" stroke-width="3" stroke-linecap="round"/>'
    '<line x1="50" y1="50" x2="68" y2="50" stroke="#1E2A3D" stroke-width="2.5" stroke-linecap="round"/>'
    '<line x1="34" y1="64" x2="46" y2="64" stroke="#E0775E" stroke-width="3" stroke-linecap="round"/>'
    '<line x1="50" y1="64" x2="62" y2="64" stroke="#1E2A3D" stroke-width="2.5" stroke-linecap="round"/>',
    "リストのアイコン",
)

ICON_TIME = _wrap_svg(
    # 時計
    '<circle cx="50" cy="50" r="36" fill="none" stroke="#1E2A3D" stroke-width="3"/>'
    '<line x1="50" y1="50" x2="50" y2="28" stroke="#E0775E" stroke-width="4" stroke-linecap="round"/>'
    '<line x1="50" y1="50" x2="68" y2="58" stroke="#1E2A3D" stroke-width="3.5" stroke-linecap="round"/>'
    '<circle cx="50" cy="50" r="3" fill="#1E2A3D"/>',
    "時間のアイコン",
)

ICON_FAIL = _wrap_svg(
    # 山＋下り（敗北の象徴。シリーズアイコン）
    '<path d="M10 80 L30 30 L50 60 L70 20 L90 80 Z" fill="#1E2A3D" opacity="0.85"/>'
    '<path d="M14 84 L88 84" stroke="#E0775E" stroke-width="3" stroke-linecap="round"/>',
    "失敗のアイコン",
)

ICON_DEFAULT = ICON_LIST  # 未マッチ時のフォールバック


# ── キーワード → アイコン名 のマッピング ──────────
# 「特化度の高いキーワードを上に」が原則。
# 上から順に走査し、最初に一致したルールを採用する。
KEYWORD_RULES = [
    # 失敗・敗北・後悔（いちばん特化）
    (["失敗", "後悔", "ダメ", "やってはいけない", "落とし穴", "罠", "嘘", "ウソ",
      "騙", "敗北", "挫折", "詰ん", "破綻"], "fail"),
    # 注意・警告
    (["注意", "警告", "リスク", "危険", "デメリット", "気をつけ"], "warning"),
    # まとめ・結論・チェック（記事末尾に多い特化見出し）
    (["まとめ", "結論", "ポイント", "チェック", "達成", "完了", "完済", "成功",
      "総括", "終わり"], "check"),
    # メンタル（早期判定）
    (["メンタル", "つらい", "辛い", "うつ", "鬱", "不安", "ストレス",
      "感情", "気持ち", "病ん", "心が", "心の"], "mental"),
    # 投資・成長
    (["投資", "NISA", "iDeCo", "積立", "積み立て", "FIRE", "複利", "資産",
      "運用", "増やす", "株式", "投信"], "growth"),
    # ビジネス・副業
    (["副業", "ビジネス", "起業", "稼ぐ", "仕事", "職場", "転職", "在宅"], "business"),
    # お金・借金（家計簿系特化キーワードのみ。広い「お金」「金」「円」は最後の最後）
    (["家計簿", "貯金", "貯蓄", "節約", "返済", "借金", "ローン", "固定費",
      "サブスク", "保険", "課金", "リボ", "支出", "収入", "給料", "年収"], "money"),
    # 気づき・学び
    (["気づい", "気づき", "学び", "悟り", "教訓", "発見", "本当の", "真実",
      "理由", "なぜ", "原因", "わかった", "知っ"], "think"),
    # 方法・ルール・ステップ・コツ
    (["ルール", "ステップ", "方法", "手順", "やり方", "コツ", "テクニック",
      "リスト", "選び方", "選択"], "list"),
    # 時間・期間（具体的な時間表現に限定）
    (["何年", "何ヶ月", "何ヵ月", "毎日", "毎月", "毎週", "毎年", "1日", "1ヶ月",
      "1年", "ヶ月で", "ヵ月で", "年で", "日で"], "time"),
    # 最後にゆるい「お金関連」フォールバック
    (["お金", "貯まる", "稼げる", "節税"], "money"),
]

ICON_BY_NAME = {
    "money": ICON_MONEY,
    "growth": ICON_GROWTH,
    "mental": ICON_MENTAL,
    "business": ICON_BUSINESS,
    "warning": ICON_WARNING,
    "check": ICON_CHECK,
    "think": ICON_THINK,
    "list": ICON_LIST,
    "time": ICON_TIME,
    "fail": ICON_FAIL,
    "default": ICON_DEFAULT,
}


# ── カテゴリ → デフォルトアイコン名 ──────────────
CATEGORY_FALLBACK = {
    "Money": "money",
    "money": "money",
    "お金": "money",
    "Mental": "mental",
    "mental": "mental",
    "メンタル": "mental",
    "Business": "business",
    "business": "business",
    "副業": "business",
    "About": "list",
}


def select_icon_for_heading(heading_text: str, category: str = "") -> str:
    """見出しテキストとカテゴリから挿絵SVGを選ぶ。"""
    # 見出しキーワード優先
    for keywords, icon_name in KEYWORD_RULES:
        if any(kw in heading_text for kw in keywords):
            return ICON_BY_NAME[icon_name]
    # カテゴリのデフォルト
    fallback_name = CATEGORY_FALLBACK.get(category, "default")
    return ICON_BY_NAME[fallback_name]


# ── HTML 注入 ────────────────────────────────────
H2_PATTERN = re.compile(r"<h2(\s[^>]*)?>(.+?)</h2>", re.DOTALL)


def _strip_html(text: str) -> str:
    """見出し中のタグを取り除く（<strong>等が混ざることがあるため）"""
    return re.sub(r"<[^>]+>", "", text).strip()


def inject_illustrations(html: str, category: str = "") -> str:
    """記事HTMLに対して、各 <h2> の直前にカテゴリ/キーワード適合SVGを挿入する。

    出力は <figure class="hb-section-illust"> でくくり、ブログCSS
    （cocoon-custom-v2.css の hb-section-illust ルール）でレイアウト調整できる。
    """
    def replace(m: re.Match) -> str:
        attrs = m.group(1) or ""
        inner = m.group(2)
        heading = _strip_html(inner)
        icon = select_icon_for_heading(heading, category)
        # figure→h2 の順で出力（h2は元のまま）
        return (
            f'<figure class="hb-section-illust" aria-hidden="true">{icon}</figure>'
            f'<h2{attrs}>{inner}</h2>'
        )

    return H2_PATTERN.sub(replace, html)


if __name__ == "__main__":
    sample = """
<h2>家計簿は何のためにつける？</h2>
<p>本文…</p>
<h2>気づいた『家計簿の本当の役割』</h2>
<p>本文…</p>
<h2>4冊目で実践した3つのルール</h2>
<p>本文…</p>
<h2>まとめ：家計簿が続かない人へ</h2>
<p>本文…</p>
""".strip()
    print(inject_illustrations(sample, category="Money"))
