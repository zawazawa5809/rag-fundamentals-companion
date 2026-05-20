<!-- License: CC0-1.0 -->
# Cumulus Labs — North Star Metric

## North Star Metric (NSM)

Cumulus Labs の North Star Metric は **Weekly Active Squads (WAS)** である。具体的には「直近 7 日間に、squad ID 単位で少なくとも 3 人のメンバーがアプリの core action (dashboard share / metric annotate / playbook run のいずれか) を実施した squad の数」と定義する。

## なぜ "squad" 単位なのか

個人ユーザ数 (MAU / WAU) は B2B プロダクトでは伸び方が拡張的になりやすい一方、価値は **チームでの利用継続** に集約されるため、squad を単位にとる。

## 周辺指標

- WAS (North Star)
- NAS (Newly Active Squads) — 過去 4 週で初めて WAS にカウントされた squad の数
- Squad Churn Rate — 過去 8 週で WAS から脱落した squad / 4 週前 WAS

## 用語整理

- "North Star Metric" は社内では NSM と略す
- 「主要目標指標」「最重要 KPI」「主指標」等の和訳は使わない (混乱回避のため "North Star" / "NSM" に統一)
- 「squad」は社内では「チーム」とも呼ばれるが、メトリクス文脈では squad で統一

## 改訂履歴

- 2025-09: NSM 候補を MAU から WAS に変更 (本ページ)
- 2024-04: 初版 (MAU を North Star としていた時代)
