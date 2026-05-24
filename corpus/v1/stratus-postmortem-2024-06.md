<!-- License: CC0-1.0 -->
# Post-mortem: Stratus Auth Service DB connection exhaustion (2024-06-13)

> Document type: Post-mortem (Sev1)
> Author: K. Mori (SRE)
> Status: Closed
> Severity: **Sev1** (顧客影響: 全顧客、22 分間ログイン不可)

## TL;DR

2024 年 6 月 13 日 14:32-14:54 (JST) の 22 分間、**Auth Service** が DB connection pool 枯渇により応答不可となり、全顧客が新規ログインできなくなった。既存セッションは生存していたため、ログイン中のユーザは利用継続可能。原因は新規顧客 onboarding のバッチ処理が想定以上の認可テストトラフィックを発生させたこと。Fix は connection pool 設定の見直しと、onboarding バッチの並列度制限。

## Timeline

| Time (JST) | Event |
| ---------- | ----- |
| 14:30 | 新規顧客 X の自動 onboarding バッチが開始 (定例) |
| 14:32 | PagerDuty が Auth Service の latency p95 > 5s を検知、on-call SRE が ack |
| 14:34 | Slack `#incident-active` でスレッド開始、Sev2 として初動 |
| 14:38 | 顧客から問い合わせが複数件、Sev1 に昇格、CS lead 巻き込み |
| 14:42 | Auth Service の DB connection pool が 100% 利用中と判明 |
| 14:48 | onboarding バッチを emergency stop、pool を一時拡張 (200 → 500) |
| 14:54 | サービス復旧、status page 更新 |
| 15:30 | post-mortem 1 次ドラフト開始 |

## Root cause

- Auth Service は **独立したマイクロサービス** として運用されており、自身の PostgreSQL に対して connection pool size = 200 を確保していた。
- 新規顧客 onboarding 時、ハルナ社内のテストツールが各顧客に対して **同時 80 並列** で認可フローを叩いていた。1 顧客につき接続 1 確保 + token 検証で接続を一時的に 2 確保するため、200 並列で 160 接続が消費される計算。
- 同時に通常トラフィックも流れており、瞬間的に pool が枯渇。Auth Service が応答不可になると、**他の全サービスが token 検証で blocking** し、全体ログイン不可に。

## Why this happened

- onboarding バッチの並列度設定が **3 年前の 1/4 規模時代の値を踏襲** していた
- Auth Service の依存関係を 1 つの failure domain として捉えていなかった
- DB connection pool 監視は alerting に組み込まれていたが、threshold が「90% で warning」設定で「30 秒以上 95% 超」のような時間軸が無く、急上昇に追従できなかった

## Action items

- [x] onboarding バッチの並列度を 80 → 20 に変更 (即日)
- [x] Auth Service の DB pool を 200 → 400 に増設
- [x] DB pool 利用率の time-window alert を追加 (3 分間 90% 超で page)
- [ ] Auth Service の SPOF 性を再評価 (アーキテクチャ委員会で議論予定)
- [ ] 新規顧客 onboarding を非同期キュー方式に置換する RFC 起票

## Lessons learned

- **Auth Service が独立サービスである** という前提は、依存関係を把握する上で重要。Stratus の他サービスはすべて Auth Service の生存に依存している。
- 認可トラフィックの「テスト」と「本物」が同じ pool を使っており、isolation が無かった。
- 緊急停止できるバッチ運用が間に合った点は良かった。次回も「最初に止める」選択肢を保持する。

## Cross-reference

- Auth Service の責務: `stratus-architecture-v3.md` §「Auth Service」
- 障害対応フロー: `haruna-incident-flow.md`
