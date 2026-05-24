<!-- License: CC0-1.0 -->
# ハルナ・テクノロジーズ — 障害対応フロー

> 最終更新: 2026 年 2 月 28 日 (SRE 部)

## 障害レベル (Sev)

ハルナでは障害を 3 レベルに分類する。判定は **最初に気付いた人** が初動レベルとして設定し、後で上下に変更してよい。

### Sev1 — Production down

- 自社プロダクト Stratus が全顧客 (もしくは Tier 1 顧客) で機能不全
- 初動 SLA: **5 分以内 acknowledge / 30 分以内 顧客連絡開始**
- on-call エンジニア + on-call SRE + CS lead が PagerDuty で同時呼び出し
- Slack channel: `#incident-active` (該当インシデント毎に thread を立てる)

### Sev2 — Partial degradation

- 一部機能不全、回避策あり
- 初動 SLA: **15 分以内 acknowledge / 2 時間以内 顧客連絡 (該当顧客のみ)**
- on-call エンジニア対応、必要に応じて squad lead を巻き込む

### Sev3 — Cosmetic / Backlog

- UI bug、文言誤り、開発環境の問題
- 翌営業日対応で OK、backlog に積む

## 初動のステップ

1. PagerDuty で acknowledge する (5 分以内)
2. `#incident-active` で Sev 判定 + 影響範囲速報を post
3. 顧客向けステータスページ (status.haruna-tech.com) を更新 (Sev1/2)
4. 一次対応: ロールバック / フェイルオーバ / トラフィック切り離し のいずれか
5. CS lead に状況同期 (顧客連絡前)

## Post-mortem

Sev1/Sev2 は **5 営業日以内に post-mortem を作成**。テンプレートは Confluence `post-mortem-template`。

- 振り返り箇所: タイムライン / 直接原因 / 根本原因 / Next Action
- post-mortem は **blameless** (個人を責めない)
- public post-mortem (顧客向け要約) は Tier 1 顧客には別途送付

## 用語整理

社内で **「障害」「インシデント」「トラブル」「サービス停止」「Sev」** はすべて同じものを指す。post-mortem 文書では英語表記 (incident) が主流、運用報告では「障害」、顧客連絡では「サービス影響」と書き分ける慣例がある。

## 関連文書

- オンコール体制は `haruna-faq-helpdesk.md` の「on-call」項目を参照
- 過去の Sev1 事例: `stratus-postmortem-2024-06.md`
