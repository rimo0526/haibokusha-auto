"""画像付きCTA 4タイプ テンプレート定義 (TPO別) - インラインstyle版."""

BRAND_IMAGES = {
    "DMM_KABU":         "https://kabu.dmm.com/_img/og/common_230120.png",
    "KASHIKINE_NEXUS":  "https://apply.mycredit.nexuscard.co.jp/lp/common/images/apple-touch-icon.png",
    "BENGOSHI_ABIES":   "https://www.abies-law.jp/img/img/co_favicon.webp",
    "COCONALA":         "https://coconala.com/images/facebook.png",
    "LIGHT_FX":         "https://lightfx.jp/images/social/facebook.jpg",
}

BRAND_URLS = {
    "DMM_KABU":         "https://px.a8.net/svt/ejp?a8mat=4B3LMU+759KY+1WP2+15QHIA",
    "KASHIKINE_NEXUS":  "https://px.a8.net/svt/ejp?a8mat=45G6PM+9ZLVPE+4T5W+5YJRM",
    "BENGOSHI_ABIES":   "https://px.a8.net/svt/ejp?a8mat=45G91P+893D6Q+5SXY+5YJRM",
    "COCONALA":         "https://px.a8.net/svt/ejp?a8mat=4B3LMU+18NKOY+2PEO+OECDE",
    "LIGHT_FX":         "https://px.a8.net/svt/ejp?a8mat=3BDWT8+FDP656+46VO+5YJRM",
}

S = {
    "wrap":   "display:block;margin:32px 0;border-radius:12px;overflow:hidden;font-family:-apple-system,BlinkMacSystemFont,Hiragino Kaku Gothic ProN,Meiryo,sans-serif;line-height:1.7;box-sizing:border-box;",
    "hero":          "background:linear-gradient(135deg,#1E3A5F 0%,#2C5078 100%);color:#fff;padding:0;box-shadow:0 4px 16px rgba(30,58,95,.25);",
    "hero_inner":    "display:flex;align-items:stretch;flex-wrap:wrap;",
    "hero_img":      "flex:1 1 200px;background:#fff;padding:18px;display:flex;align-items:center;justify-content:center;min-height:140px;",
    "hero_img_im":   "max-width:100%;max-height:140px;height:auto;object-fit:contain;",
    "hero_body":     "flex:2 1 300px;padding:20px 24px;color:#fff;",
    "hero_label":    "display:inline-block;background:#FBC97A;color:#1E3A5F;font-weight:700;font-size:12px;padding:3px 10px;border-radius:4px;margin-bottom:8px;",
    "hero_title":    "font-size:18px;font-weight:700;margin:0 0 8px;color:#fff;line-height:1.4;",
    "hero_desc":     "font-size:14px;margin:0 0 14px;color:#E8EFF7;",
    "hero_btn":      "display:inline-block;background:#C56A4E;color:#fff;font-weight:700;padding:10px 22px;border-radius:6px;font-size:15px;text-decoration:none;",
    "card":          "background:#fff;border:1px solid #DDE3EC;box-shadow:0 2px 8px rgba(0,0,0,.06);",
    "card_imgwrap":  "width:100%;background:#F7F3EC;padding:20px;text-align:center;",
    "card_imgwrap_im":"max-width:60%;max-height:90px;height:auto;",
    "card_body":     "padding:18px 22px;",
    "card_label":    "display:inline-block;background:#1E3A5F;color:#fff;font-size:11px;font-weight:700;padding:3px 8px;border-radius:4px;margin-bottom:6px;",
    "card_title":    "font-size:17px;font-weight:700;margin:0 0 8px;color:#1E3A5F;line-height:1.4;",
    "card_desc":     "font-size:14px;margin:0 0 12px;color:#444;",
    "card_btn":      "display:block;background:#C56A4E;color:#fff;font-weight:700;text-align:center;padding:12px 16px;border-radius:6px;font-size:15px;text-decoration:none;",
    "card_disc":     "font-size:11px;color:#888;margin:8px 0 0;text-align:center;",
    "bottom":        "background:#F7F3EC;border:2px solid #C56A4E;padding:24px;text-align:center;",
    "bottom_top":    "display:flex;align-items:center;justify-content:center;gap:14px;margin-bottom:16px;flex-wrap:wrap;",
    "bottom_top_im": "width:80px;height:80px;object-fit:contain;background:#fff;border-radius:8px;padding:6px;border:1px solid #DDE3EC;",
    "bottom_brand":  "font-size:13px;font-weight:700;color:#666;letter-spacing:1px;",
    "bottom_title":  "font-size:22px;font-weight:800;color:#1E3A5F;margin:0 0 12px;line-height:1.4;",
    "bottom_quote":  "font-size:14px;color:#444;background:#fff;padding:14px 18px;border-left:4px solid #C56A4E;text-align:left;margin:0 0 16px;border-radius:4px;",
    "bottom_btn":    "display:inline-block;background:linear-gradient(135deg,#C56A4E 0%,#E08263 100%);color:#fff;font-weight:800;padding:14px 32px;border-radius:8px;font-size:17px;box-shadow:0 4px 12px rgba(197,106,78,.3);text-decoration:none;",
    "bottom_disc":   "font-size:11px;color:#888;margin:14px 0 0;",
    "ul":            "list-style:none;padding:0;margin:0 0 14px;",
    "li":            "padding:3px 0 3px 22px;font-size:13px;color:#1E3A5F;position:relative;",
}


def cta_hero(brand_key, label, title, desc, btn):
    img = BRAND_IMAGES[brand_key]
    url = BRAND_URLS[brand_key]
    return (
        f'<div class="hb-cta-v2 hb-cta-hero" style="{S["wrap"]}{S["hero"]}">'
        f'<div style="{S["hero_inner"]}">'
        f'<div style="{S["hero_img"]}"><img src="{img}" alt="{title}" style="{S["hero_img_im"]}" loading="lazy"></div>'
        f'<div style="{S["hero_body"]}">'
        f'<span style="{S["hero_label"]}">{label}</span>'
        f'<h3 style="{S["hero_title"]}">{title}</h3>'
        f'<p style="{S["hero_desc"]}">{desc}</p>'
        f'<a href="{url}" style="{S["hero_btn"]}" rel="sponsored nofollow noopener">{btn} →</a>'
        f'</div></div></div>'
    )


def cta_card(brand_key, label, title, desc, benefits, btn):
    img = BRAND_IMAGES[brand_key]
    url = BRAND_URLS[brand_key]
    items = "".join(f'<li style="{S["li"]}">✓ {b}</li>' for b in benefits)
    return (
        f'<div class="hb-cta-v2 hb-cta-card" style="{S["wrap"]}{S["card"]}">'
        f'<div style="{S["card_imgwrap"]}"><img src="{img}" alt="{title}" style="{S["card_imgwrap_im"]}" loading="lazy"></div>'
        f'<div style="{S["card_body"]}">'
        f'<span style="{S["card_label"]}">{label}</span>'
        f'<h3 style="{S["card_title"]}">{title}</h3>'
        f'<p style="{S["card_desc"]}">{desc}</p>'
        f'<ul style="{S["ul"]}">{items}</ul>'
        f'<a href="{url}" style="{S["card_btn"]}" rel="sponsored nofollow noopener">{btn} →</a>'
        f'<p style="{S["card_disc"]}">※本リンク経由の申込で運営者に紹介料が発生します</p>'
        f'</div></div>'
    )


def cta_inline(brand_key, anchor_text):
    img = BRAND_IMAGES[brand_key]
    url = BRAND_URLS[brand_key]
    return (
        f'<a class="hb-cta-v2 hb-cta-inline" href="{url}" rel="sponsored nofollow noopener" '
        f'style="display:inline-flex;align-items:center;gap:6px;background:#FFF8E7;padding:4px 10px;border-radius:4px;border-bottom:2px solid #FBC97A;font-weight:600;color:#1E3A5F;text-decoration:none;">'
        f'<img src="{img}" alt="" style="width:18px;height:18px;border-radius:3px;object-fit:contain;background:#fff;padding:1px;" loading="lazy">{anchor_text} →</a>'
    )


def cta_bottom(brand_key, brand_name, title, quote, benefits, btn):
    img = BRAND_IMAGES[brand_key]
    url = BRAND_URLS[brand_key]
    items = "".join(f'<li style="background:#fff;border:1px solid #DDE3EC;border-radius:20px;padding:6px 14px;font-size:13px;color:#1E3A5F;font-weight:600;display:inline-block;margin:0 4px 4px 0;">{b}</li>' for b in benefits)
    return (
        f'<div class="hb-cta-v2 hb-cta-bottom" style="{S["wrap"]}{S["bottom"]}">'
        f'<div style="{S["bottom_top"]}">'
        f'<img src="{img}" alt="{brand_name}" style="{S["bottom_top_im"]}" loading="lazy">'
        f'<span style="{S["bottom_brand"]}">{brand_name}</span>'
        f'</div>'
        f'<h3 style="{S["bottom_title"]}">{title}</h3>'
        f'<p style="{S["bottom_quote"]}">{quote}</p>'
        f'<ul style="list-style:none;padding:0;margin:0 0 18px;">{items}</ul>'
        f'<a href="{url}" style="{S["bottom_btn"]}" rel="sponsored nofollow noopener">{btn} →</a>'
        f'<p style="{S["bottom_disc"]}">※本記事には広告が含まれます。本リンク経由の申込で運営者に紹介料が発生します。</p>'
        f'</div>'
    )


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
        "card": dict(label="FX 学習用", title="LIGHT FX：少額から為替を体験する", desc="※元本損失リスク高い投機。借金返済中の人は基本NGだが、為替の仕組みを学ぶには使える。", benefits=["少額からスタート可能", "高機能取引ツール", "スワップ高水準"], btn="LIGHT FX 詳細を見る"),
        "inline": dict(anchor_text="LIGHT FX（投機注意）"),
        "bottom": dict(brand_name="LIGHT FX", title="FXは「起死回生」じゃなく「学習」で触る", quote="ガチャと同じで、FXに「これで一発逆転」を期待した瞬間に終わる。俺は借金返済中はFXに触らない。完済後、為替の仕組みを学ぶ目的で少額触るかも、という距離感。", benefits=["少額OK", "学習用", "スワップ高め", "国内大手"], btn="LIGHT FX 公式サイト"),
    },
}


def make_cta(brand_key, layout):
    cfg = PRESETS[brand_key][layout]
    if layout == "hero":   return cta_hero(brand_key, **cfg)
    if layout == "card":   return cta_card(brand_key, **cfg)
    if layout == "inline": return cta_inline(brand_key, **cfg)
    if layout == "bottom": return cta_bottom(brand_key, **cfg)
    raise ValueError(layout)


CTA_STYLE_BLOCK = ""
