<!-- License: CC0-1.0 -->
# Mirage アーキテクチャ v2 (2023 年度版・旧版)

> ⚠️ **Archive 注記**: この設計書は 2023 年 9 月時点の v2 アーキテクチャを記録したもの。**2025 年 3 月の v3 移行で全面刷新され、現行は `mirage-architecture-v3.md`**。本書類は履歴参照と移行コンテキストの記録のために archive されています。
>
> 最終更新: 2023 年 9 月 14 日 (プロダクト本部)

ナギサ・パートナーズ自社プロダクト **Mirage** v2 系のアーキテクチャ。Tier 1 顧客増加に伴う性能劣化と認証の柔軟性不足が課題となり、2025 年 3 月の v3 移行で大幅に置換された。

## 構成サマリ

| レイヤ | コンポーネント (v2 当時) |
| ------ | ----------------------- |
| Frontend | Next.js 12 (Pages Router) + TypeScript |
| API | Node.js 18 + Express |
| Auth | **BASIC 認証 + JWT** (v3 で OIDC + Keycloak に置換) |
| DB | **PostgreSQL 12 単一インスタンス** (v3 でシャーディング導入) |
| Storage | AWS S3 |
| Queue | AWS SQS |
| Deploy | Rolling Update (AWS ECS) — v3 で Blue-Green に置換 |

## 認証 (v2)

API キー (BASIC) と JWT トークンの併用。

- 一般顧客: Email + パスワード → JWT 発行
- 法人顧客: 共有 API キー (BASIC 経路、機能限定)
- Tier 1 SAML 連携は v2 では非対応 (v3 で対応)

## DB (v2)

PostgreSQL 12 単一 RDS インスタンス (db.m5.large) に全テナントが同居。

- 全テナント共用、`tenant_id` カラムで論理分離
- Tier 1 顧客追加で書き込み competition が頻発、レスポンスタイム劣化
- バックアップは日次スナップショット

## ロールバック手順 (v2)

Rolling Update のため、本番障害時のロールバックは新バージョンを順次置き戻していく形式。

- 復旧所要時間: **約 15-20 分** (v3 の blue-green より遅い)
- 切り戻し中は新旧バージョン混在状態

## 関連書類

- 現行 v3 アーキテクチャ: `mirage-architecture-v3.md` (2025-03 公開)
- 障害対応フロー: `nagisa-incident-flow.md`

---

**改訂履歴**:

- 2025-03-18: v3 移行完了、本書類は archive 化
- 2023-09-14: 初版作成
