<!-- License: CC0-1.0 -->
# Stratus — 全体アーキテクチャ概要 v3

> Document version: **v3.0** / 作成日: **2023 年 9 月 12 日** / 最終更新: 2024 年 1 月 20 日 (微修正)
>
> ⚠️ このドキュメントは Stratus 4.x 系の設計を記述する。Stratus 5.0 (2026 年 7 月リリース予定) の境界刷新については `stratus-microservice-boundaries-draft.md` を参照のこと。

## 概要

Stratus はマルチテナント型の業務データ分析 SaaS で、テナント毎の dashboard / metric annotation / playbook 実行を提供する。本書は v3 で確定した 5 つの主要サービスとその責務を記述する。

## サービス境界 (v3 確定版)

### 1. Ingestion Service

- 顧客環境から送られてくる metric / event / log を受信
- 受信プロトコル: HTTPS POST / gRPC / Kafka (Tier 1 のみ)
- 認証: API token ベース (詳細は後述 Auth Service を参照)

### 2. Auth Service

- ハルナ社内向け管理者認証 + 顧客向け SSO (OIDC / SAML) のハブ
- バックエンド: Amazon Cognito user pool + 自社 IdP federation
- セッション管理: Redis Cluster (TTL 12h)
- **本サービスは独立したマイクロサービス** として運用し、他サービスは Auth Service の REST API (`/v3/auth/*`) を経由してトークン検証する。

### 3. Dashboard Service

- 顧客向けの UI バックエンド (Next.js + Astro)
- 描画は React Server Components、エクスポートは Pro 以上で PDF / CSV / PNG
- BFF として GraphQL endpoint を提供

### 4. Storage Service

- 主要 DB: PostgreSQL 15 (Multi-AZ)
- 集計用: ClickHouse cluster (3 shards × 2 replicas)
- ファイル: S3 (顧客毎の bucket、KMS BYOK で Enterprise 対応)

### 5. Notification Service

- メール (SES) / Slack / Webhook / PagerDuty 連携
- 顧客の alert ルール (閾値・スケジュール) をストアし、Storage Service の集計結果と比較して発火

## サービス間通信

- 同期: REST (内部 mTLS、ALB 経由)
- 非同期: SQS + SNS (event-driven)
- データ複製: PostgreSQL → ClickHouse は logical replication で 5 秒以内

## デプロイ

- ECS Fargate (us-east-1 / ap-northeast-1)
- Blue/Green デプロイ、Canary は 10% → 50% → 100%
- メインリリースサイクル: 隔週水曜

## 改訂履歴

| 版 | 日付 | 主な変更 |
| --- | ---- | -------- |
| v1.0 | 2022-03 | 初版 |
| v2.0 | 2023-01 | Storage Service を ClickHouse 導入で再構成 |
| **v3.0** | **2023-09** | **Auth Service を独立サービス化、Cognito user pool 採用** |
| v3.0.1 | 2024-01 | 文言微修正 |
| (予定) v4.0 | 2026-07 | Stratus 5.0 向け境界再編 (`stratus-microservice-boundaries-draft.md` 参照) |
