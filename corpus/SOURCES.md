# Corpus sources

## License

このディレクトリ配下のすべての `.md` ファイルは、本 series のために fictional に生成したものです。**いかなる第三者著作物のコピーも含みません**。

すべて [CC0 1.0 Universal](../LICENSES/CC0-1.0.txt) (パブリックドメイン宣言) でリリースされています。商用 / 非商用問わず、attribution なしで自由に再利用・改変できます。

各 `.md` の冒頭に `<!-- License: CC0-1.0 -->` の per-file ヘッダがあります。

## 構成

`Cumulus Labs` は本 series 専用に設定した架空の B2B SaaS 企業です。実在する企業名・人物・URL・商標とは無関係です。

| File | 概要 | Part 利用想定 |
| ---- | ---- | ------------- |
| `cumulus-okr-2026q2.md` | OKR 定義と Q2 の Key Result | Part 1 / Part 2 |
| `cumulus-north-star.md` | North Star Metric (WAS) の定義 | Part 1 (同義語 demo) |
| `cumulus-pricing.md` | 価格表と支払い条件 | Part 1 / Part 2 |
| `cumulus-support-escalation.md` | 3 段階エスカレーション | Part 2 / Part 3 |
| `cumulus-oncall.md` | エンジニア on-call ローテ | Part 3 |
| `cumulus-brand-voice.md` | brand voice 規範 | Part 1 (文体類似 trap 用) |
| `cumulus-office-it.md` | 入社時 IT セットアップ | Part 2 / Part 4 |
| `cumulus-hiring.md` | 採用 4 段階フロー | Part 4 (golden set) |
| `cumulus-faq-customer.md` | 顧客 FAQ 10 件 | Part 1 / Part 4 |
| `cumulus-bearista-coffee-review.md` | 社内マスコットのコーヒー豆評価 | **Part 1 distance trap demo** |

## なぜこの corpus 設計か

Part 2 以降の検索改善 (chunking / hybrid / reranker) が**数値で改善する**ことを示すためには、Part 1 の素朴な実装が「いかにも失敗しそう」な特徴を corpus に意図的に混入しておく必要があります。

意図的に入れた特徴:

- **synonym / acronym 過密**: OKR / KR / KPI / NSM / WAS / NAS — Part 2 BM25 hybrid の効果
- **改訂履歴**: north-star.md に「2024 では MAU、2025 で WAS に変更」と書く → Part 2 freshness 議論
- **文体類似 trap**: bearista-coffee-review が brand-voice ガイドと類似の文体トーン → Part 1 「距離 0.95 でも内容無関係」の demo
- **cross-reference**: `See also: cumulus-X.md` 形式で文書間に明示的なリンクを置く → Part 5 grounding 議論

これらの「仕込み」は教育目的であり、実プロダクションの corpus 設計とは異なる方針です。
