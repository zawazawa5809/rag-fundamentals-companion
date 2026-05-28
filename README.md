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

## 0 円で動かしたいとき (Ollama + Qwen3)

API キーを取らずに全 Part を再現したい読者向けに、Ollama (ローカル LLM ランタイム) + Qwen3 ファミリーを公式サポートしています。詳細は [zerozawa の ADR 0003](https://github.com/zawazawa5809/zerozawa/blob/main/docs/decisions/0003-ollama-free-alternative-stack.md) を参照。

```bash
# 1. Ollama を入れる (macOS なら brew install ollama)
brew install ollama
ollama serve &      # daemon を起動 (常駐させる場合は `brew services start ollama`)

# 2. モデルを pull (合計 ~6 GB / 約 5 分。16 GB Mac を想定)
ollama pull qwen3:8b               # 生成 (Apache 2.0、100+ 言語)
ollama pull qwen3-embedding:0.6b   # 埋め込み (MTEB multilingual #1 系列の軽量版)

# 3. .env で provider を切替
echo 'RAG_PROVIDER=ollama' >> .env

# 4. あとは同じ
uv run python -m examples.naive_rag
uv run python -m examples.generation.run
uv run python -m examples.evaluate    # Part 4 RAGAs (judge も Ollama に流れる)
```

**所要時間の目安 (free ≠ fast)**: Part 1-3 / 5 の単発クエリはローカル Ollama でも数秒で返ります。一方 Part 4 の `examples.evaluate` は 30 件 × 3 pipeline × 4 指標 = 360 回の構造化判定を回すバッチ処理で、ローカル Ollama では **~76 分**かかります (48 GB Mac でも同程度。後述のとおり RAM ではなく GPU コア / メモリ帯域律速)。反復検証中は `--limit 5` で代表サンプルだけ回すか、judge だけ高速な API 経路 (`RAG_PROVIDER` を default の `anthropic_openai` に戻すと judge = `gpt-4o-mini`) に切り替えると待ち時間を大きく減らせます。「0 円」は事実ですが「速い」とは別の話で、free 経路の Part 4 はバッチとして重い、と割り切ってください。

メモリ余力に合わせた tier (RAM はモデルが**収まるか**＝同時ロードできるかを決めるだけで、生成速度は GPU コア / メモリ帯域律速。RAM を増やしても単発生成は速くなりません):

| RAM | 生成 | 埋め込み | 判定 (Part 4) |
| --- | ---- | -------- | ------------- |
| **16 GB Mac (モデルが収まる最小構成)** | `qwen3:8b` | `qwen3-embedding:0.6b` | `qwen3:8b` (共用) |
| 32 GB+ | `qwen3:8b` | `qwen3-embedding:4b` | `qwen3:14b` (別ロードで self-preference 緩和) |
| 8 GB | `qwen3:4b` | `qwen3-embedding:0.6b` | `qwen3:4b` (共用) |

トレードオフ:

- Part 3 で扱う Anthropic Citations API は Anthropic 固有のため、Ollama 経路では構造的に再現できません (代わりに prompt-engineering 風 citation で代替)。記事本文の主張は Anthropic 経路で読み、Ollama 経路は「構造を体感する」用途に位置付けてください
- Part 4 で judge と generator が同一モデルになると self-preference バイアスが乗ります。記事 §「LLM-as-judge の良いところ・悪いところ」§「同型バイアス」がそのまま該当しますので、Ollama 経路で動かすと当該バイアスを **読者自身が実機で体感** できます

## Series articles (back-link)

- ハブ: <https://zerozawa.pages.dev/series/rag-fundamentals>
- Part 1: <https://zerozawa.pages.dev/posts/rag-naive-baseline>
- 以降は順次公開

## Tech stack

- Python 3.11+ / [uv](https://docs.astral.sh/uv/) (lockfile commit 済)
- LLM (default): [Anthropic Claude](https://www.anthropic.com/) (`anthropic` SDK)
- Embedding (default): [OpenAI text-embedding-3-small](https://platform.openai.com/docs/guides/embeddings)
- LLM/Embedding (free 代替): [Ollama](https://ollama.com/) + Qwen3 (`qwen3:8b` + `qwen3-embedding:0.6b`) — ADR 0003 参照
- BM25: [`rank-bm25`](https://github.com/dorianbrown/rank_bm25)
- Cross-encoder rerank: [`sentence-transformers`](https://www.sbert.net/)
- Eval (Part 4): [Ragas](https://docs.ragas.io/) 0.4 系 collections API
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
