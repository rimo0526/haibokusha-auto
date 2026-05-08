"""WP公開記事の CTA ボックスを「実際の遷移先ブランド」に合わせて差し替えるスクリプト。

問題：
  CTA_RAKUTEN_SHOKEN / CTA_RAKUTEN_DEBIT / CTA_MFW を含む CTA ボックスが、
  fix_links.py の FALLBACK_MAP で URL は DMM株 / Nexus Card / ココナラ に解決されるが、
  アンカー・タイトル・本文がそれぞれ「楽天証券」「楽天デビット」「マネーフォワード」のまま。
  ユーザーは「楽天証券」をクリックしたつもりが DMM株 のページに着地し、不信感を持つ。

このスクリプトの動作：
  1. WP REST API で全公開記事を取得
  2. 古い CTA ボックス HTML（「楽天証券で新NISA口座を開設」「マネーフォワードMEで家計を見える化」など）を
     新ブランドの CTA ボックス HTML（DMM株 / Nexus Card / ココナラ）に置換
  3. WP REST API で記事更新

使い方：
  WP_URL=https://haibokusha.com WP_USERNAME=xxx WP_APP_PASSWORD=xxx \
    python fix_cta_mismatch.py            # ドライラン
  python fix_cta_mismatch.py --apply      # 確定実行
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


WP_URL = os.environ.get("WP_URL", "").rstrip("/")
WP_USERNAME = os.environ.get("WP_USERNAME", "")
WP_APP_PASSWORD = os.environ.get("WP_APP_PASSWORD", "")


# 新CTAボックステンプレート（実際の遷移先ブランドに合わせた）
NEW_CTA_DMM_KABU = """<div class="hb-cta-box">
<span class="hb-cta-label">NISA口座</span>
<h3 class="hb-cta-title">DMM株：手数料0円・初心者にも分かりやすい</h3>
<p class="hb-cta-desc">国内株式の取引手数料が0円。スマホアプリのUIがシンプルで、NISAも対応。「証券口座は怖い」と感じる初心者にもとっつきやすい1社です。</p>
<ul class="hb-cta-bullets">
<li>国内株 売買手数料：0円</li>
<li>米国株も取り扱いあり（為替手数料無料キャンペーンあり）</li>
<li>新NISA対応（成長投資枠）</li>
</ul>
<a href="https://px.a8.net/svt/ejp?a8mat=4B3LMU+759KY+1WP2+15QHIA" class="hb-cta-btn" rel="sponsored nofollow noopener">DMM株で口座開設 →</a>
<small class="hb-cta-disclosure">※ 本リンク経由のお申込みで運営者に紹介料が発生します</small>
</div>"""

NEW_CTA_NEXUS = """<div class="hb-cta-box">
<span class="hb-cta-label">クレカ作れない時の選択肢</span>
<h3 class="hb-cta-title">Nexus Card：審査に不安がある人向けカード</h3>
<p class="hb-cta-desc">任意整理中・債務整理経験ありで、新規クレカ審査が通らない人向けの選択肢。デポジット型なので一般カードより審査ハードルが下がります。サブスク・ネット決済用として安心。</p>
<ul class="hb-cta-bullets">
<li>デポジット型（事前入金）でクレカが持てる</li>
<li>VISA加盟店で利用可能</li>
<li>サブスク・ネット決済の "クレカ枠" を埋められる</li>
</ul>
<a href="https://px.a8.net/svt/ejp?a8mat=45G6PM+9ZLVPE+4T5W+5YJRM" class="hb-cta-btn" rel="sponsored nofollow noopener">Nexus Card の詳細を見る →</a>
<small class="hb-cta-disclosure">※ 本リンク経由のお申込みで運営者に紹介料が発生します</small>
</div>"""

NEW_CTA_COCONALA = """<div class="hb-cta-box">
<span class="hb-cta-label">副業 / スキル販売</span>
<h3 class="hb-cta-title">ココナラ：自分のスキルを500円から売れる</h3>
<p class="hb-cta-desc">「自分には売るスキルなんて無い」と思っている人ほど、ココナラ向き。話を聞く・占い・愚痴聞き・Excel代行・文字起こしまで、本気か冗談か微妙なサービスでも売れている。俺も副業で挑戦中の選択肢の1つ。</p>
<ul class="hb-cta-bullets">
<li>登録無料・出品手数料なし</li>
<li>500円から自分の値付け可能</li>
<li>会員数 400万人超のスキルマーケット</li>
</ul>
<a href="https://px.a8.net/svt/ejp?a8mat=4B3LMU+18NKOY+2PEO+OECDE" class="hb-cta-btn" rel="sponsored nofollow noopener">ココナラに登録する →</a>
<small class="hb-cta-disclosure">※ 本リンク経由のお申込みで運営者に紹介料が発生します</small>
</div>"""


# ── 古い CTA ボックスを検出する正規表現 ──
# WP に保存されると class 属性順や空白が変わる可能性があるので、特徴的な日本語文字列で識別

# WPは <div>...</div> 内に <p> を強制挿入し、構造が乱れる。
# 信頼できるアンカーは「<h3 class="hb-cta-title">[特定キーワード]」と
# 同CTAの末尾「<small class="hb-cta-disclosure">...</small>」までの範囲。
# h3 から </small> までを丸ごと「新CTAボックス」に置き換える。

RE_OLD_RAKUTEN_SHOKEN = re.compile(
    r'<h3 class="hb-cta-title">楽天証券.*?<small class="hb-cta-disclosure">[^<]*</small>',
    re.DOTALL,
)
RE_OLD_RAKUTEN_DEBIT = re.compile(
    r'<h3 class="hb-cta-title">楽天銀行デビット.*?<small class="hb-cta-disclosure">[^<]*</small>',
    re.DOTALL,
)
RE_OLD_MFW = re.compile(
    r'<h3 class="hb-cta-title">マネーフォワード.*?<small class="hb-cta-disclosure">[^<]*</small>',
    re.DOTALL,
)

# 新ブランドの内側だけ（h3〜small） 構築する版
NEW_INNER_DMM_KABU = (
    '<h3 class="hb-cta-title">DMM株：手数料0円・初心者にも分かりやすい</h3>\n'
    '<p class="hb-cta-desc">国内株式の取引手数料が0円。スマホアプリのUIがシンプルで、NISAも対応。「証券口座は怖い」と感じる初心者にもとっつきやすい1社です。</p>\n'
    '<ul class="hb-cta-bullets">\n'
    '<li>国内株 売買手数料：0円</li>\n'
    '<li>米国株も取り扱いあり（為替手数料無料キャンペーンあり）</li>\n'
    '<li>新NISA対応（成長投資枠）</li>\n'
    '</ul>\n'
    '<a href="https://px.a8.net/svt/ejp?a8mat=4B3LMU+759KY+1WP2+15QHIA" class="hb-cta-btn" rel="sponsored nofollow noopener">DMM株で口座開設 →</a>\n'
    '<small class="hb-cta-disclosure">※ 本リンク経由のお申込みで運営者に紹介料が発生します</small>'
)
NEW_INNER_NEXUS = (
    '<h3 class="hb-cta-title">Nexus Card：審査に不安がある人向けカード</h3>\n'
    '<p class="hb-cta-desc">任意整理中・債務整理経験ありで、新規クレカ審査が通らない人向けの選択肢。デポジット型なので一般カードより審査ハードルが下がります。</p>\n'
    '<ul class="hb-cta-bullets">\n'
    '<li>デポジット型（事前入金）でクレカが持てる</li>\n'
    '<li>VISA加盟店で利用可能</li>\n'
    '<li>サブスク・ネット決済の "クレカ枠" を埋められる</li>\n'
    '</ul>\n'
    '<a href="https://px.a8.net/svt/ejp?a8mat=45G6PM+9ZLVPE+4T5W+5YJRM" class="hb-cta-btn" rel="sponsored nofollow noopener">Nexus Card の詳細を見る →</a>\n'
    '<small class="hb-cta-disclosure">※ 本リンク経由のお申込みで運営者に紹介料が発生します</small>'
)
NEW_INNER_COCONALA = (
    '<h3 class="hb-cta-title">ココナラ：自分のスキルを500円から売れる</h3>\n'
    '<p class="hb-cta-desc">「自分には売るスキルなんて無い」と思っている人ほど、ココナラ向き。話を聞く・占い・愚痴聞き・Excel代行・文字起こしまで、本気か冗談か微妙なサービスでも売れている。俺も副業で挑戦中の選択肢の1つ。</p>\n'
    '<ul class="hb-cta-bullets">\n'
    '<li>登録無料・出品手数料なし</li>\n'
    '<li>500円から自分の値付け可能</li>\n'
    '<li>会員数 400万人超のスキルマーケット</li>\n'
    '</ul>\n'
    '<a href="https://px.a8.net/svt/ejp?a8mat=4B3LMU+18NKOY+2PEO+OECDE" class="hb-cta-btn" rel="sponsored nofollow noopener">ココナラに登録する →</a>\n'
    '<small class="hb-cta-disclosure">※ 本リンク経由のお申込みで運営者に紹介料が発生します</small>'
)


def auth_header():
    if not (WP_USERNAME and WP_APP_PASSWORD):
        return {"User-Agent": "haibokusha-fix-cta/1.0"}
    cred = f"{WP_USERNAME}:{WP_APP_PASSWORD}"
    return {
        "Authorization": "Basic " + base64.b64encode(cred.encode()).decode("ascii"),
        "User-Agent": "haibokusha-fix-cta/1.0",
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


def fix_content(html):
    """3 種類の古いCTAボックスの中身（h3〜small）を新しいブランドのCTAに置換。"""
    counts = {"RAKUTEN_SHOKEN→DMM_KABU": 0, "RAKUTEN_DEBIT→NEXUS": 0, "MFW→COCONALA": 0}
    new = html

    new, n1 = RE_OLD_RAKUTEN_SHOKEN.subn(NEW_INNER_DMM_KABU, new)
    counts["RAKUTEN_SHOKEN→DMM_KABU"] = n1

    new, n2 = RE_OLD_RAKUTEN_DEBIT.subn(NEW_INNER_NEXUS, new)
    counts["RAKUTEN_DEBIT→NEXUS"] = n2

    new, n3 = RE_OLD_MFW.subn(NEW_INNER_COCONALA, new)
    counts["MFW→COCONALA"] = n3

    counts = {k: v for k, v in counts.items() if v > 0}
    return new, counts


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    args = p.parse_args()

    if not (WP_URL and WP_USERNAME and WP_APP_PASSWORD):
        print("環境変数 WP_URL / WP_USERNAME / WP_APP_PASSWORD が必要", file=sys.stderr)
        sys.exit(2)

    print("=" * 70)
    print(f" Mode: {'APPLY' if args.apply else 'DRY-RUN'}")
    print(f" 古いCTAボックスを 新ブランドCTAに差し替え（楽天→DMM株 / 楽天デビ→Nexus / MFW→ココナラ）")
    print("=" * 70)

    page = 1
    total_changes = 0
    total_posts = 0
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
        for p_ in posts:
            total_posts += 1
            content = p_.get("content", {}).get("rendered", "")
            new_content, counts = fix_content(content)
            if counts:
                title = p_.get("title", {}).get("rendered", "")[:50]
                print(f"\n  [{p_['status']}] id={p_['id']} {title}")
                for k, v in counts.items():
                    print(f"      ×{v}  {k}")
                    total_changes += v
                if args.apply:
                    try:
                        wp_update(p_["id"], {"content": new_content})
                        print(f"      ✓ updated")
                        time.sleep(0.4)
                    except Exception as e:
                        print(f"      ERR: {e}", file=sys.stderr)
        if len(posts) < 50:
            break
        page += 1

    print("\n" + "=" * 70)
    print(f" 対象記事: {total_posts}")
    print(f" 置換総数: {total_changes}")
    print("=" * 70)
    if not args.apply:
        print(" --apply で確定実行")


if __name__ == "__main__":
    main()
