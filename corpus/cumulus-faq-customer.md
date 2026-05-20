<!-- License: CC0-1.0 -->
# Cumulus Labs — 顧客 FAQ (要約版)

サポートに問い合わせの多い 10 件をまとめる。詳細は別 doc 参照。

## 料金

**Q: Starter から Pro に途中で変更できますか？**
A: はい、契約期間の途中でも prorated で切り替え可能です。詳細: `cumulus-pricing.md`

**Q: 年間契約の途中解約はできますか？**
A: 原則できません。Enterprise のみ個別交渉可。料金は払い戻し対象外。

**Q: 学生 / 非営利向けの割引はありますか？**
A: 非営利は Starter を 50% off。学生は dedicated student plan を提供中 (年 $0)。

## 機能

**Q: dashboard を export できますか？**
A: Pro 以上で PDF / CSV / PNG エクスポート可。Starter は CSV のみ。

**Q: API はありますか？**
A: 全 plan で REST API 提供。rate limit が plan ごとに異なる。`cumulus-pricing.md` 参照。

**Q: 自社 LLM を connect できますか？**
A: Pro 以上で OpenAI / Anthropic / Azure OpenAI を bring-your-own で接続可。Starter は Cumulus 提供のものを使う。

## セキュリティ

**Q: SOC 2 Type II 取得済みですか？**
A: はい、2025 年取得。最新レポートは sales@ 経由で NDA 後送付。

**Q: データは暗号化されていますか？**
A: 通信は TLS 1.3、保管は AES-256。Enterprise は KMS BYOK (顧客管理鍵) 対応。

## サポート

**Q: 日本語サポートはありますか？**
A: JST 営業時間内はメール / Slack 日本語対応。on-call の Sev1 は英語の場合あり (24/7 体制のため)。

**Q: 解約方法は？**
A: アカウント設定 → 「契約管理」→ 解約申請 (実行は次月末)。
