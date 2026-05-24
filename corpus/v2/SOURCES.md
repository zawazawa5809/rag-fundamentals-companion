<!-- License: CC0-1.0 -->

# Corpus v2 sources (ADR 0004 baseline)

## License

このディレクトリ配下のすべての `.md` ファイルは、本 series のために fictional に生成したものです。**いかなる第三者著作物のコピーも含みません**。

すべて [CC0 1.0 Universal](../../LICENSES/CC0-1.0.txt) (パブリックドメイン宣言) でリリースされています。商用 / 非商用問わず、attribution なしで自由に再利用・改変できます。

各 `.md` の冒頭に `<!-- License: CC0-1.0 -->` の per-file ヘッダがあります。

## Why v2

v1 (`corpus/v1/`) はハルナ・テクノロジーズ + Stratus 設定で、OpenAI `text-embedding-3-small` の挙動を暗黙の前提に hand-tuned されていた。Ollama (`qwen3-embedding:0.6b`) を再現基準とした実機検証で trap 構造が embedding-model 依存だったことが判明し、ADR 0004 (2026-05-23) で全面再設計を決定。v2 は新世界観 + Ollama 基準で trap 構造を意図的に組み込み、両 embedding model で挙動を事前検証した構成にする。

v1 は legacy として `corpus/v1/` に保持しており、`RAG_CORPUS_VERSION=v1` で旧 narrative の再現が可能。

## 設定 (新世界観)

「**ナギサ・パートナーズ株式会社**」(本社: 神奈川県横浜市みなとみらい、関西支店: 大阪市淀川区) は、本 series v2 のために設定した架空の日本 SIer 企業です。社員約 600 名、創業 2008 年、非上場のオーナー企業。

業態は **受託開発 7 割 + 自社プロダクト 3 割**。受託では大手物流・金融・観光 DMO の基幹システム再構築を主軸にし、自社では中小企業向け文書管理 SaaS **Mirage** (ミラージュ) を 2018 年から開発・運用しています。実在する企業名・人物・URL・商標とは無関係です。

### 主要顧客プロジェクト (架空)

| Project | 顧客業界 | 期間 | 概要 |
| ------- | -------- | ---- | ---- |
| **Project Lumen** | 大手物流 | 2024- | 倉庫管理システム (WMS) の再構築。約 80 拠点ロールアウト |
| **Project Tide** | 地方銀行 | 2023-2025 | 反社チェック・AML 規制対応ダッシュボード (契約終了済) |
| **Project Marisol** | 観光 DMO | 2022-2024 | 宿泊予約プラットフォーム (リリース済、保守フェーズ) |

### 主要部署

- SI 第 1 事業部 (Project Lumen 担当)
- SI 第 2 事業部 (Project Tide / Marisol 担当)
- プロダクト本部 (Mirage)
- SRE 室 (全社横断、障害対応の一次窓口)
- コーポレート本部 (人事・経理・法務)
- 情報システム部 (社内 IT インフラ)

### 障害分類

ナギサでは障害を **P1 / P2 / P3** の 3 段階で分類 (v1 ハルナの Sev 表記とは命名意図的に変えてある)。

## 構成 (15 件)

文書数とジャンル比率は ADR 0004 + Phase 1 spec (`docs/specs/rag-fundamentals-redesign/spec.md` of `zerozawa` repo) で確定:

- **genuine relevant**: 5 件 — 各 query の正解 doc
- **trap (surface 一致)**: 3 件 — query 表層と語が一致するが意味は無関係
- **trap (意味的近接)**: 3 件 — 意味は近いが reference に不適
- **trap (古い記述)**: 2 件 — current spec と矛盾する deprecated doc
- **filler / noise**: 2 件 — どの query にも該当しない雑文書

### Genuine relevant (5 件)

| File | 種別 | 概要 |
| ---- | ---- | ---- |
| `nagisa-remote-work.md` | 社内規程 | リモートワーク制度・在宅勤務手当 (2025 改訂) |
| `nagisa-expense.md` | 社内規程 | 経費精算ガイド (2025 改訂、月次/出張上限) |
| `nagisa-incident-flow.md` | SRE | 障害対応フロー P1-P3 + ロールバック判断基準 |
| `nagisa-faq-helpdesk.md` | 社内 FAQ | 社内ヘルプデスク FAQ (人事・労務・IT 横断) |
| `mirage-architecture-v3.md` | 技術 | 自社プロダクト Mirage 現行アーキテクチャ v3.2 (認証・DB・コードレビュー基準) |

### Trap: surface 一致 (3 件)

embedding model は表層構文を強く拾うため、query の語が doc に出現するだけで類似度が上がる失敗が起きる[^embedding-surface-bias]。

| File | 概要 | 想定 query | trap key |
| ---- | ---- | ---------- | -------- |
| `nagisa-running-club-plan.md` | ランニング部 5 月練習計画 | 「Project Lumen 今期リリース計画」 | 「計画」 |
| `nagisa-csat-report-2025q1.md` | 顧客満足度調査 (CSAT) 2025 Q1 結果 | 「P1 障害時の顧客連絡基準」 | 「顧客」 |
| `lumen-rollback-pallet.md` | Lumen 物流倉庫の誤出荷ロールバック手順 (荷物の戻し作業) | 「Mirage P1 時のロールバック判断」 | 「ロールバック」 |

物流業界の「ロールバック」(誤出荷した荷物をパレット単位で戻す作業) と IT の「ロールバック」(デプロイ取り消し) は別概念。embedding は語の意味文脈を区別しない。

### Trap: 意味的近接 (3 件)

意味が近いが reference に不適。Part 2 hybrid retrieval では残り、Part 3 cross-encoder rerank で消える設計。

| File | 概要 | 想定 query | 類似観点 |
| ---- | ---- | ---------- | -------- |
| `nagisa-boardgame-monthly.md` | ボードゲーム同好会 4 月活動報告 | 「P1 障害 post-mortem テンプレ」 | post-mortem 構造類似 (TL;DR / やったこと / 振り返り / Next Action) |
| `nagisa-lt-evaluation.md` | 社内 LT 大会 評価基準 | 「Mirage コードレビュー基準」 | 「評価基準」「採点」観点の意味類似 |
| `nagisa-office-security.md` | オフィス入退館 BCP (物理セキュリティ) | 「Mirage セキュリティインシデント対応」 | 「セキュリティ」ドメイン差 (物理 vs 情報) |

### Trap: 古い記述 (2 件)

社内 wiki にありがちな「旧版を archive せず並列で残してある」状況を再現。`status: archived` の前提だが、Part 5 で扱う metadata filter / freshness filter までは index に混入する。

| File | 概要 | 矛盾相手 | 矛盾点 |
| ---- | ---- | -------- | ------ |
| `nagisa-expense-2023-archive.md` | 経費精算 2023 旧版 (月 40,000 円 / 出張 150,000 円) | `nagisa-expense.md` (2025 改訂版) | 月次上限 / 出張上限の数値 |
| `mirage-architecture-v2-archive.md` | Mirage v2 アーキテクチャ (2023 公開) | `mirage-architecture-v3.md` (現行 v3.2) | DB 構造 (シャーディング有無) / 認証経路 |

### Filler / Noise (2 件)

どの想定 query にも relevant にならないが、社内 wiki に普通に存在する短文書。Recall@k の母集団を安定させるためのノイズ枠。

| File | 概要 |
| ---- | ---- |
| `nagisa-snack-policy.md` | オフィスお菓子コーナー運用ポリシー (補充ルール・支払い方法) |
| `nagisa-onboarding-checklist.md` | 新入社員 onboarding 1 週目チェックリスト (短文・参照頻度高) |

## なぜこの corpus 設計か

本シリーズ (Part 1-5) は「動く RAG」から「使える RAG」までの距離を可視化することが目的です。corpus 側に **教育目的の "仕込み"** を意図的に入れてあります。v1 から踏襲した仕込みもあれば、v2 で Ollama embedding 挙動に合わせて再設計した仕込みもあります。

### 仕込み 1: synonym / acronym 過密 (Part 2 hybrid で効く)

業務文書あるある:

- 「リモートワーク」「在宅勤務」「テレワーク」「WFH」
- 「障害」「インシデント」「トラブル」「P1/P2/P3」「故障」
- 「経費」「立替」「精算」「PR」
- 「コードレビュー」「PR レビュー」「コード品質」「査読」
- 「ロールバック」「rollback」「巻き戻し」「リバート」「戻し作業」(IT) / 「返品」「再格納」(物流)

これらは Part 2 で BM25 + dense embedding の hybrid search + RRF で効果が数値化されます。

### 仕込み 2: ドキュメンテーション劣化 (Part 1 で爆発、Part 2 + Part 5 で回収)

SIer + 自社プロダクト両建てで本当にあるあるな課題:

- 自社プロダクト Mirage の設計が **v2 と v3 で並列に wiki に残る**
- 顧客 PJ ごとに**ロールバック手順が違う**が、共通用語で書かれている
- 経費規程が**改訂時に旧版を archive せず**並列に残る
- 障害対応フロー (SRE 室管轄) と顧客 PJ 固有の対応手順が**重複・矛盾**

Part 1 では「LLM が古い設計をそのまま結論として返す」「物流業界のロールバックと IT ロールバックを混同して回答する」失敗パターンを体感します。

Part 2 では metadata 保持型 chunking で版情報を文書に残し、Part 5 では freshness filter + index 更新タイミング設計で運用面から解決します。

### 仕込み 3: 文体類似 trap (Part 2-3 reranker で効く)

「ボードゲーム同好会の月例振り返り」は **業務文書と全く同じ構造** (TL;DR / やったこと / 振り返り / Next Action) で書かれています。embedding は内容ではなく構文・文体を強く拾うため、振り返り構文のクエリで意図せず混入します。

Part 2-3 で cross-encoder reranker を 2 段目に挟むことで、表層類似ではなく内容関連性で再採点できることを示します。

### 仕込み 4: 専門領域差トラップ (Part 3 引用設計に布石)

`lumen-rollback-pallet.md` の「ロールバック」は **物流業界用語** (誤出荷荷物のパレット戻し作業)。`mirage-architecture-v3.md` の「ロールバック」は **IT デプロイ用語** (失敗デプロイの巻き戻し)。Part 3 で正しい引用付き RAG を実装するとき、context にどちらが渡っているかで答えが大きく変わります。

### 仕込み 5: cross-reference (Part 5 に布石)

ほぼすべての文書に `関連: xxx.md` 形式のリンクを置いてあります。Part 5 で「freshness filter + 関連参照グラフ」を扱うとき、これらの参照関係を grounding に使えます。

---

これらの「仕込み」は **教育目的** であり、実プロダクションの corpus 設計とは異なる方針です。実運用では:

- ドキュメント版数管理は metadata で明示すべき
- 古い文書は archive 化して index から除外すべき
- post-mortem は「ある時点のスナップショット」と明示すべき

— といったベストプラクティスがあります。Part 5「本番運用」でこれらを扱います。

## v1 との対応

| v1 (corpus/v1/) | v2 (corpus/v2/) | 備考 |
| --------------- | --------------- | ---- |
| `haruna-remote-work.md` | `nagisa-remote-work.md` | 数値・組織名のみ更新 |
| `haruna-expense.md` | `nagisa-expense.md` + `nagisa-expense-2023-archive.md` | v2 では新旧 2 件で stale trap 化 |
| `haruna-incident-flow.md` | `nagisa-incident-flow.md` | Sev → P1/P2/P3 へ命名差別化 |
| `haruna-faq-helpdesk.md` | `nagisa-faq-helpdesk.md` | 内容刷新 |
| `haruna-club-painting.md` | `nagisa-boardgame-monthly.md` | お絵描き → ボードゲーム、post-mortem 構造類似は踏襲 |
| `stratus-architecture-v3.md` | `mirage-architecture-v3.md` | Stratus → Mirage、技術スタック更新 |
| `stratus-postmortem-2024-06.md` | (廃止) | v2 は genuine が SRE フロー + Mirage アーキ中心 |
| `stratus-microservice-boundaries-draft.md` | (廃止) | v2 では「draft 並存」は v2/v3 archive で代替 |
| `stratus-api-reference.md` | (廃止) | v2 では自動生成 API ref は narrative に必要なし |
| `pegasus-er-diagram.md` | `mirage-architecture-v2-archive.md` | レガシー DB 図 → Mirage v2 archive で stale trap 化 |
| — | `nagisa-running-club-plan.md` | v2 新規 surface trap (「計画」一致) |
| — | `nagisa-csat-report-2025q1.md` | v2 新規 surface trap (「顧客」一致) |
| — | `lumen-rollback-pallet.md` | v2 新規 surface trap (「ロールバック」専門領域差) |
| — | `nagisa-lt-evaluation.md` | v2 新規 semantic trap (「評価基準」意味類似) |
| — | `nagisa-office-security.md` | v2 新規 semantic trap (「セキュリティ」ドメイン差) |
| — | `nagisa-snack-policy.md` | v2 新規 filler |
| — | `nagisa-onboarding-checklist.md` | v2 新規 filler |

## 想定 query 例 (golden_set 完成版は Phase 3 で構築)

Phase 2 では trap rank pattern の検証用に最小限の draft query を用意。完成版 30 件 (happy 15 / sad 10 / edge 5) は ADR 0004 Phase 3 で `golden_set.jsonl` に commit。

| qid 案 | query | genuine | 想定 trap | 想定 narrative |
| ------ | ----- | ------- | --------- | -------------- |
| H01 | リモートワーク手当はいくら？ | `nagisa-remote-work.md` | — | embedding 単独で top-1 |
| H02 | 経費精算の月次上限は？ | `nagisa-expense.md` | (stale) `nagisa-expense-2023-archive.md` | Part 5 freshness filter で archive 除外 |
| H03 | Mirage 現行アーキの認証経路は？ | `mirage-architecture-v3.md` | (stale) `mirage-architecture-v2-archive.md` | Part 5 で archive 除外 |
| H04 | P1 障害時の初動 SLA は？ | `nagisa-incident-flow.md` | (semantic) `nagisa-boardgame-monthly.md` | Part 3 rerank で trap 圏外へ |
| H05 | Mirage P1 障害時のロールバック判断は？ | `nagisa-incident-flow.md` + `mirage-architecture-v3.md` | (surface) `lumen-rollback-pallet.md` | Part 2 hybrid で surface trap 抑制 |
| S01 | コードレビューの観点・採点基準は？ | `mirage-architecture-v3.md` | (semantic) `nagisa-lt-evaluation.md` | Part 3 rerank で trap 消失 |
| S02 | Project Lumen 今期リリース計画は？ | (なし — 顧客 NDA で公開されない設定) | (surface) `nagisa-running-club-plan.md` | Part 5 status filter で「該当なし」回答 |
| E01 | お菓子コーナーの支払い方法は？ | `nagisa-snack-policy.md` | — | filler が genuine になる edge ケース |

[^embedding-surface-bias]: Reimers & Gurevych, "Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks" (EMNLP 2019) で議論される、sentence embedding の表層構文への bias。
