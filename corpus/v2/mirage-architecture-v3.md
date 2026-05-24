<!-- License: CC0-1.0 -->
# Mirage アーキテクチャ v3.2 (現行)

> 最終更新: 2025 年 3 月 18 日 (プロダクト本部 / SRE 室レビュー済)
> v2 → v3 移行完了、本番稼働中。v2 は `mirage-architecture-v2-archive.md` に archive 済

ナギサ・パートナーズ自社プロダクト **Mirage** (中小企業向け文書管理 SaaS) の現行アーキテクチャ。2025 年 3 月の v3 メジャー移行で大幅に刷新された。

## 構成サマリ

| レイヤ | コンポーネント | 採用バージョン |
| ------ | -------------- | -------------- |
| Frontend | Next.js 14 (App Router) + TypeScript | 2024-09 移行 |
| API | Node.js 22 LTS + Hono framework | 2025-03 v3 移行で Express から置換 |
| Auth | Keycloak (OIDC provider) | v3 で BASIC + JWT から置換 |
| DB | PostgreSQL 15 (顧客別シャーディング) | v3 で v12 単一インスタンスから置換 |
| Storage | S3 互換 (Cloudflare R2) | 文書 blob と OCR テキスト |
| Queue | Amazon SQS | 非同期 OCR ジョブ |
| Deploy | Blue-Green on AWS ECS Fargate | v3 で Rolling Update から置換 |

## 認証

OIDC 経路で Keycloak に委任。Tier 1 顧客 (年商 50 億以上) は顧客 IdP との **SAML 2.0 連携**をオプションで提供。

- 一般顧客: Email + 多要素認証 (TOTP)
- Tier 1: 顧客 IdP (Okta / Azure AD / Google Workspace) と SAML 連携
- API キー認証は廃止 (v2 で利用可能だった BASIC + JWT は v3 で完全撤廃)

## DB シャーディング

PostgreSQL 15 を顧客別にシャーディング。`tenant_id` を sharding key として 8 shard で運用。

- shard 配置: AWS RDS 8 インスタンス (m6i.xlarge)
- shard 跨ぎクエリは禁止 (アプリ層で `tenant_id` を必ず付与)
- 顧客追加時のリバランスは半年に 1 度の定期 maintenance window で実施

v2 では単一 RDS インスタンス + 全テナント同居だったため、Tier 1 顧客が増えるごとにレスポンスタイム劣化が発生していた。

## コードレビュー基準

Mirage 開発で PR をマージするには以下を満たすこと:

- **2 人以上の approve 必須** (うち 1 人は同事業部、もう 1 人は他事業部 reviewer が望ましい)
- 1 PR あたり **400 LOC まで** (超える場合は分割推奨)
- deploy 前に staging で動作確認、確認結果を PR コメントに record
- 観点: ロジック正確性 / セキュリティ (SQL injection / XSS) / パフォーマンス / 命名 / テストカバレッジ 80% 以上
- 採点形式ではなく review コメントで議論、合意で approve

## ロールバック手順

Mirage は **blue-green デプロイ**で運用。本番障害時は ALB の listener rule を 1 コマンドで切り替えて旧バージョンに戻せる。

```
# SRE 室 on-call が実行 (例)
$ aws elbv2 modify-listener --listener-arn $LISTENER --default-actions \
    Type=forward,TargetGroupArn=$BLUE_OR_GREEN
```

- 切り替え所要時間: **約 1 分**、ヘルスチェック含めて 5 分以内に完全復旧
- v2 (Rolling Update) では復旧に 15-20 分要していた
- 切り替え判断は SRE lead (on-call) — 詳細は `nagisa-incident-flow.md` の「ロールバック判断基準」

## 関連書類

- 障害対応フロー: `nagisa-incident-flow.md`
- 旧版アーキテクチャ (参考のみ): `mirage-architecture-v2-archive.md`
- セキュリティ・脆弱性報告窓口: CS lead 経由で受付 (物理セキュリティとは別、`nagisa-office-security.md` とは異なる)
