<!-- License: CC0-1.0 -->
# ナギサ・パートナーズ — 障害対応フロー

> 最終更新: 2025 年 11 月 12 日 (SRE 室)

## 障害レベル (Priority)

ナギサでは障害を 3 レベルに分類する。判定は **最初に気付いた人** が初動レベルとして設定し、状況把握後に上下に変更してよい。

### P1 — Production down

- 自社プロダクト **Mirage** が全顧客 (もしくは Tier 1 顧客) で機能不全、または受託 PJ の本番環境が顧客通知必要レベルで停止
- 初動 SLA: **5 分以内 acknowledge / 30 分以内 顧客連絡開始**
- on-call エンジニア + on-call SRE + CS lead が PagerDuty で同時呼び出し
- Slack channel: `#incident-active` (該当インシデントごとに thread を立てる)

### P2 — Partial degradation

- 一部機能不全、ユーザ回避策あり
- 初動 SLA: **15 分以内 acknowledge / 2 時間以内 顧客連絡 (該当顧客のみ)**
- on-call エンジニアが対応、必要に応じて squad lead を巻き込む

### P3 — Cosmetic / Backlog

- UI bug、文言誤り、開発環境の問題
- 翌営業日対応で OK、backlog に積む

## 初動のステップ

1. PagerDuty で acknowledge する (5 分以内)
2. `#incident-active` で Priority 判定 + 影響範囲速報を post
3. 顧客向けステータスページ (status.mirage.nagisa-partners.jp) を更新 (P1/P2)
4. **一次対応として以下のいずれかを実施**:
   - ロールバック (直近デプロイの取り消し)
   - フェイルオーバ (待機系への切替)
   - トラフィック切り離し (該当機能の一時停止)
5. CS lead に状況同期 (顧客連絡前)

## ロールバック判断基準

P1 障害かつ **直近 30 分以内にデプロイがあった場合**、ロールバックを第一選択とする。Mirage は blue-green デプロイなので、5 分以内に switch back 可能 (`mirage-architecture-v3.md` 参照)。

- ロールバック実施前に SRE lead (on-call) に必ず通知
- 5 分以内に switch back で復旧しない場合は、別の一次対応 (フェイルオーバ / 切り離し) に切り替え
- 受託 PJ (Lumen / Marisol) では顧客側システム連携の都合でロールバック手順が異なる場合がある。各 PJ ドキュメントを優先

## Post-mortem

P1 / P2 は **5 営業日以内に post-mortem を作成**。テンプレートは Confluence `incident-postmortem-template`。

- 振り返り箇所: タイムライン / 直接原因 / 根本原因 / Next Action
- post-mortem は **blameless** (個人を責めない)
- public post-mortem (顧客向け要約) は Tier 1 顧客には別途送付

## 用語整理

社内で **「障害」「インシデント」「トラブル」「サービス停止」「P1/P2/P3」** はすべて同じものを指す。post-mortem 文書では英語表記 (incident) が主流、運用報告では「障害」、顧客連絡では「サービス影響」と書き分ける慣例がある。

## 関連書類

- on-call 体制は `nagisa-faq-helpdesk.md` の「on-call」項目を参照
- Mirage アーキテクチャの詳細 (ロールバック手順含む) は `mirage-architecture-v3.md`
- 顧客 PJ 固有のロールバック手順: Lumen は別 wiki page を参照 (倉庫オペレーションでの誤出荷ロールバックは `lumen-rollback-pallet.md` だが、これは IT 障害ではない)
