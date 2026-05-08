"""
inject_internal_links.py
========================

haibokusha.com の記事末尾に「関連記事3本」セクションを自動挿入するモジュール。

使い方:
    from inject_internal_links import inject_related_articles

    new_html = inject_related_articles(
        html=original_html,
        category="Money",
        current_slug="2026-05-09-kakeibo-truth",
        n=3,
    )

仕様:
- 挿入位置の優先順位:
    1) 「まとめ」H2 の直後（<h2 ...>まとめ</h2> の直後の </section> または次のH2 直前）
    2) 該当がなければ </body> の直前
    3) </body> もなければ末尾追記
- 冪等: marker `<!-- HB_RELATED -->` が既にHTML内に存在する場合は何もしない
- 自分自身の slug は除外
- 候補が n に満たない場合は、足りない分は他カテゴリからフォールバック

ペルソナ前提:
- 「敗北者」(30代男性、独身、実家暮らし、年収380万、月手取り20万)
- 任意整理2年半・残債131万・月8万返済中
- カテゴリ "Money" / "Mental" / "Save" / "Side" / "Life" の5系統で運用
"""

from __future__ import annotations

import re
from typing import Iterable

# -----------------------------------------------------------------------------
# カテゴリ別 関連記事候補
# -----------------------------------------------------------------------------
# 形式: (slug, title)
# slug は URL に使う形（拡張子なし）。タイトルは表示用。
# 候補は多め（5〜10本）に持つことで、自記事除外しても3本は確保できる。
# -----------------------------------------------------------------------------

RELATED_BY_CATEGORY: dict[str, list[tuple[str, str]]] = {
    "Money": [
        ("2026-05-09-kakeibo-truth", "家計簿は何のためにつける？敗北者が3年続けて気づいたこと"),
        ("2026-05-10-fixed-cost-cut", "固定費削減5パターン：月8万返済中の俺が実際にやった節約"),
        ("2026-05-08-nisa-after-debt-relief", "完済したらNISAやる3つの理由"),
        ("2026-05-15-burnout-after-payoff", "完済後の燃え尽き症候群、どう乗り越える？"),
        ("2026-05-12-credit-info-recovery", "任意整理後の信用情報、5年で本当に消えるのか"),
        ("2026-05-14-bank-loan-strategy", "銀行ローン残21万、繰上返済する派しない派"),
        ("2026-05-18-cash-only-rule", "現金主義に戻したら月2万浮いた話"),
        ("2026-05-20-emergency-fund", "任意整理中でも生活防衛資金は積んだほうがいい"),
    ],
    "Mental": [
        ("2026-05-12-self-denial-escape", "自己否定からの脱却：廃課金時代の僕に伝えたいこと"),
        ("2026-05-16-loneliness-debt", "借金中の孤独感とどう付き合うか"),
        ("2026-05-19-shame-spiral", "恥のループから抜け出す3つのきっかけ"),
        ("2026-05-22-motivation-decay", "返済モチベが落ちる月、俺がやってる回復ルーティン"),
        ("2026-05-24-comparison-trap", "SNSで他人と比較してしまう癖の壊し方"),
        ("2026-05-26-implicit-shame", "実家暮らし30代男のうしろめたさを言語化する"),
    ],
    "Save": [
        ("2026-05-11-jisui-real-cost", "自炊は本当に節約か：実家暮らし男の検証"),
        ("2026-05-13-mvno-switch", "格安SIMに変えて月5,000円浮いた話"),
        ("2026-05-17-subscription-audit", "サブスク総点検：月払い10本を3本に絞った"),
        ("2026-05-21-jitsuka-life-tips", "実家暮らしの節約術10選"),
        ("2026-05-23-utility-cut", "光熱費を月3,000円下げた地味な工夫"),
        ("2026-05-25-clothes-purge", "服を月0円で済ませる：1年やって学んだこと"),
    ],
    "Side": [
        ("2026-05-09-side-zero-yen", "副業1年で収益0円、それでも続ける理由"),
        ("2026-05-15-cowork-vibe-coding", "AI完全初心者がCoworkでバイブコーディング始めた"),
        ("2026-05-18-blog-vs-x", "ブログとX、どっちから始めるべきか敗北者の答え"),
        ("2026-05-20-individual-game-dev", "プログラミング未経験でゲーム開発できるのか"),
        ("2026-05-22-ai-tools-budget", "月3,000円で回すAI副業ツールの組み合わせ"),
    ],
    "Life": [
        ("2026-05-10-jikka-modori", "実家に戻った日、僕が泣かなかった理由"),
        ("2026-05-14-30s-childoji", "30代こどおじの平日タイムテーブル"),
        ("2026-05-17-gacha-sotsugyou", "ソシャゲ卒業から3年、暇との付き合い方"),
        ("2026-05-21-friendship-debt", "借金していた頃の友人関係、どう再構築したか"),
        ("2026-05-23-weekend-routine", "土日を持て余さない：返済期の余暇の使い方"),
    ],
}

# -----------------------------------------------------------------------------
# Marker / Templates
# -----------------------------------------------------------------------------

MARKER = "<!-- HB_RELATED -->"

ASIDE_TEMPLATE = """{marker}
<aside class="hb-related" aria-label="関連記事">
  <h3>関連記事</h3>
  <ul>
{items}
  </ul>
</aside>
"""

ITEM_TEMPLATE = '    <li><a href="/{slug}.html">{title}</a></li>'


# -----------------------------------------------------------------------------
# Core
# -----------------------------------------------------------------------------

def _pick_candidates(
    category: str,
    current_slug: str,
    n: int,
    fallback_categories: Iterable[str] = ("Money", "Mental", "Save", "Side", "Life"),
) -> list[tuple[str, str]]:
    """
    カテゴリから候補を n 本選ぶ。自記事と重複は除外。
    足りなければ他カテゴリからフォールバック補充。
    """
    seen: set[str] = {current_slug}
    picked: list[tuple[str, str]] = []

    primary = RELATED_BY_CATEGORY.get(category, [])
    for slug, title in primary:
        if slug in seen:
            continue
        picked.append((slug, title))
        seen.add(slug)
        if len(picked) >= n:
            return picked

    # フォールバック
    for cat in fallback_categories:
        if cat == category:
            continue
        for slug, title in RELATED_BY_CATEGORY.get(cat, []):
            if slug in seen:
                continue
            picked.append((slug, title))
            seen.add(slug)
            if len(picked) >= n:
                return picked

    return picked


def _build_aside(items: list[tuple[str, str]]) -> str:
    body = "\n".join(ITEM_TEMPLATE.format(slug=s, title=t) for s, t in items)
    return ASIDE_TEMPLATE.format(marker=MARKER, items=body)


def _insert_after_matome(html: str, aside: str) -> tuple[str, bool]:
    """
    「まとめ」H2の直後 — 直近の </section> または次のH2 の直前に挿入。
    挿入できなかった場合は (html, False) を返す。
    """
    # <h2 ...>まとめ</h2> を探す（"まとめ" 単体のH2 を想定）
    h2_re = re.compile(r"<h2[^>]*>\s*まとめ\s*</h2>", re.IGNORECASE)
    m = h2_re.search(html)
    if not m:
        return html, False

    after = m.end()
    # まとめH2 以降で、次の H2 か </section> か </main> を探す
    next_section = re.search(r"</section>|<h2[\s>]|</main>", html[after:])
    if next_section:
        insert_pos = after + next_section.start()
    else:
        insert_pos = after

    new_html = html[:insert_pos] + "\n" + aside + "\n" + html[insert_pos:]
    return new_html, True


def _insert_before_body_close(html: str, aside: str) -> tuple[str, bool]:
    """ </body> 直前に挿入。 """
    idx = html.lower().rfind("</body>")
    if idx == -1:
        return html, False
    new_html = html[:idx] + aside + "\n" + html[idx:]
    return new_html, True


def inject_related_articles(
    html: str,
    category: str,
    current_slug: str,
    n: int = 3,
) -> str:
    """
    記事HTMLに関連記事ブロックを挿入する。

    Args:
        html: 元の記事HTML（フルドキュメント or 本文のみ どちらでもOK）
        category: "Money" / "Mental" / "Save" / "Side" / "Life" のいずれか
        current_slug: 現在の記事 slug（例: "2026-05-09-kakeibo-truth"）
        n: 関連記事の本数（デフォルト3）

    Returns:
        関連記事ブロックを挿入したHTML文字列。
        既に MARKER がある場合は html をそのまま返す（冪等）。
    """
    if MARKER in html:
        # 冪等: 既挿入はスキップ
        return html

    items = _pick_candidates(category, current_slug, n=n)
    if not items:
        return html  # 候補ゼロなら何もしない

    aside = _build_aside(items)

    # 1) まとめH2 後
    new_html, ok = _insert_after_matome(html, aside)
    if ok:
        return new_html

    # 2) </body> 前
    new_html, ok = _insert_before_body_close(html, aside)
    if ok:
        return new_html

    # 3) フォールバック: 末尾
    return html + "\n" + aside


# -----------------------------------------------------------------------------
# Sample test
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    sample_html = """<!doctype html>
<html lang="ja">
<head><meta charset="utf-8"><title>家計簿の真実</title></head>
<body>
  <main>
    <article>
      <h1>家計簿は何のためにつける？</h1>
      <p>どうも、敗北者です。任意整理2年半経って、家計簿について書く。</p>
      <h2>過去の僕は家計簿を「罪滅ぼし」と思っていた</h2>
      <p>あの頃の僕はバカで、家計簿を書くこと自体が反省のフリだった。</p>
      <h2>今の俺の家計簿の使い方</h2>
      <p>俺は今、家計簿を「次の月に何を増やすか」のためだけに使っている。</p>
      <h2>まとめ</h2>
      <p>家計簿は記録じゃなくて、未来の判断材料。</p>
    </article>
  </main>
</body>
</html>
"""
    out = inject_related_articles(
        html=sample_html,
        category="Money",
        current_slug="2026-05-09-kakeibo-truth",
        n=3,
    )
    print("=" * 60)
    print("First injection:")
    print("=" * 60)
    print(out)

    # 冪等性確認
    out2 = inject_related_articles(
        html=out,
        category="Money",
        current_slug="2026-05-09-kakeibo-truth",
        n=3,
    )
    print("=" * 60)
    print("Idempotent check (should equal first):", out == out2)
    print("=" * 60)

    # 「まとめ」がない場合のフォールバック
    no_matome = "<html><body><article><h1>テスト</h1><p>本文</p></article></body></html>"
    out3 = inject_related_articles(
        html=no_matome,
        category="Mental",
        current_slug="some-other-slug",
        n=3,
    )
    print("Fallback (no まとめ, insert before </body>):")
    print(out3)
