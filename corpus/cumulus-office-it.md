<!-- License: CC0-1.0 -->
# Cumulus Labs — Office IT セットアップ

## 入社時に配布されるもの

- MacBook Pro (M シリーズ、過去 18 ヶ月以内モデル)
- USB-C 充電器 + ハブ
- 外付け 27 inch ディスプレイ (希望者のみ、自宅配送可)
- Yubikey 2 個 (1 つは予備、別保管)
- 社員証

## 初日にやること

1. macOS セットアップ (個人情報入力済、初回起動だけ)
2. 1Password にログイン (招待リンクが入社前にメール送付済)
3. Slack / Linear / GitHub / PagerDuty に SSO 経由でログイン
4. Yubikey を GitHub / Google account に登録
5. `#new-folks` channel で自己紹介

## SSO

すべての社内ツールは Okta SSO 経由。Okta のパスワードは 1Password に保存。Yubikey は MFA の唯一の手段 (SMS / TOTP は禁止)。

## VPN

社内ネットワーク (`*.internal.cumulus.dev`) へのアクセスは Tailscale 経由。CTO の招待を待つ。

## トラブル

- Slack `#help-it` へ
- 営業時間は JST 10:00-19:00。それ以外は緊急のみ on-call の IT 担当 (`#oncall-it`) へ
