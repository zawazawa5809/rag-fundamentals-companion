<!-- License: CC0-1.0 -->
# Stratus 5.0 — マイクロサービス境界の見直し (ドラフト)

> Document version: **draft v1.2** / 起草日: 2025 年 11 月 7 日 / 最終更新: **2026 年 4 月 22 日**
>
> ⚠️ **本書はまだ承認されていないドラフト** である。CTO + アーキテクチャ委員会の最終承認は 2026 年 5 月末を予定。実装着手は最終承認後。
>
> ⚠️ 内容は **v3 (`stratus-architecture-v3.md`) と一部矛盾する**。両者の差分を §「v3 からの主な変更点」にまとめている。

## ゴール

Stratus 5.0 (2026 年 7 月リリース予定) で、以下を達成するための境界再編を行う。

- 認証フローのレイテンシを 25% 改善 (目標 p95 < 80ms)
- マイクロサービス間の往復回数を削減 (目標 -40%)
- 新規顧客 onboarding の自動化率を向上 (目標 90%)

## 新境界 (draft v1.2)

### A. API Gateway (Auth 統合)

- これまで独立サービスだった **Auth Service を API Gateway に統合** する
- トークン検証は API Gateway の Lambda Authorizer で完結
- バックエンドサービスは検証済みクレームを `x-tenant-id` / `x-user-roles` ヘッダで受け取る
- Cognito user pool は引き続き利用するが、各サービスから直接呼ばない

### B. Data Plane

- Ingestion / Storage / Notification を「Data Plane」としてグルーピング
- 内部通信は API Gateway を経由しない (mTLS + service mesh)

### C. Control Plane

- Dashboard / 顧客 onboarding / 管理者 UI を「Control Plane」としてグルーピング
- すべて API Gateway 経由

## v3 からの主な変更点

| 項目 | v3 (現行) | draft v1.2 (新) |
| ---- | --------- | --------------- |
| Auth | 独立サービス、REST `/v3/auth/*` | API Gateway 統合、Lambda Authorizer |
| サービス数 | 5 | 4 (Auth 廃止) + 統合 GW |
| Token 検証経路 | 各サービス → Auth Service | API GW で完結 |
| トラフィック分離 | なし | Data Plane / Control Plane |

## リスクと未解決事項

- 既存 Auth Service の SDK (Java / Python / Go の 3 言語) を deprecation するタイミング
- 顧客が直接 Auth Service API を叩いている事例があり、後方互換性の設計が未確定
- Stratus 4.x の本番稼働中は v3 設計が引き続き正
- **本書の内容に基づいてコードを書かないこと**。承認前は v3 が現行設計

## 次のステップ

- 2026-05-27 アーキテクチャ委員会で最終承認 (予定)
- 承認後、`stratus-architecture-v3.md` を v4 に更新
- 7 月リリースに向けて段階的に切り替え
