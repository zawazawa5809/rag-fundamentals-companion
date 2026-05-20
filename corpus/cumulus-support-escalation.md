<!-- License: CC0-1.0 -->
# Cumulus Labs — Support Escalation

## 3 段階エスカレーション

### Sev1 — Production down

- 全顧客 / 重要顧客の本番環境が利用不可
- 初動: Enterprise 1 時間 / Pro 4 時間 / Starter 1 営業日
- on-call engineer に PagerDuty で即時通知 (`cumulus-oncall.md` 参照)
- 関係者: CTO + CS lead + 該当 squad

### Sev2 — Partial degradation

- 一部機能が利用不可、ただし回避策あり
- 初動: Enterprise 4 時間 / Pro 1 営業日 / Starter 3 営業日
- Support engineer → escalation engineer の順
- 24 時間以内に解消できない場合は Sev1 に昇格

### Sev3 — Cosmetic / Non-blocking

- UI bug、文言間違い、ドキュメント不整合 など
- backlog 化、次のリリースで対応
- 1 週間以内に「いつ直すか」を顧客に返信

## ベストプラクティス

- 顧客とのコミュニケーションは Slack connect が default。電話は Enterprise Sev1 のみ
- 内部での log 共有は機密マスクを必ず通す (PII / 顧客名)
- Sev1/Sev2 は post-mortem を 5 営業日以内に書く

## See also

- on-call rotation: `cumulus-oncall.md`
- Brand voice (顧客連絡時): `cumulus-brand-voice.md`
