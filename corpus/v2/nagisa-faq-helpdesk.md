<!-- License: CC0-1.0 -->
# ナギサ・パートナーズ — 社内ヘルプデスク FAQ

> 最終更新: 2025 年 10 月 28 日 (情報システム部)

社内で「これどこに聞けば？」と詰まりがちな質問をまとめた、横断 FAQ。問い合わせ前にここを検索することを推奨。

## IT インフラ系

### VPN が繋がらない

社内 IT サポート (`#help-it` Slack チャンネル) に連絡。VPN クライアントは Pulse Secure。在宅勤務初日のセットアップ手順は onboarding wiki を参照 (`nagisa-onboarding-checklist.md`)。

### パスワード再設定

社員ポータル (portal.nagisa-partners.internal) → 「アカウント設定」→「パスワード変更」。多要素認証用 OTP アプリは Authy を推奨。

### GitHub Enterprise の権限申請

`#help-devops` で「PJ 名 + repo 名 + write/read」を post。SRE 室が当日中に処理 (営業時間内)。

## 人事 / 労務系

### 有給休暇申請

kintone「休暇申請」フォームから 1 営業日前までに申請。半休 (午前/午後) も同フォーム。

### 在宅勤務手当の支給日

毎月 25 日。前月の出勤記録から自動判定 (在宅 5 営業日以上)。詳細は `nagisa-remote-work.md`。

### 経費精算が承認されない

部門長承認が滞っている可能性。マネーフォワード経費の「申請状況」を確認。3 営業日以上動いていなければ `#help-keiri` に問い合わせ。経費ルールは `nagisa-expense.md`。

## SRE / 障害対応系

### 緊急障害が発生した

`#incident-active` に Priority 速報を post。詳細フローは `nagisa-incident-flow.md` を参照。

### on-call ローテーション

SRE 室の on-call は週次ローテ (月-日)。PagerDuty に登録されている。プロダクト本部 (Mirage) の on-call は SI 事業部の障害には呼ばれない (それは SRE 室で扱う)。

### サービスステータスページの更新権限

CS lead と SRE 室 lead が持つ。P1/P2 障害時は CS lead が更新するのが慣例。

## オフィス / 総務系

### 来客対応

受付 (1F エントランス) で来客者の名前を確認。社員カード IC で入退館管理 (`nagisa-office-security.md`)。

### お菓子コーナーの使い方

1F カフェスペース。詳細は `nagisa-snack-policy.md`。

### 社内クラブ

ボードゲーム同好会 (`#club-boardgame`)、ランニング部 (`#club-running`) など。各クラブの活動報告は wiki にまとめられている (例: `nagisa-boardgame-monthly.md`)。

## 関連書類

- 障害対応の詳細フロー: `nagisa-incident-flow.md`
- リモートワーク制度: `nagisa-remote-work.md`
- 経費精算: `nagisa-expense.md`
