"""敗北者記事へのCTAボックス挿入モジュール。

設計：
  - 記事のカテゴリ・キーワードから適切なCTA案件を選択
  - 中盤H2・末尾H2 直後にCTAボックスを挿入（idempotent: 既挿入はスキップ）
  - placeholder URL（#REPLACE_*）使用、ASP提携承認後に sed で一括置換可能

CTA配置ルール：
  - H2 が3つ未満の記事はCTA末尾1個のみ
  - H2 が3つ以上：中盤（H2 #(N//2)) + 末尾 で2個
  - H2 が5つ以上：冒頭 + 中盤 + 末尾 で3個

使用：
  from inject_ctas import inject_ctas
  new_html = inject_ctas(html, categories=["Money", "Mental"], slug="2026-05-09-kakeibo-truth")
"""

import re
from typing import List


# ── CTAテンプレ定義 ────────────────────────────────
# 各CTAは独立HTMLスニペット。CSSは記事冒頭で1度だけ定義する想定。

CTA_BENGOSHI_PRIMARY = """
<div class="hb-cta-box hb-cta-primary">
  <span class="hb-cta-label">無料相談</span>
  <h3 class="hb-cta-title">借金の悩み、まず弁護士に「無料相談」だけしてみる</h3>
  <p class="hb-cta-desc">俺も任意整理を決断する前、3社の弁護士事務所に相談しました。1社目で結論を出さず、複数比較したから自分の状況に合う方針が見えました。</p>
  <ul class="hb-cta-bullets">
    <li>相談は無料、契約しなくてもOK</li>
    <li>24時間Webから予約可能</li>
    <li>債務整理の経験豊富な事務所</li>
  </ul>
  <a href="#REPLACE_BENGOSHI_ADIRE_URL" class="hb-cta-btn" rel="sponsored nofollow noopener">公式サイトで無料相談を予約 →</a>
  <small class="hb-cta-disclosure">※ 本リンク経由のお申込みで運営者に紹介料が発生します</small>
</div>
""".strip()

CTA_DMM_KABU = """
<div class="hb-cta-box">
  <span class="hb-cta-label">NISA口座</span>
  <h3 class="hb-cta-title">楽天証券で新NISA口座を開設（無料）</h3>
  <p class="hb-cta-desc">俺自身、楽天証券で新NISA口座を持っています。楽天ポイントで投信が買える、楽天カード積立で1%還元、UI シンプルの3点が決め手でした。</p>
  <ul class="hb-cta-bullets">
    <li>口座開設＆維持費用：0円</li>
    <li>楽天ポイントで投信積立可能</li>
    <li>NISAつみたて投資枠で月100円から</li>
  </ul>
  <a href="#REPLACE_RAKUTEN_SHOKEN_URL" class="hb-cta-btn" rel="sponsored nofollow noopener">楽天証券で口座開設 →</a>
  <small class="hb-cta-disclosure">※ 本リンク経由のお申込みで運営者に紹介料が発生します</small>
</div>
""".strip()

CTA_SBI_SHOKEN = """
<div class="hb-cta-box">
  <span class="hb-cta-label">NISA口座</span>
  <h3 class="hb-cta-title">SBI証券：低コスト投資の本格派</h3>
  <p class="hb-cta-desc">NISA口座を真剣に運用したい人向け。手数料の安さ、取扱商品の多さ、三井住友カード積立でのポイント還元が強み。</p>
  <a href="#REPLACE_SBI_SHOKEN_URL" class="hb-cta-btn" rel="sponsored nofollow noopener">SBI証券で口座開設 →</a>
  <small class="hb-cta-disclosure">※ 本リンク経由のお申込みで運営者に紹介料が発生します</small>
</div>
""".strip()

CTA_NEXUS_CARD = """
<div class="hb-cta-box">
  <span class="hb-cta-label">デビカ</span>
  <h3 class="hb-cta-title">楽天銀行デビット VISA：俺のメインカード</h3>
  <p class="hb-cta-desc">任意整理中だとクレカが作れない。サブスクやネットショッピングは必要。そんな俺がたどり着いた1枚。年会費無料、楽天ポイント還元、VISA加盟店で使えます。</p>
  <a href="#REPLACE_RAKUTEN_DEBIT_URL" class="hb-cta-btn" rel="sponsored nofollow noopener">楽天銀行デビットの詳細を見る →</a>
  <small class="hb-cta-disclosure">※ 本リンク経由のお申込みで運営者に紹介料が発生します</small>
</div>
""".strip()

CTA_COCONALA = """
<div class="hb-cta-box">
  <span class="hb-cta-label">家計簿アプリ</span>
  <h3 class="hb-cta-title">マネーフォワードMEで家計を見える化</h3>
  <p class="hb-cta-desc">俺の家計簿は、紙→Excel→マネフォの順で進化しました。複数の銀行・カード・証券を自動連携して「使ったお金を後から記入する」手間が消えます。</p>
  <a href="#REPLACE_MFW_URL" class="hb-cta-btn" rel="sponsored nofollow noopener">マネーフォワードMEを使う →</a>
  <small class="hb-cta-disclosure">※ 本リンク経由のお申込みで運営者に紹介料が発生します</small>
</div>
""".strip()

CTA_STUDYING = """
<div class="hb-cta-box">
  <span class="hb-cta-label">資格学校</span>
  <h3 class="hb-cta-title">通信スクールで資格学習を効率化</h3>
  <p class="hb-cta-desc">独学が続かないなら、通信スクールが一番コスパが良い。俺も家計に余裕ができたら簿記2級か宅建を狙ってます。スマホ完結のスタディングなら月2,000〜5,000円から。</p>
  <a href="#REPLACE_STUDYING_URL" class="hb-cta-btn" rel="sponsored nofollow noopener">無料お試しを見る →</a>
  <small class="hb-cta-disclosure">※ 本リンク経由のお申込みで運営者に紹介料が発生します</small>
</div>
""".strip()

CTA_AMAZON_BOOKS = """
<div class="hb-cta-box">
  <span class="hb-cta-label">参考書籍</span>
  <h3 class="hb-cta-title">この記事を書く時に参考にした本</h3>
  <p class="hb-cta-desc">借金返済・お金の整え方をテーマに、俺が読んで参考にした書籍。Kindle Unlimited 対象本も多いので無料体験中に読むのもアリ。</p>
  <a href="#REPLACE_AMAZON_BOOK_URL" class="hb-cta-btn" rel="sponsored nofollow noopener">Amazon で見る →</a>
  <small class="hb-cta-disclosure">※ Amazonアソシエイトプログラム参加。リンク経由のご購入で運営者に紹介料が発生します</small>
</div>
""".strip()

CTA_DMM_KABU = """
<div class="hb-cta-box">
  <span class="hb-cta-label">NISA口座</span>
  <h3 class="hb-cta-title">DMM株：手数料0円・初心者にも分かりやすい</h3>
  <p class="hb-cta-desc">国内株式の取引手数料が0円。スマホアプリのUIがシンプルで、NISAも対応。「証券口座は怖い」と感じる初心者にもとっつきやすい1社です。</p>
  <ul class="hb-cta-bullets">
    <li>国内株 売買手数料：0円</li>
    <li>米国株も取り扱いあり（為替手数料無料キャンペーンあり）</li>
    <li>新NISA対応（成長投資枠）</li>
  </ul>
  <a href="#REPLACE_DMM_KABU_URL" class="hb-cta-btn" rel="sponsored nofollow noopener">DMM株で口座開設 →</a>
  <small class="hb-cta-disclosure">※ 本リンク経由のお申込みで運営者に紹介料が発生します</small>
</div>
""".strip()

# ── 弁護士・司法書士（5件） ─────────────────────────────
# 用途：bengoshi比較記事 / 任意整理関連記事
# 注意：YMYL × 弁護士法72条の遵守 → 「無料相談だけでもOK」を強調、特定方針の押し付けNG

CTA_BENGOSHI_ABIES = """
<div class="hb-cta-box hb-cta-primary">
  <span class="hb-cta-label">無料相談</span>
  <h3 class="hb-cta-title">アビエス法律事務所：債務整理に強い王道の1社</h3>
  <p class="hb-cta-desc">借金問題に注力する法律事務所。任意整理・個人再生・自己破産まで幅広く対応。相談は無料で、契約しなくてもOK。「いきなり弁護士に頼む勇気がない」状態の人がまず動き出す一歩として最適。</p>
  <ul class="hb-cta-bullets">
    <li>相談料 0円・契約しなくてもOK</li>
    <li>債務整理の取扱い実績豊富</li>
    <li>Web から24時間予約可能</li>
  </ul>
  <a href="#REPLACE_BENGOSHI_ABIES_URL" class="hb-cta-btn" rel="sponsored nofollow noopener">アビエス法律事務所で無料相談 →</a>
  <small class="hb-cta-disclosure">※ 本リンク経由のお申込みで運営者に紹介料が発生します</small>
</div>
""".strip()

CTA_BENGOSHI_SAKURA = """
<div class="hb-cta-box">
  <span class="hb-cta-label">無料相談</span>
  <h3 class="hb-cta-title">さくら中央法律事務所：丁寧なヒアリングで方針提案</h3>
  <p class="hb-cta-desc">「複数事務所に話を聞いて納得して決めたい」人向けの選択肢。任意整理・過払い金・個人再生など債務整理メインに対応。1社目で結論を出さず比較するのが、後悔しないコツです。</p>
  <a href="#REPLACE_BENGOSHI_SAKURA_URL" class="hb-cta-btn" rel="sponsored nofollow noopener">さくら中央法律事務所で無料相談 →</a>
  <small class="hb-cta-disclosure">※ 本リンク経由のお申込みで運営者に紹介料が発生します</small>
</div>
""".strip()

CTA_BENGOSHI_HIRAYANAGI = """
<div class="hb-cta-box">
  <span class="hb-cta-label">司法書士</span>
  <h3 class="hb-cta-title">平柳司法書士事務所：費用を抑えたい人の選択肢</h3>
  <p class="hb-cta-desc">司法書士は1社あたりの債務が140万円以下の任意整理に対応可能。費用が弁護士より抑えめなことが多い。「弁護士費用が払えるか不安」という人は司法書士から検討してみるのもアリ。</p>
  <ul class="hb-cta-bullets">
    <li>1社あたりの債務 140万円以下なら司法書士で対応可</li>
    <li>弁護士事務所より費用が抑えめになるケースが多い</li>
  </ul>
  <a href="#REPLACE_BENGOSHI_HIRAYANAGI_URL" class="hb-cta-btn" rel="sponsored nofollow noopener">平柳司法書士事務所で無料相談 →</a>
  <small class="hb-cta-disclosure">※ 本リンク経由のお申込みで運営者に紹介料が発生します</small>
</div>
""".strip()

CTA_BENGOSHI_KOUKAI = """
<div class="hb-cta-box">
  <span class="hb-cta-label">任意整理</span>
  <h3 class="hb-cta-title">後悔しない任意整理：まず情報収集から</h3>
  <p class="hb-cta-desc">「契約まで決めるのは怖い」「どこに相談すればいいか分からない」という段階の人向け。任意整理の選び方・費用相場・流れを把握してから動けるサービスです。</p>
  <a href="#REPLACE_BENGOSHI_KOUKAI_URL" class="hb-cta-btn" rel="sponsored nofollow noopener">任意整理の情報を見る →</a>
  <small class="hb-cta-disclosure">※ 本リンク経由のお申込みで運営者に紹介料が発生します</small>
</div>
""".strip()

CTA_BENGOSHI_LADIES = """
<div class="hb-cta-box">
  <span class="hb-cta-label">女性向け</span>
  <h3 class="hb-cta-title">レディースフタバ：女性スタッフ対応の債務整理</h3>
  <p class="hb-cta-desc">「男性弁護士に借金の話を切り出すのは正直キツい」と感じる女性向け。女性スタッフが相談を受け付ける窓口があるので、心理的ハードルを下げて第一歩が踏み出しやすい。</p>
  <a href="#REPLACE_BENGOSHI_LADIES_URL" class="hb-cta-btn" rel="sponsored nofollow noopener">レディースフタバで無料相談 →</a>
  <small class="hb-cta-disclosure">※ 本リンク経由のお申込みで運営者に紹介料が発生します</small>
</div>
""".strip()

# ── デビカ／キャッシング（注意喚起付き） ─────────────────
# 重要：キャッシング系は「最後の手段」「まず弁護士相談を優先」「借金ループに陥らないため計画的に」を必ず併記
# 違法な勧誘にならないよう、債務整理経験者ペルソナ（敗北者）の視点で「失敗から学んでほしい」トーンで書く

CTA_NEXUS_CARD = """
<div class="hb-cta-box">
  <span class="hb-cta-label">クレカ作れない時の選択肢</span>
  <h3 class="hb-cta-title">Nexus Card：審査に不安がある人向けカード</h3>
  <p class="hb-cta-desc">任意整理中・債務整理経験ありで、新規クレカ審査が通らない人向けの選択肢。デポジット型なので一般カードより審査ハードルが下がります。サブスク・ネット決済用として、楽天デビットと並列で持つと安心。</p>
  <ul class="hb-cta-bullets">
    <li>デポジット型（事前入金）でクレカが持てる</li>
    <li>VISA加盟店で利用可能</li>
    <li>サブスク・ネット決済の "クレカ枠" を埋められる</li>
  </ul>
  <a href="#REPLACE_KASHIKINE_NEXUS_URL" class="hb-cta-btn" rel="sponsored nofollow noopener">Nexus Card の詳細を見る →</a>
  <small class="hb-cta-disclosure">※ 本リンク経由のお申込みで運営者に紹介料が発生します</small>
</div>
""".strip()

CTA_KASHIKINE_WARN_WRAPPER = """
<div class="hb-cta-box">
  <span class="hb-cta-label">⚠ 最後の手段</span>
  <h3 class="hb-cta-title">借入は「最後の手段」です。まず弁護士の無料相談を</h3>
  <p class="hb-cta-desc">俺自身、ガチャと消費者金融の借金で多重債務になり、最終的に任意整理に追い込まれました。<strong>新しい借入で目の前の問題を先送りにすると、雪だるま式に悪化します</strong>。やむを得ず借入を検討する前に、必ず弁護士・司法書士の無料相談を受けてください。借りる場合も、年収の3分の1までを上限に、計画的に。</p>
  <a href="#REPLACE_BENGOSHI_ABIES_URL" class="hb-cta-btn" rel="sponsored nofollow noopener">まず弁護士に無料相談する →</a>
  <small class="hb-cta-disclosure">※ 借入は計画的に。完済できる見込みがない借入はおすすめしません。</small>
</div>
""".strip()

# ── FX・暗号通貨（投資中級者向け、リスク注意喚起必須） ───
# 敗北者ペルソナでは原則「インデックス積立」推奨。FX/暗号は "投機の罠" 文脈で扱う

CTA_LIGHT_FX = """
<div class="hb-cta-box">
  <span class="hb-cta-label">FX（投機注意）</span>
  <h3 class="hb-cta-title">LIGHT FX：FXに興味がある人向けの基礎情報</h3>
  <p class="hb-cta-desc"><strong>※FXは元本を上回る損失リスクがある投機性の高い取引です。</strong>俺は基本的にインデックス積立を推奨していますが、「為替の仕組みを実際に体験する勉強用」として少額で触る人もいます。FXに踏み込む前に、必ずリスクを完全理解してください。借金返済中の人が "起死回生" を狙う使い方は絶対にNGです。</p>
  <a href="#REPLACE_LIGHT_FX_URL" class="hb-cta-btn" rel="sponsored nofollow noopener">LIGHT FX の公式サイトを見る →</a>
  <small class="hb-cta-disclosure">※ FX取引は元本割れのリスクが高い投機です。借金返済の手段として用いるべきではありません。本リンク経由のお申込みで運営者に紹介料が発生します。</small>
</div>
""".strip()

CTA_GMO_COIN = """
<div class="hb-cta-box">
  <span class="hb-cta-label">暗号資産（投機注意）</span>
  <h3 class="hb-cta-title">GMOコイン：暗号資産取引所の選択肢</h3>
  <p class="hb-cta-desc"><strong>※暗号資産は価格変動が激しく、元本割れリスクが大きい投機商品です。</strong>俺自身は基本的にインデックス積立を中核に据えていますが、ポートフォリオの "サテライト" として小額（資産の5%以下）暗号資産を持つ人もいます。借金返済中の人にとっては基本的に推奨しません。</p>
  <a href="#REPLACE_GMO_COIN_URL" class="hb-cta-btn" rel="sponsored nofollow noopener">GMOコインの公式サイトを見る →</a>
  <small class="hb-cta-disclosure">※ 暗号資産は価格変動リスクが大きい投機商品です。本リンク経由のお申込みで運営者に紹介料が発生します。</small>
</div>
""".strip()

# ── 保険 ─────────────────────────────────────────
CTA_HOKEN_BANG = """
<div class="hb-cta-box">
  <span class="hb-cta-label">保険見直し</span>
  <h3 class="hb-cta-title">保険スクエアbang!：固定費削減で家計改善</h3>
  <p class="hb-cta-desc">借金返済中の家計改善は「固定費」から。保険料は月数千円〜数万円の固定費で、見直しの余地が大きい代表項目。複数社の見積もりを一括で比較できるので、「今の保険が高すぎないか」を1回チェックする価値はあります。</p>
  <ul class="hb-cta-bullets">
    <li>複数社の見積もりを無料で一括比較</li>
    <li>FP相談も可能</li>
    <li>月数千円の節約で年間数万円の家計改善になることも</li>
  </ul>
  <a href="#REPLACE_HOKEN_BANG_URL" class="hb-cta-btn" rel="sponsored nofollow noopener">保険スクエアbang!で一括見積もり →</a>
  <small class="hb-cta-disclosure">※ 本リンク経由のお申込みで運営者に紹介料が発生します</small>
</div>
""".strip()

# ── 弁護士・司法書士（追加：アース） ─────────────
CTA_BENGOSHI_EARTH = """
<div class="hb-cta-box">
  <span class="hb-cta-label">司法書士</span>
  <h3 class="hb-cta-title">アース司法書士事務所：相談無料の任意整理対応</h3>
  <p class="hb-cta-desc">司法書士事務所の選択肢の1つ。1社あたりの債務が140万円以下なら司法書士で対応可能で、弁護士事務所より費用が抑えめになる場合があります。複数事務所を比較する候補に。</p>
  <a href="#REPLACE_BENGOSHI_EARTH_URL" class="hb-cta-btn" rel="sponsored nofollow noopener">アース司法書士事務所で無料相談 →</a>
  <small class="hb-cta-disclosure">※ 本リンク経由のお申込みで運営者に紹介料が発生します</small>
</div>
""".strip()

# ── ウェブサービス・スキルマーケット ──────────────
CTA_COCONALA = """
<div class="hb-cta-box">
  <span class="hb-cta-label">副業 / スキル販売</span>
  <h3 class="hb-cta-title">ココナラ：自分のスキルを500円から売れる</h3>
  <p class="hb-cta-desc">「自分には売るスキルなんて無い」と思っている人ほど、ココナラ向き。話を聞く・占い・愚痴聞き・Excel代行・文字起こしまで、本気か冗談か微妙なサービスでも売れている。俺も副業で挑戦中の選択肢の1つ。</p>
  <ul class="hb-cta-bullets">
    <li>登録無料・出品手数料なし</li>
    <li>500円から自分の値付け可能</li>
    <li>会員数 400万人超のスキルマーケット</li>
  </ul>
  <a href="#REPLACE_COCONALA_URL" class="hb-cta-btn" rel="sponsored nofollow noopener">ココナラに登録する →</a>
  <small class="hb-cta-disclosure">※ 本リンク経由のお申込みで運営者に紹介料が発生します</small>
</div>
""".strip()

CTA_ONAMAE = """
<div class="hb-cta-box">
  <span class="hb-cta-label">サイト運営</span>
  <h3 class="hb-cta-title">お名前.com：自分のブログ用ドメインを取得</h3>
  <p class="hb-cta-desc">アフィリエイトやブログを始めるなら、独自ドメインは必須。お名前.com は国内最大級のドメイン登録サービスで、初年度1円〜の格安ドメインも豊富。「副業ブログを始めたい」最初の一歩に。</p>
  <a href="#REPLACE_ONAMAE_URL" class="hb-cta-btn" rel="sponsored nofollow noopener">お名前.com でドメインを探す →</a>
  <small class="hb-cta-disclosure">※ 本リンク経由のお申込みで運営者に紹介料が発生します</small>
</div>
""".strip()

CTA_A8_SELF = """
<div class="hb-cta-box">
  <span class="hb-cta-label">アフィリエイト入門</span>
  <h3 class="hb-cta-title">A8.net：日本最大級のアフィリエイトASP（無料登録）</h3>
  <p class="hb-cta-desc">俺がこのブログでアフィリエイト収益化に使っているのも A8.net。サイトを持ってなくても登録できて、案件と提携してから記事を書くこともできる。「副業でアフィリやってみたい」入口として実用的。</p>
  <a href="#REPLACE_A8_SELF_URL" class="hb-cta-btn" rel="sponsored nofollow noopener">A8.netに無料登録 →</a>
  <small class="hb-cta-disclosure">※ 本リンク経由のお申込みで運営者に紹介料が発生します</small>
</div>
""".strip()

# ── ライフスタイル／ダイエット ────────────────────
CTA_RIZAP = """
<div class="hb-cta-box">
  <span class="hb-cta-label">ダイエット / 自己投資</span>
  <h3 class="hb-cta-title">RIZAP：本気の体型改善を結果コミットで</h3>
  <p class="hb-cta-desc">「お金で痩せる」価値を理解している人向け。完全個別の食事＆トレーニング指導で、結果にコミットする本気のサービスです。</p>
  <a href="#REPLACE_RIZAP_URL" class="hb-cta-btn" rel="sponsored nofollow noopener">RIZAP の無料カウンセリングを予約 →</a>
  <small class="hb-cta-disclosure">※ 本リンク経由のお申込みで運営者に紹介料が発生します</small>
</div>
""".strip()

# ── 書籍・コンテンツ（聴く読書 / 電子書籍） ───────
CTA_AUDIBLE = """
<div class="hb-cta-box">
  <span class="hb-cta-label">学習 / 通勤時間活用</span>
  <h3 class="hb-cta-title">Audible：本を「聴く」習慣で通勤を学習時間に</h3>
  <p class="hb-cta-desc">紙の本が読めない夜、通勤の電車、家事の合間。Audible なら "ながら学習" で月数冊消化できる。30日無料体験で、お金を返済中の俺たちでもリスクなしで試せます。</p>
  <ul class="hb-cta-bullets">
    <li>30日間無料体験あり</li>
    <li>12万冊以上の聴き放題対象</li>
    <li>通勤・家事・寝る前の "余白時間" を学習に変えられる</li>
  </ul>
  <a href="#REPLACE_AUDIBLE_URL" class="hb-cta-btn" rel="sponsored nofollow noopener">Audible 30日無料体験 →</a>
  <small class="hb-cta-disclosure">※ 本リンク経由のお申込みで運営者に紹介料が発生します</small>
</div>
""".strip()

CTA_AUDIOBOOK_JP = """
<div class="hb-cta-box">
  <span class="hb-cta-label">学習 / 通勤時間活用</span>
  <h3 class="hb-cta-title">audiobook.jp：聴き放題プランで月額1,330円〜</h3>
  <p class="hb-cta-desc">日本語のオーディオブック専門。Audible より日本語コンテンツが多く、ビジネス書・自己啓発書の聴き放題プランがあるのが強み。最初の14日無料体験あり。</p>
  <a href="#REPLACE_AUDIOBOOK_JP_URL" class="hb-cta-btn" rel="sponsored nofollow noopener">audiobook.jp の無料体験 →</a>
  <small class="hb-cta-disclosure">※ 本リンク経由のお申込みで運営者に紹介料が発生します</small>
</div>
""".strip()

CTA_DMM_BOOKS = """
<div class="hb-cta-box">
  <span class="hb-cta-label">電子書籍</span>
  <h3 class="hb-cta-title">DMMブックス：金融・自己啓発の電子書籍が安い</h3>
  <p class="hb-cta-desc">電子書籍は紙より2割ほど安いことが多く、セール頻度も高い。お金の本・任意整理関連の本を買うなら、紙にこだわる理由はそこまでありません。</p>
  <a href="#REPLACE_DMM_BOOKS_URL" class="hb-cta-btn" rel="sponsored nofollow noopener">DMMブックスを見る →</a>
  <small class="hb-cta-disclosure">※ 本リンク経由のお申込みで運営者に紹介料が発生します</small>
</div>
""".strip()

# CTA CSSスタイル（記事冒頭に1度だけ挿入）
CTA_CSS = """<style>
.hb-cta-box{margin:28px 0;padding:24px 28px;border-radius:12px;background:#FAF7F2;border:1px solid #E0775E;font-family:-apple-system,"Hiragino Kaku Gothic ProN","Hiragino Sans",sans-serif}
.hb-cta-box.hb-cta-primary{background:linear-gradient(135deg,#1E2A3D 0%,#2C3E5C 100%);color:#FAF7F2;border:none}
.hb-cta-box .hb-cta-label{display:inline-block;background:#E0775E;color:#fff;padding:3px 10px;border-radius:4px;font-size:11px;font-weight:700;letter-spacing:.05em;margin-bottom:10px}
.hb-cta-box .hb-cta-title{font-size:17px;font-weight:700;margin:0 0 8px;color:#1E2A3D}
.hb-cta-box.hb-cta-primary .hb-cta-title{color:#FBC97A}
.hb-cta-box .hb-cta-desc{font-size:14px;line-height:1.7;margin:0 0 14px;color:#4B5563}
.hb-cta-box.hb-cta-primary .hb-cta-desc{color:rgba(255,255,255,.85)}
.hb-cta-box .hb-cta-btn{display:inline-block;padding:12px 28px;background:#E0775E;color:#fff!important;text-decoration:none;font-weight:700;font-size:15px;border-radius:8px;transition:opacity .2s}
.hb-cta-box.hb-cta-primary .hb-cta-btn{background:#FBC97A;color:#1E2A3D!important}
.hb-cta-box .hb-cta-btn:hover{opacity:.85}
.hb-cta-box .hb-cta-disclosure{display:block;margin-top:12px;font-size:11px;color:#9CA3AF}
.hb-cta-box.hb-cta-primary .hb-cta-disclosure{color:rgba(255,255,255,.5)}
.hb-cta-box .hb-cta-bullets{margin:8px 0 14px;padding-left:20px;font-size:13px;color:#4B5563}
.hb-cta-box.hb-cta-primary .hb-cta-bullets{color:rgba(255,255,255,.85)}
.hb-cta-box .hb-cta-bullets li{margin-bottom:4px}
@media(max-width:600px){.hb-cta-box{padding:18px 20px}.hb-cta-box .hb-cta-btn{display:block;text-align:center}}
</style>
""".strip()


# ── キーワード → CTA案件マッピング ────────────────
# 上から順に走査、最初にマッチしたものが優先。
# 1記事に2〜3個のCTAを配置する場合、優先順位上位から選択。

CATEGORY_CTA_PRIMARY = {
    "Money": CTA_BENGOSHI_PRIMARY,
    "money": CTA_BENGOSHI_PRIMARY,
    "お金": CTA_BENGOSHI_PRIMARY,
    "Mental": CTA_BENGOSHI_PRIMARY,
    "Business": CTA_DMM_KABU,
    "business": CTA_DMM_KABU,
    "副業": CTA_DMM_KABU,
    "About": CTA_DMM_KABU,
}

CATEGORY_CTA_SECONDARY = {
    "Money": CTA_NEXUS_CARD,
    "money": CTA_NEXUS_CARD,
    "お金": CTA_NEXUS_CARD,
    "Mental": CTA_AMAZON_BOOKS,
    "Business": CTA_COCONALA,
    "business": CTA_COCONALA,
    "副業": CTA_COCONALA,
}

CATEGORY_CTA_CLOSING = {
    "Money": CTA_COCONALA,
    "money": CTA_COCONALA,
    "お金": CTA_COCONALA,
    "Mental": CTA_DMM_KABU,
    "Business": CTA_STUDYING,
    "business": CTA_STUDYING,
    "副業": CTA_STUDYING,
}


def select_ctas(categories: List[str], slug: str = "") -> tuple:
    """記事のカテゴリ・slug からCTAを選択。
    戻り値: (mid_cta, end_cta, secondary_cta_optional) のタプル
    """
    primary_cat = categories[0] if categories else "Money"
    primary = CATEGORY_CTA_PRIMARY.get(primary_cat, CTA_BENGOSHI_PRIMARY)
    secondary = CATEGORY_CTA_SECONDARY.get(primary_cat, CTA_NEXUS_CARD)
    closing = CATEGORY_CTA_CLOSING.get(primary_cat, CTA_COCONALA)

    # slug ベースの上書き（特定キーワードを含む場合）
    s = slug.lower()
    if "nisa" in s or "shoken" in s or "investment" in s:
        # 2026-05-08: DMM株 のアフィリンク確定。SBI証券は提携待ちのため DMM株 に差替
        primary, secondary, closing = CTA_DMM_KABU, CTA_DMM_KABU, CTA_NEXUS_CARD
    elif "kakeibo" in s or "household" in s:
        primary, secondary, closing = CTA_COCONALA, CTA_BENGOSHI_PRIMARY, CTA_DMM_KABU
    elif "saimu-seiri" in s or "bengoshi" in s or "lawyer" in s:
        primary, secondary, closing = CTA_BENGOSHI_PRIMARY, CTA_NEXUS_CARD, CTA_COCONALA
    elif "debit" in s or "card" in s:
        primary, secondary, closing = CTA_NEXUS_CARD, CTA_BENGOSHI_PRIMARY, CTA_DMM_KABU

    return primary, secondary, closing


# ── HTML 操作 ──────────────────────────────────
H2_RE = re.compile(r"<h2(\s[^>]*)?>(.+?)</h2>", re.DOTALL)


def inject_ctas(html: str, categories: List[str] = None, slug: str = "") -> str:
    """記事HTMLにCTAボックスを挿入する。冪等。

    挿入ロジック：
      1. 既に hb-cta-box を含む場合はスキップ（冪等性）
      2. 記事冒頭に CTA_CSS を挿入（既挿入はスキップ）
      3. H2 数 N に応じて：
         - N < 2: 末尾CTA 1個のみ
         - 2 <= N < 4: H2#(N//2) と末尾の2個
         - N >= 4: H2#1 と H2#(N//2) と末尾の3個

    戻り値: 改変後HTML
    """
    if html is None:
        return html
    categories = categories or ["Money"]

    # 1. 既挿入チェック
    if "hb-cta-box" in html:
        return html

    # 2. CTA選択
    primary, secondary, closing = select_ctas(categories, slug)

    # 3. CSS挿入（先頭）
    if "hb-cta-box{" not in html:
        html = CTA_CSS + "\n\n" + html

    # 4. H2 を全部見つける
    h2_matches = list(H2_RE.finditer(html))
    n = len(h2_matches)

    # 5. 挿入計画
    insertions = []  # list of (offset, content) ：offset 降順で挿入する

    if n == 0:
        # H2なし：末尾に1個
        insertions.append((len(html), "\n\n" + closing + "\n"))
    elif n == 1:
        # H2 1個：末尾に1個（H2直後にすると過剰に目立つ）
        insertions.append((len(html), "\n\n" + closing + "\n"))
    elif n < 4:
        # H2 2〜3個：中央 H2 直後 + 末尾
        mid_idx = n // 2
        mid_h2_end = h2_matches[mid_idx].end()
        # H2タグ末尾の次の段落（</p>または<table>の終わり）の後に挿入したい
        # 簡易：H2タグの直後に挿入（厳密にはH2の本文section末尾が望ましいが、まず実装優先）
        insertions.append((mid_h2_end, "\n\n" + primary + "\n"))
        insertions.append((len(html), "\n\n" + closing + "\n"))
    else:
        # H2 4個以上：1つ目H2の後 + 中央H2の後 + 末尾
        first_h2_end = h2_matches[0].end()
        mid_idx = n // 2
        mid_h2_end = h2_matches[mid_idx].end()
        insertions.append((first_h2_end, "\n\n" + primary + "\n"))
        insertions.append((mid_h2_end, "\n\n" + secondary + "\n"))
        insertions.append((len(html), "\n\n" + closing + "\n"))

    # 6. 挿入実行（オフセット降順で末尾から）
    insertions.sort(key=lambda x: x[0], reverse=True)
    for offset, content in insertions:
        html = html[:offset] + content + html[offset:]

    return html


if __name__ == "__main__":
    sample = """<h2>本文1</h2><p>段落</p>
<h2>本文2</h2><p>段落</p>
<h2>本文3</h2><p>段落</p>
<h2>本文4</h2><p>段落</p>
<h2>まとめ</h2><p>段落</p>
""".strip()
    out = inject_ctas(sample, categories=["Money"], slug="test-saimu-seiri-3-comparison")
    print(out[:1000])
    print("\n---")
    print(f"CTA count in output: {out.count('hb-cta-box')}")
