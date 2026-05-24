<!-- License: CC0-1.0 -->
# Pegasus — レガシーシステム ER 図解説

> Document type: 設計補足ドキュメント
> 作成日: 2018 年 5 月 (推定。Confluence の作成日が消失しており Wiki 履歴から逆算)
> 最終更新: 2023 年 11 月 (Stratus 移行計画の冒頭で軽微な追記)
>
> ⚠️ **本書は 2023 年 11 月時点の Pegasus DB スキーマを記述する**。Stratus への段階移行は計画されたが、2024 年以降一部テナント (旧 Enterprise 契約) で **継続稼働** しており、現状の DB との一致は保証されない。最新状態は Pegasus の本番 DB schema ダンプ (SRE 部管轄) を参照すること。

## Pegasus の位置付け

Pegasus はハルナ・テクノロジーズが 2017 年に開発した顧客管理 / 受注管理システム。2022 年に Stratus がリリースされ、新規顧客は Stratus に集約、既存顧客は段階移行を予定していた。

しかし以下の事情で **移行が完全には進まず、一部 Enterprise 顧客では Pegasus が引き続き本番運用** されている。

- 顧客側カスタム連携の改修コストが大きい
- 旧契約 (買い切りライセンス) の継続対応が必要
- Stratus 側で未実装の機能 (帳票出力など) を Pegasus に残している

## 主要テーブル (ER)

```
users
  ├─ id (PK, bigint)
  ├─ tenant_id (FK → tenants.id)
  ├─ email (unique within tenant)
  ├─ created_at
  └─ deleted_at (soft delete)

tenants
  ├─ id (PK)
  ├─ name
  ├─ plan ('starter', 'pro', 'enterprise')
  └─ created_at

orders
  ├─ id (PK)
  ├─ tenant_id (FK)
  ├─ user_id (FK → users.id)
  ├─ amount
  ├─ status ('pending', 'paid', 'cancelled')
  └─ created_at

payments
  ├─ id (PK)
  ├─ order_id (FK → orders.id)
  ├─ provider ('stripe', 'paypal', 'invoice')
  ├─ amount
  └─ confirmed_at

audit_log
  ├─ id (PK)
  ├─ actor_user_id (nullable)
  ├─ entity_type ('user', 'order', 'payment')
  ├─ entity_id
  ├─ action ('create', 'update', 'delete')
  ├─ payload (jsonb)
  └─ logged_at
```

## 既知の差異 (2023 年 11 月時点で確認)

- `orders.status` には実本番では `'refunded'` が追加されている (本書に未反映)
- `users` には `phone_number` カラムが追加された可能性あり (Confluence コメントによる、未検証)
- `audit_log.payload` の中身に PII が含まれることがあり、Stratus 移行時には除外設計が必要

## Stratus との対応関係 (移行計画より)

| Pegasus | Stratus | 状態 |
| ------- | ------- | ---- |
| `tenants` | `Tenant` (Storage Service) | 移行済 |
| `users` | `User` (Auth Service) | 移行済 |
| `orders` | `Order` (Storage Service) | **部分移行** (旧 Enterprise は Pegasus 維持) |
| `payments` | (未対応) | Stratus 側に未実装 |
| `audit_log` | (未対応) | Stratus 側に統一監査ログ実装予定だが未着手 |

## 連絡先

- DB スキーマの最新状態: SRE 部 `#sre-pegasus`
- ビジネス継続に関する判断: 経営企画部
- 移行スケジュールの最新: アーキテクチャ委員会 (議事録は Confluence)
