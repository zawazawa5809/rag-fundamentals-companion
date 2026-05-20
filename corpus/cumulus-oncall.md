<!-- License: CC0-1.0 -->
# Cumulus Labs — Engineering On-call

## ローテーション

engineering の on-call は週次 (月曜 10:00 JST 〜 翌月曜 10:00 JST) で、PagerDuty で管理する。各 squad ごとに primary / secondary を 1 名ずつ assign する。

- primary: alert 一次対応、Sev1 では 5 分以内に acknowledge
- secondary: primary が応答できない場合の backup、30 分 SLA

## Compensation

- on-call 週: 通常給与 + on-call 手当 $500/週
- ページされた場合: 別途実工数を残業として計上 (上限なし)
- on-call 直後の月曜は flex day (出社しなくてよい)

## Escalation Path

```
Alert → primary (5 min) → secondary (30 min) → squad lead → CTO
```

## On-call kit

- ノートPC + 充電器
- PagerDuty mobile app + 緊急時 SMS
- Runbook (各 service の wiki ページに reference)
- 連絡用 Slack channel `#oncall-engineering`

## 文化

- on-call で叩き起こされたら必ず post-mortem を書く
- 「叩き起こされない」状態が理想。alert noise が増えたら squad の dev capacity を 20% 削って alert hygiene に回す
