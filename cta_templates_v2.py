"""画像付きCTA 4タイプ テンプレート定義 (TPO別).

タイプA: Hero Banner   - 記事冒頭、画像左+テキスト右、強い訴求
タイプB: Card          - 中盤、画像上+ベネフィット+ボタン、自然な誘導
タイプC: Inline        - 文中の自然リンク、軽い言及
タイプD: Bottom Final  - 末尾の最強訴求、ロゴ+体験談+ボタン
"""

# 各アフィの公式 OG 画像 URL（公開アクセス可、social embed 用に提供されているもの）
BRAND_IMAGES = {
    "DMM_KABU":         "https://kabu.dmm.com/_img/og/common_230120.png",
    "KASHIKINE_NEXUS":  "https://apply.mycredit.nexuscard.co.jp/lp/common/images/apple-touch-icon.png",
    "BENGOSHI_ABIES":   "https://www.abies-law.jp/img/img/co_logo.png",  # 通常ロゴ
    "COCONALA":         "https://coconala.com/images/facebook.png",
    "LIGHT_FX":         "https://lightfx.jp/images/social/facebook.jpg",
}

# 各アフィのアフィリエイト URL（A8 経由、5/9時点で全て200で実LP着地確認済）
BRAND_URLS = {
    "DMM_KABU":         "https://px.a8.net/svt/ejp?a8mat=4B3LMU+759KY+1WP2+15QHIA",
    "KASHIKINE_NEXUS":  "https://px.a8.net/svt/ejp?a8mat=45G6PM+9ZLVPE+4T5W+5YJRM",
    "BENGOSHI_ABIES":   "https://px.a8.net/svt/ejp?a8mat=45G91P+893D6Q+5SXY+5YJRM",
    "COCONALA":         "https://px.a8.net/svt/ejp?a8mat=4B3LMU+18NKOY+2PEO+OECDE",
    "LIGHT_FX":         "https://px.a8.net/svt/ejp?a8mat=3BDWT8+FDP656+46VO+5YJRM",
}

# ── 共通CSS（HTMLに先頭で1度だけ挿入する想定）──
CTA_STYLE_BLOCK = """<style>
.hb-cta-v2{box-sizing:border-box;border-radius:12px;margin:32px 0;font-family:-apple-system,BlinkMacSystemFont,"Hiragino Kaku Gothic ProN",Meiryo,sans-serif;line-height:1.7}
.hb-cta-v2 *{box-sizing:border-box}
.hb-cta-v2 a{text-decoration:none}

/* ── タイプA: Hero ── */
.hb-cta-hero{display:flex;align-items:stretch;background:linear-gradient(135deg,#1E3A5F 0%,#2C5078 100%);color:#fff;padding:0;overflow:hidden;box-shadow:0 4px 16px rgba(30,58,95,.25)}
.hb-cta-hero__img{flex:0 0 35%;background:#fff;padding:16px;display:flex;align-items:center;justify-content:center}
.hb-cta-hero__img img{max-width:100%;max-height:140px;height:auto;object-fit:contain}
.hb-cta-hero__body{flex:1;padding:20px 24px}
.hb-cta-hero__label{display:inline-block;background:#FBC97A;color:#1E3A5F;font-weight:700;font-size:12px;padding:3px 10px;border-radius:4px;margin-bottom:8px}
.hb-cta-hero__title{font-size:18px;font-weight:700;margin:0 0 8px;color:#fff;line-height:1.4}
.hb-cta-hero__desc{font-size:14px;margin:0 0 14px;color:#E8EFF7}
.hb-cta-hero__btn{display:inline-block;background:#C56A4E;color:#fff;font-weight:700;padding:10px 22px;border-radius:6px;font-size:15px}
.hb-cta-hero__btn:hover{background:#A85940}
@media(max-width:600px){.hb-cta-hero{flex-direction:column}.hb-cta-hero__img{flex:0 0 auto;padding:18px}.hb-cta-hero__img img{max-height:80px}.hb-cta-hero__btn{display:block;text-align:center;width:100%;padding:12px 16px}}

/* ── タイプB: Card ── */
.hb-cta-card{background:#FFF;border:1px solid #DDE3EC;border-radius:12px;padding:0;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.06)}
.hb-cta-card__img{width:100%;background:#F7F3EC;padding:20px;text-align:center}
.hb-cta-card__img img{max-width:60%;max-height:90px;height:auto}
.hb-cta-card__body{padding:18px 22px}
.hb-cta-card__label{display:inline-block;background:#1E3A5F;color:#fff;font-size:11px;font-weight:700;padding:3px 8px;border-radius:4px;margin-bottom:6px}
.hb-cta-card__title{font-size:17px;font-weight:700;margin:0 0 8px;color:#1E3A5F;line-height:1.4}
.hb-cta-card__desc{font-size:14px;margin:0 0 12px;color:#444}
.hb-cta-card__benefits{margin:0 0 14px;padding:0;list-style:none}
.hb-cta-card__benefits li{position:relative;padding:3px 0 3px 22px;font-size:13px;color:#1E3A5F}
.hb-cta-card__benefits li::before{content:"✓";position:absolute;left:4px;top:3px;color:#C56A4E;font-weight:900}
.hb-cta-card__btn{display:block;background:#C56A4E;color:#fff;font-weight:700;text-align:center;padding:12px 16px;border-radius:6px;font-size:15px}
.hb-cta-card__btn:hover{background:#A85940}
.hb-cta-card__disc{font-size:11px;color:#888;margin:8px 0 0;text-align:center}

/* ── タイプC: Inline ── */
.hb-cta-inline{display:inline-flex;align-items:center;gap:6px;background:#FFF8E7;padding:4px 10px;border-radius:4px;border-bottom:2px solid #FBC97A;font-weight:600;color:#1E3A5F}
.hb-cta-inline img{width:18px;height:18px;border-radius:3px;object-fit:contain;background:#fff;padding:1px}
.hb-cta-inline:hover{background:#FBE8B5}

/* ── タイプD: Bottom Final ── */
.hb-cta-bottom{background:#F7F3EC;border:2px solid #C56A4E;border-radius:12px;padding:24px;text-align:center}
.hb-cta-bottom__top{display:flex;align-items:center;justify-content:center;gap:14px;margin-bottom:16px}
.hb-cta-bottom__top img{width:80px;height:80px;object-fit:contain;background:#fff;border-radius:8px;padding:6px;border:1px solid #DDE3EC}
.hb-cta-bottom__brandname{font-size:13px;font-weight:700;color:#666;letter-spacing:1px}
.hb-cta-bottom__title{font-size:22px;font-weight:800;color:#1E3A5F;margin:0 0 12px;line-height:1.4}
.hb-cta-bottom__quote{font-size:14px;color:#444;background:#FFF;padding:14px 18px;border-left:4px solid #C56A4E;text-align:left;margin:0 0 16px;border-radius:4px}
.hb-cta-bottom__benefits{display:flex;flex-wrap:wrap;justify-content:center;gap:10px;margin:0 0 18px;padding:0;list-style:none}
.hb-cta-bottom__benefits li{background:#FFF;border:1px solid #DDE3EC;border-radius:20px;padding:6px 14px;font-size:13px;color:#1E3A5F;font-weight:600}
.hb-cta-bottom__btn{display:inline-block;background:linear-gradient(135deg,#C56A4E 0%,#E08263 100%);color:#fff;font-weight:800;padding:14px 32px;border-radius:8px;font-size:17px;box-shadow:0 4px 12px rgba(197,106,78,.3);min-width:240px}
.hb-cta-bottom__btn:hover{background:linear-gradient(135deg,#A85940 0%,#C56A4E 100%);transform:translateY(-1px)}
.hb-cta-bottom__disc{font-size:11px;color:#888;margin:14px 0 0}
@media(max-width:600px){.hb-cta-bottom__btn{display:block;width:100%}}
</style>"""


def cta_hero(brand_key: str, label: str, title: str, desc: str, btn: str) -> str:
    img = BRAND_IMAGES[brand_key]
    url = BRAND_URLS[brand_key]
    return (
        f'<aside class="hb-cta-v2 hb-cta-hero">'
        f'<div class="hb-cta-hero__img"><img src="{img}" alt="{title}" loading="lazy"></div>'
        f'<div class="hb-cta-hero__body">'
        f'<span class="hb-cta-hero__label">{label}</span>'
        f'<h3 class="hb-cta-hero__title">{title}</h3>'
        f'<p class="hb-cta-hero__desc">{desc}</p>'
        f'<a href="{url}" class="hb-cta-hero__btn" rel="sponsored nofollow noopener">{btn} →</a>'
        f'</div>'
        f'</aside>'
    )


def cta_card(brand_key: str, label: str, title: str, desc: str, benefits: list, btn: str) -> str:
    img = BRAND_IMAGES[brand_key]
    url = BRAND_URLS[brand_key]
    benefits_html = "".join(f"<li>{b}</li>" for b in benefits)
    return (
        f'<aside class="hb-cta-v2 hb-cta-card">'
        f'<div class="hb-cta-card__img"><img src="{img}" alt="{title}" loading="lazy"></div>'
        f'<div class="hb-cta-card__body">'
        f'<span class="hb-cta-card__label">{label}</span>'
        f'<h3 class="hb-cta-card__title">{title}</h3>'
        f'<p class="hb-cta-card__desc">{desc}</p>'
        f'<ul class="hb-cta-card__benefits">{benefits_html}</ul>'
        f'<a href="{url}" class="hb-cta-card__btn" rel="sponsored nofollow noopener">{btn} →</a>'
        f'<p class="hb-cta-card__disc">※本リンク経由の申込で運営者に紹介料が発生します</p>'
        f'</div>'
        f'</aside>'
    )


def cta_inline(brand_key: str, anchor_text: str) -> str:
    img = BRAND_IMAGES[brand_key]
    url = BRAND_URLS[brand_key]
    return (
        f'<a class="hb-cta-inline" href="{url}" rel="sponsored nofollow noopener">'
        f'<img src="{img}" alt="" loading="lazy">{anchor_text} →</a>'
    )


def cta_bottom(brand_key: str, brand_name: str, title: str, quote: str, benefits: list, btn: str) -> str:
    img = BRAND_IMAGES[brand_key]
    url = BRAND_URLS[brand_key]
    benefits_html = "".join(f"<li>{b}</li>" for b in benefits)
    return (
        f'<aside class="hb-cta-v2 hb-cta-bottom">'
        f'<div class="hb-cta-bottom__top">'
        f'<img src="{img}" alt="{brand_name}" loading="lazy">'
        f'<span class="hb-cta-bottom__brandname">{brand_name}</span>'
        f'</div>'
        f'<h3 class="hb-cta-bottom__title">{title}</h3>'
        f'<p class="hb-cta-bottom__quote">{quote}</p>'
        f'<ul class="hb-cta-bottom__benefits">{benefits_html}</ul>'
        f'<a href="{url}" class="hb-cta-bottom__btn" rel="sponsored nofollow noopener">{btn} →</a>'
        f'<p class="hb-cta-bottom__disc">※本記事には広告が含まれます。本リンク経由の申込で運営者に紹介料が発生します。</p>'
        f'</aside>'
    )


# ── プリセット（5アフィ × タイプ別） ──
PRESETS = {
    "DMM_KABU": {
        "hero": dict(label="新NISA口座", title="DMM株：手数料0円・スマホ完結のNISA口座", desc="国内株売買手数料0円、米国株も対応。新NISA成長投資枠OK。", btn="DMM株で口座開設"),
        "card": dict(label="新NISA口座", title="DMM株なら国内株の手数料0円", desc="シンプルなアプリ操作で、初めての証券口座にも安心。", benefits=["国内株 売買手数料：0円", "米国株も取り扱い", "新NISA成長投資枠対応"], btn="DMM株で口座開設"),
        "inline": dict(anchor_text="DMM株（手数料0円NISA）"),
        "bottom": dict(brand_name="DMM 株", title="完済後のNISA口座、もう決めてある", quote="俺は完済まであと1年。完済したら DMM株でNISA口座を開く。手数料0円・スマホ完結・新NISA対応で「初めての投資」を始めるには十分。", benefits=["手数料0円", "新NISA対応", "米国株もOK", "スマホ完結"], btn="DMM株で無料口座開設"),
    },
    "KASHIKINE_NEXUS": {
        "hero": dict(label="クレカ作れない時の選択肢", title="Nexus Card：審査に不安があっても持てる", desc="任意整理中・債務整理経験ありでもサブスクのクレカ枠が埋められる。", btn="Nexus Cardの詳細を見る"),
        "card": dict(label="ブラックでも持てる", title="任意整理中の俺が選んだ Nexus Card", desc="デポジット型なので一般カード審査が通らない人でも持てる。", benefits=["デポジット型で審査ハードル低", "VISA加盟店で利用可", "サブスク・ネット決済OK"], btn="Nexus Card 申込"),
        "inline": dict(anchor_text="Nexus Card（審査不安でも持てる）"),
        "bottom": dict(brand_name="Nexus Card", title="クレカ無しで生きていけない時代の生存戦略", quote="任意整理開始から半年、サブスク全部解約は無理だった。Netflix、ChatGPT Plus、ドメイン更新…クレカ枠は要る。Nexus Card のデポジット型で必要最低限を埋めてる。", benefits=["デポジット型", "VISA加盟店OK", "ブラックOK", "年会費抑えめ"], btn="Nexus Card を申し込む"),
    },
    "BENGOSHI_ABIES": {
        "hero": dict(label="無料相談", title="アビエス法律事務所：債務整理に強い王道の1社", desc="任意整理・個人再生・自己破産まで幅広く対応。相談無料・契約しなくてもOK。", btn="アビエス法律事務所で無料相談"),
        "card": dict(label="無料相談", title="借金の悩み、まず弁護士に話してみる", desc="俺も任意整理を決断する前、3社に相談しました。比較してから決めるのが正解。", benefits=["相談料0円", "契約しなくてOK", "Webから24時間予約可"], btn="アビエスで無料相談"),
        "inline": dict(anchor_text="アビエス法律事務所（無料相談）"),
        "bottom": dict(brand_name="弁護士法人 アビエス法律事務所", title="借金、もう一人で抱えなくていい", quote="俺は任意整理を始める時、3社の弁護士事務所に相談した。1社目で結論を出さなかったから、自分の状況に合う方針が見えた。1人で悩むより、まず無料相談だけでも踏み出してほしい。", benefits=["相談料 0円", "契約義務なし", "債務整理 実績豊富", "Web24時間予約"], btn="無料相談を予約する"),
    },
    "COCONALA": {
        "hero": dict(label="副業 / スキル販売", title="ココナラ：500円から自分のスキルを売れる", desc="登録無料・出品手数料なし。話を聞く・相談・代行など幅広く出品可能。", btn="ココナラに無料登録"),
        "card": dict(label="副業の第一歩", title="俺も副業挑戦中：ココナラで月1万を狙う", desc="完済前に副業収入を作りたい人向け。スキル無くても出品から始められる。", benefits=["登録・出品料 0円", "500円から値付けOK", "会員400万人超のマーケット"], btn="ココナラに無料登録"),
        "inline": dict(anchor_text="ココナラ（副業マーケット）"),
        "bottom": dict(brand_name="ココナラ", title="完済後を見据えた、もう1本の収入源", quote="任意整理中、本業給与だけだと完済までの心が折れる。月1〜3万でも副業収入があると気持ちが違う。ココナラなら登録無料・売れなくてもノーリスク。話を聞くだけのサービスでも売れてる人がいる世界。", benefits=["登録無料", "出品手数料0円", "500円から", "会員400万超"], btn="ココナラに無料登録"),
    },
    "LIGHT_FX": {
        "hero": dict(label="FX（投機注意）", title="LIGHT FX：FXの基礎を少額で勉強したい人へ", desc="※元本損失リスクあり。借金返済中の起死回生狙いには絶対NG。為替の仕組み学習用。", btn="LIGHT FX 公式サイトを見る"),
        "card": dict(label="FX 学習用 (リスク注意)", title="LIGHT FX：少額から為替を体験する", desc="※元本損失リスク高い投機。借金返済中の人は基本NGだが、為替の仕組みを学ぶには使える。", benefits=["少額からスタート可能", "高機能取引ツール", "スワップ高水準"], btn="LIGHT FX 詳細を見る"),
        "inline": dict(anchor_text="LIGHT FX（投機注意）"),
        "bottom": dict(brand_name="LIGHT FX", title="FXは「起死回生」じゃなく「学習」で触る", quote="ガチャと同じで、FXに「これで一発逆転」を期待した瞬間に終わる。俺は借金返済中はFXに触らない。完済後、為替の仕組みを学ぶ目的で少額触るかも、という距離感。", benefits=["少額OK", "学習用", "スワップ高め", "国内大手"], btn="LIGHT FX 公式サイト"),
    },
}


def make_cta(brand_key: str, layout: str) -> str:
    """指定ブランド・レイアウトのCTA HTMLを返す。layout: hero / card / inline / bottom"""
    cfg = PRESETS[brand_key][layout]
    if layout == "hero":
        return cta_hero(brand_key, **cfg)
    if layout == "card":
        return cta_card(brand_key, **cfg)
    if layout == "inline":
        return cta_inline(brand_key, **cfg)
    if layout == "bottom":
        return cta_bottom(brand_key, **cfg)
    raise ValueError(layout)
