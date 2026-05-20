# rag-fundamentals-companion

ZeroZawa シリーズ「[今更聞けない RAG の作り方、評価の仕方](https://zerozawa.pages.dev/series/rag-fundamentals)」のサンプルコード repo です。各 Part に対応した実装が `examples/` 配下に並び、Part ごとの git tag (`part-01` 〜 `part-05`) でその時点の最小スコープを再現できます。

## Quick start

```bash
# 依存導入 (uv 必須)
uv sync --frozen

# キー設定
cp .env.example .env
# .env を編集して ANTHROPIC_API_KEY と OPENAI_API_KEY を入れる

# Part 1 の素朴な RAG を動かす
uv run python -m examples.naive_rag

# API キー無しで挙動だけ見たい場合
uv run python -m examples.naive_rag --mock
```

## Part ↔ tag 対応

| Part | Tag | スコープ | エントリポイント |
| ---- | --- | -------- | ---------------- |
| 1 | `part-01` | 素朴な RAG (100 行) | `examples.naive_rag` |
| 2 | `part-02` | chunking / embedding / hybrid + BM25 | `examples.retrieval.run` |
| 3 | `part-03` | reranker + citation + prompt design | `examples.generation.run` |
| 4 | `part-04` | RAGAs + golden set 評価 | `examples.evaluate` |
| 5 | `part-05` | logging safety + drift + cost | `examples.ops.run` |

特定の Part だけ動かしたい場合:

```bash
git checkout part-01
uv sync --frozen
uv run python scripts/smoke_part.py --part 01 --mock
```

## Series articles (back-link)

- ハブ: <https://zerozawa.pages.dev/series/rag-fundamentals>
- Part 1: <https://zerozawa.pages.dev/posts/rag-naive-baseline>
- 以降は順次公開

## Tech stack

- Python 3.11+ / [uv](https://docs.astral.sh/uv/) (lockfile commit 済)
- LLM: [Anthropic Claude](https://www.anthropic.com/) (`anthropic` SDK)
- Embedding: [OpenAI text-embedding-3-small](https://platform.openai.com/docs/guides/embeddings)
- BM25: [`rank-bm25`](https://github.com/dorianbrown/rank_bm25)
- Cross-encoder rerank: [`sentence-transformers`](https://www.sbert.net/)
- (Optional) [Cohere Rerank API](https://docs.cohere.com/docs/rerank) for Part 3 比較

## Repository status

このリポジトリは ZeroZawa シリーズの進行と並行して育ちます。Part 1 公開時点では雛形のみ commit されており、各 Part の本実装は順次 push されます。

| Status | What's here |
| ------ | ----------- |
| 🌱 scaffolded | この時点。雛形 + `uv.lock` + smoke workflow のみ |
| 🚧 active | Part 1〜N の examples 追加中 |
| ✅ stable | Part 5 公開後。`main` は完結版を保持 |

## License

- Code (`clients.py`, `examples/`, `scripts/`, `tests/`): **MIT** (see [LICENSE](./LICENSE))
- `corpus/**`: **CC0 1.0** (see [LICENSES/CC0-1.0.txt](./LICENSES/CC0-1.0.txt))
- `squad_subset.jsonl` + `scripts/build_squad_subset.py`: **CC BY-SA 4.0** (see [LICENSES/CC-BY-SA-4.0.txt](./LICENSES/CC-BY-SA-4.0.txt) and [NOTICE](./NOTICE))

## Issues / questions

シリーズ本文 (zerozawa.pages.dev) に書きたい質問や typo 修正は当 repo の Issues、ZeroZawa 全体への feedback はブログ側のコンタクトを使ってください。
