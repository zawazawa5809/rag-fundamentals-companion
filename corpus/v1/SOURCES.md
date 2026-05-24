# Corpus sources

## License

このディレクトリ配下のすべての `.md` ファイルは、本 series のために fictional に生成したものです。**いかなる第三者著作物のコピーも含みません**。

すべて [CC0 1.0 Universal](../LICENSES/CC0-1.0.txt) (パブリックドメイン宣言) でリリースされています。商用 / 非商用問わず、attribution なしで自由に再利用・改変できます。

各 `.md` の冒頭に `<!-- License: CC0-1.0 -->` の per-file ヘッダがあります。

## 設定

「ハルナ・テクノロジーズ株式会社」(本店: 群馬県高崎市、東京本社: 渋谷区) は、本 series 専用に設定した架空の日本 IT 企業です。社員約 1,000 名、SaaS プロダクト **Stratus** (マルチテナント業務データ分析) と受託システム開発の両建てで、上場準備中という想定です。実在する企業名・人物・URL・商標とは無関係です。

## 構成 (10 件)

### 一般社内ドキュメント (4 件)

| File | 概要 |
| ---- | ---- |
| `haruna-remote-work.md` | リモートワーク制度・在宅勤務手当 |
| `haruna-expense.md` | 経費精算ガイド (マネーフォワード経費、領収書ルール) |
| `haruna-incident-flow.md` | 障害対応フロー (Sev1-Sev3) |
| `haruna-faq-helpdesk.md` | 社内ヘルプデスク FAQ (人事・労務・IT 横断) |

### 開発系ドキュメント (5 件) — **意図的に劣化** させた設計

| File | 種別 | 劣化の種類 |
| ---- | ---- | ---------- |
| `stratus-architecture-v3.md` | アーキテクチャ図 v3 | **2023 年版・現行だが古い前提。v4 で見直し予定と注記** |
| `stratus-microservice-boundaries-draft.md` | マイクロサービス境界 draft v1.2 | **承認前ドラフト・v3 と矛盾**。実装着手は最終承認後 |
| `stratus-api-reference.md` | API リファレンス | **コード自動生成 (openapi-generator)・最新だが文体が完全に異質** |
| `stratus-postmortem-2024-06.md` | 障害ポストモーテム | **古い Auth Service 設計を前提に書かれている** |
| `pegasus-er-diagram.md` | レガシー Pegasus ER 図 | **作成日 2018 年推定、2023 年に軽微追記、現状の DB と乖離** |

### 文体類似 trap (1 件)

| File | 役割 |
| ---- | ---- |
| `haruna-club-painting.md` | お絵描き同好会の月例活動報告。**post-mortem や 1on1 振り返りシートと構造が酷似** (やったこと / 振り返り / Next Action)。内容は完全に無関係 |

## なぜこの corpus 設計か

本シリーズの目標 (Part 1-5) は、「動く RAG」から「使える RAG」までの距離を可視化することです。そのために corpus 側に **教育目的の "仕込み"** を意図的に入れてあります。

### 仕込み 1: synonym / acronym 過密 (Part 2 hybrid 効く)

社内文書あるある:
- 「リモートワーク」「在宅勤務」「テレワーク」「WFH」
- 「障害」「インシデント」「トラブル」「Sev」
- 「経費」「立替」「精算」「PR」
- 「会議」「ミーティング」「mtg」「打ち合わせ」

これらは Part 2 で **BM25 + dense embedding の hybrid search + RRF** で効果が数値化されます。

### 仕込み 2: ドキュメンテーション劣化 (Part 1 で爆発、Part 2 + Part 5 で回収)

開発組織で本当にあるあるな課題:
- **同じシステム (Stratus) の設計が複数版** で wiki に並ぶ (v3 確定版 / draft v1.2 / API 自動生成)
- **古い文書と新しい文書が矛盾** している
- **更新日が信頼できない** (Pegasus は作成日が消失)
- **承認前ドラフトと本番設計が並列に存在**

Part 1 ではこれを「**LLM が矛盾を見抜けず、古い設計をそのまま結論として返す**」失敗パターンとして体感します。

Part 2 では metadata 保持型 chunking で版情報を文書に残し、Part 5 では freshness filter + index 更新タイミング設計で運用面から解決します。

### 仕込み 3: 文体類似 trap (Part 2-3 reranker 効く)

「お絵描き同好会の振り返り」は **業務文書と全く同じ構造** (TL;DR / やったこと / 振り返り / Next Action) で書かれています。embedding は内容ではなく構文・文体を強く拾うため[^embedding-surface-bias]、振り返り構文のクエリで意図せず混入します。

Part 2-3 で cross-encoder reranker を 2 段目に挟むことで、表層類似ではなく内容関連性で再採点できることを示します。

### 仕込み 4: cross-reference (Part 3 引用設計に布石)

ほぼすべての文書に `See also: xxx.md` 形式のリンクを置いてあります。Part 3 で「正しい引用付き RAG」を実装するとき、これらの参照関係を grounding に使えます。

---

これらの「仕込み」は **教育目的** であり、実プロダクションの corpus 設計とは異なる方針です。実運用では:
- ドキュメント版数管理は metadata で明示すべき
- 古い文書は archive 化して index から除外すべき
- post-mortem は「ある時点のスナップショット」と明示すべき

— といったベストプラクティスがあります。Part 5「本番運用」でこれらを扱います。

[^embedding-surface-bias]: Reimers & Gurevych, "Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks" (EMNLP 2019) で議論される、sentence embedding の表層構文への bias。
