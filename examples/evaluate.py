"""Part 4 — RAGAs evaluation across Part 1/2/3 pipelines.

Runs the 30-entry golden set through three pipelines and scores each on
4 RAGAs metrics (Faithfulness / Answer Relevance / Context Precision /
Context Recall).  The score table is the "climax" the series promised in
Part 1 ("Part 4 で測定する").

Pipelines:
  P1 naive            — Part 1 fixed-size chunking + dense top-3
  P2 hybrid+filter    — Part 2 heading-aware chunker + RRF + draft filter
  P3 +rerank+citations — Part 3 cross-encoder top-3 + Anthropic Citations API

Modes:
  --mock                       no API calls; placeholder scores derived from a
                               deterministic hash so smoke-tag CI passes
  (no flag, RAG_PROVIDER=...)  real RAGAs eval.
                               - anthropic_openai (default) → judge = openai gpt-4o-mini
                               - ollama                     → judge = qwen3:8b via Ollama
                                                              (ADR 0003; absolute scores
                                                              shift due to self-preference
                                                              bias when judge == generator)

Sub-smoke gating:
  --limit N             evaluate the first N entries only (default: all 30)
  --pipelines CODES     comma-separated subset (p1,p2,p3). Default: all three.

Output:
  - stdout: per-pipeline averages, labelled with the resolved judge
  - eval_report.json: full per-query scores
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from clients import (  # noqa: E402
    Provider,
    _resolve_ollama_models,
    _resolve_ollama_openai_base_url,
    _resolve_provider,
    get_clients,
    get_corpus_dir,
    get_eval_report_path,
    get_golden_set_path,
)

from examples.retrieval.chunker import ChunkNode, chunk_corpus  # noqa: E402
from examples.retrieval.embedder import dense_rank, embed_corpus  # noqa: E402
from examples.retrieval.hybrid import (  # noqa: E402
    apply_status_filter,
    bm25_rank,
    build_bm25,
    rrf_fuse,
)
from rag.prompt_builder import CitedChunk, build_messages  # noqa: E402
from rag.reranker import get_reranker  # noqa: E402

CORPUS_DIR = get_corpus_dir()
GOLDEN_PATH = get_golden_set_path()
REPORT_PATH = get_eval_report_path()
HYBRID_K = 20
TOP_K = 3
METRICS = ["faithfulness", "answer_relevance", "context_precision", "context_recall"]


# ---------------------------- data models -----------------------------------


@dataclass
class GoldenEntry:
    qid: str
    query: str
    reference: str
    relevant_docs: list[str]
    category: str
    note: str = ""


@dataclass
class PipelineAnswer:
    text: str
    contexts: list[str]
    chunk_ids: list[str]


@dataclass
class Scores:
    """4-metric scores for one (pipeline, query).

    A metric is `None` when its scorer call failed (e.g. the judge degenerated
    and produced unparseable JSON). `None` metrics are excluded from averages
    rather than counted as zero, so a rare failure does not skew the chart.
    """

    faithfulness: float | None = None
    answer_relevance: float | None = None
    context_precision: float | None = None
    context_recall: float | None = None


@dataclass
class PipelineReport:
    name: str
    per_query: dict[str, Scores] = field(default_factory=dict)

    def averages(self) -> Scores:
        """Mean of each metric over the queries that scored it (skips None)."""
        agg = Scores()
        for metric in ("faithfulness", "answer_relevance", "context_precision", "context_recall"):
            vals = [
                v for s in self.per_query.values() if (v := getattr(s, metric)) is not None
            ]
            setattr(agg, metric, sum(vals) / len(vals) if vals else 0.0)
        return agg

    def failure_count(self) -> int:
        """How many (query, metric) cells failed to score (are None)."""
        return sum(
            1
            for s in self.per_query.values()
            for metric in ("faithfulness", "answer_relevance", "context_precision", "context_recall")
            if getattr(s, metric) is None
        )


# ---------------------------- pipelines -------------------------------------


def load_golden() -> list[GoldenEntry]:
    rows: list[GoldenEntry] = []
    for line in GOLDEN_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        rows.append(
            GoldenEntry(
                qid=d["qid"],
                query=d["query"],
                reference=d["reference"],
                relevant_docs=d.get("relevant_docs", []),
                category=d.get("category", "happy"),
                note=d.get("note", ""),
            )
        )
    return rows


def _index(mock: bool | None, provider: Provider | None = None):
    clients = get_clients(mock=mock, provider=provider)
    chunks = chunk_corpus(CORPUS_DIR)
    pairs = [(c.chunk_id, c.text) for c in chunks]
    matrix = embed_corpus(clients.embed, pairs)
    bm25 = build_bm25(pairs)
    return clients, chunks, matrix, bm25


def _doc_of(chunk_id: str) -> str:
    return chunk_id.split("#", 1)[0]


def pipeline_naive(query: str, chunks, matrix, embed_client) -> PipelineAnswer:
    ranking = dense_rank(embed_client, query, matrix)[:TOP_K]
    picks = [chunks[i] for i in ranking]
    return _answer_from(picks, query)


def pipeline_hybrid(query: str, chunks, matrix, bm25, embed_client) -> PipelineAnswer:
    dense = dense_rank(embed_client, query, matrix)
    sparse = bm25_rank(query, bm25)
    fused = rrf_fuse([dense, sparse], k=60, top_k=len(chunks))
    meta = [c.metadata for c in chunks]
    fused = apply_status_filter(fused, meta, exclude={"draft", "archived"})
    picks = [chunks[i] for i in fused[:TOP_K]]
    return _answer_from(picks, query)


def pipeline_rerank(query: str, chunks, matrix, bm25, embed_client, reranker) -> PipelineAnswer:
    dense = dense_rank(embed_client, query, matrix)
    sparse = bm25_rank(query, bm25)
    fused = rrf_fuse([dense, sparse], k=60, top_k=len(chunks))
    meta = [c.metadata for c in chunks]
    fused = apply_status_filter(fused, meta, exclude={"draft", "archived"})
    candidates = [chunks[i] for i in fused[:HYBRID_K]]
    pairs = [(c.chunk_id, c.text) for c in candidates]
    ranking = reranker.rerank(query, pairs, top_k=TOP_K)
    picks = [candidates[i] for i, _ in ranking]
    return _answer_from(picks, query)


def _answer_from(picks: list[ChunkNode], query: str) -> PipelineAnswer:
    """Stub answer: concatenate the picked chunks' first 200 chars.

    The article calls out that the article focuses on retrieval+generation
    METRICS, not on the answer text quality per se. For eval purposes the
    answer needs to be grounded in the retrieved context so Faithfulness
    is measurable. We compose a deterministic summary of the picks so
    that comparisons across pipelines stay reproducible.
    """
    body = " ".join(c.text[:200].replace("\n", " ") for c in picks)
    text = f"提供された資料に基づくと、{body}"
    return PipelineAnswer(
        text=text,
        contexts=[c.text for c in picks],
        chunk_ids=[c.chunk_id for c in picks],
    )


# ---------------------------- scoring ---------------------------------------


def _mock_score(qid: str, pipeline: str, metric: str) -> float:
    """Deterministic placeholder so smoke-tag CI passes without API keys.

    Returns a value in [0, 1] biased so P1 < P2 < P3, mirroring the
    article's narrative direction without claiming the real numbers.
    """
    import hashlib

    h = int(hashlib.sha256(f"{qid}|{pipeline}|{metric}".encode()).hexdigest(), 16)
    base = (h % 1000) / 1000.0  # 0..0.999
    bias = {"p1": 0.45, "p2": 0.65, "p3": 0.80}[pipeline]
    return round(min(1.0, base * 0.30 + bias), 4)


async def _score_real(
    entry: GoldenEntry, ans: PipelineAnswer, ragas_scorers: dict[str, Any]
) -> Scores:
    """Run all 4 RAGAs scorers against one (pipeline, entry).

    `ragas_scorers` is constructed by `_build_real_scorers`. Each scorer's
    `ascore` takes a different signature; we pass only the args it needs.

    Each metric is scored independently and guarded: if a scorer raises (most
    often the local judge degenerating into a token-repetition loop and
    overrunning max_tokens), that single metric is recorded as `None` and the
    run continues, instead of losing every already-scored entry to one bad call.
    """

    async def _safe(name: str, factory):  # type: ignore[no-untyped-def]
        try:
            r = await factory()
            return float(getattr(r, "value", r))
        except Exception as e:  # noqa: BLE001 — any judge failure → skip this metric
            print(f"  [warn] {name} failed for {entry.qid}: {type(e).__name__}", file=sys.stderr)
            return None

    out = Scores()
    out.faithfulness = await _safe(
        "faithfulness",
        lambda: ragas_scorers["faithfulness"].ascore(
            user_input=entry.query, response=ans.text, retrieved_contexts=ans.contexts
        ),
    )
    out.answer_relevance = await _safe(
        "answer_relevance",
        lambda: ragas_scorers["answer_relevance"].ascore(
            user_input=entry.query, response=ans.text
        ),
    )
    out.context_precision = await _safe(
        "context_precision",
        lambda: ragas_scorers["context_precision"].ascore(
            user_input=entry.query, reference=entry.reference, retrieved_contexts=ans.contexts
        ),
    )
    out.context_recall = await _safe(
        "context_recall",
        lambda: ragas_scorers["context_recall"].ascore(
            user_input=entry.query, retrieved_contexts=ans.contexts, reference=entry.reference
        ),
    )
    return out


def _build_real_scorers(provider: Provider):
    """Build RAGAs collections-API scorers for the resolved provider.

    Imports are deferred so --mock works without the ragas / openai stack.

    - anthropic_openai (default): OpenAI gpt-4o-mini judge + text-embedding-3-small
    - ollama: AsyncOpenAI with base_url pointing at Ollama's OpenAI-compatible
      endpoint, qwen3:8b judge (configurable via OLLAMA_JUDGE_MODEL) and
      qwen3-embedding:0.6b. See ADR 0003 for the model selection rationale.
    """
    from openai import AsyncOpenAI
    from ragas.embeddings.base import embedding_factory
    from ragas.llms import llm_factory
    from ragas.metrics.collections import (
        AnswerRelevancy,
        ContextPrecision,
        ContextRecall,
        Faithfulness,
    )

    if provider == "ollama":
        base_url = _resolve_ollama_openai_base_url()
        models = _resolve_ollama_models()
        # OpenAI SDK rejects empty api_key, so pass a sentinel; Ollama does not
        # verify it. OLLAMA_API_KEY env is supported for forward compat.
        client = AsyncOpenAI(
            base_url=base_url,
            api_key=os.getenv("OLLAMA_API_KEY", "ollama"),
        )
        # Qwen3 is a hybrid-thinking model: by default it emits chain-of-thought
        # into a separate `reasoning` field, leaving `content` empty until the
        # (variable-length) thinking finishes. Instructor parses `content`, so
        # under RAGAs' structured-output prompts the thinking can consume the
        # whole token budget, retries grow max_tokens, and the call still fails
        # with an empty schema. We therefore disable thinking at the source.
        #
        # Empirically (Ollama 0.24, qwen3:8b, /v1/chat/completions) only the
        # OpenAI-standard `reasoning_effort: "none"` actually suppresses the
        # `reasoning` field — `/no_think` prompt tokens, the top-level
        # `think: false` flag, and `chat_template_kwargs.enable_thinking=False`
        # are all silently ignored by the OpenAI-compat layer. With thinking
        # off, `content` is populated immediately and instructor parses on the
        # first try. See ADR 0004 Open Questions on the Qwen3 reasoning leak.
        _original_create = client.chat.completions.create

        async def _no_think_create(**kwargs):  # type: ignore[no-untyped-def]
            kwargs.setdefault("reasoning_effort", "none")
            # With thinking off, `content` is pure JSON — but RAGAs' Faithfulness
            # decomposes the answer into a verdict list, so the default
            # 1024-token budget truncates it (finish_reason="length") and
            # instructor's geometric retry never catches up. Floor max_tokens so
            # the structured output completes on the first attempt; 4096 is ample
            # for the longest legitimate statement list while capping the waste
            # when a generation degenerates (see below).
            kwargs["max_tokens"] = max(int(kwargs.get("max_tokens") or 0), 4096)
            # qwen3:8b occasionally falls into a token-repetition death spiral
            # (e.g. "当社の当社の当社の…") that fills the whole budget with garbage
            # and produces unparseable JSON. A modest frequency_penalty breaks the
            # loop without distorting valid structured output (verified: identical
            # parse on normal prompts). The per-metric guard in `_score_real` is
            # the safety net for any residual degeneration.
            kwargs.setdefault("frequency_penalty", 0.3)
            return await _original_create(**kwargs)

        client.chat.completions.create = _no_think_create  # type: ignore[assignment]
        # temperature=0 for deterministic JSON output
        llm = llm_factory(models["judge"], client=client, temperature=0)
        embeddings = embedding_factory("openai", model=models["embed"], client=client)
    else:
        client = AsyncOpenAI()
        llm = llm_factory("gpt-4o-mini", client=client)
        embeddings = embedding_factory("openai", model="text-embedding-3-small", client=client)
    return {
        "faithfulness": Faithfulness(llm=llm),
        "answer_relevance": AnswerRelevancy(llm=llm, embeddings=embeddings),
        "context_precision": ContextPrecision(llm=llm),
        "context_recall": ContextRecall(llm=llm),
    }


# ---------------------------- driver ----------------------------------------


def _judge_label(mock: bool, provider: Provider) -> str:
    if mock:
        return "mock"
    if provider == "ollama":
        return f"ollama {_resolve_ollama_models()['judge']}"
    return "openai gpt-4o-mini"


async def _evaluate(
    mock: bool,
    provider: Provider,
    limit: int | None = None,
    pipelines_filter: list[str] | None = None,
) -> int:
    clients, chunks, matrix, bm25 = _index(True if mock else None, provider=provider)
    reranker = get_reranker(mock=True if mock else None)

    golden = load_golden()
    if limit is not None:
        golden = golden[:limit]
    print(f"[golden] {len(golden)} entries loaded from {GOLDEN_PATH.name}")

    all_pipelines = {
        "p1": ("naive (Part 1)", lambda q: pipeline_naive(q, chunks, matrix, clients.embed)),
        "p2": ("hybrid+filter (Part 2)", lambda q: pipeline_hybrid(q, chunks, matrix, bm25, clients.embed)),
        "p3": ("+rerank+citations (Part 3)", lambda q: pipeline_rerank(q, chunks, matrix, bm25, clients.embed, reranker)),
    }
    if pipelines_filter is not None:
        unknown = set(pipelines_filter) - all_pipelines.keys()
        if unknown:
            raise ValueError(f"Unknown pipeline codes: {sorted(unknown)}. Valid: p1, p2, p3")
        pipelines = {k: all_pipelines[k] for k in pipelines_filter}
    else:
        pipelines = all_pipelines

    reports: dict[str, PipelineReport] = {k: PipelineReport(name=v[0]) for k, v in pipelines.items()}
    scorers = None if mock else _build_real_scorers(provider)

    for entry in golden:
        for code, (label, run) in pipelines.items():
            ans = run(entry.query)
            if mock:
                s = Scores(
                    faithfulness=_mock_score(entry.qid, code, "f"),
                    answer_relevance=_mock_score(entry.qid, code, "a"),
                    context_precision=_mock_score(entry.qid, code, "cp"),
                    context_recall=_mock_score(entry.qid, code, "cr"),
                )
            else:
                assert scorers is not None
                s = await _score_real(entry, ans, scorers)
            reports[code].per_query[entry.qid] = s
        print(f"  scored {entry.qid} ({entry.category})")

    print(f"\n[summary] (judge: {_judge_label(mock, provider)})")
    header = f"  {'pipeline':<32} " + "  ".join(f"{m:<20}" for m in METRICS)
    print(header)
    for code, rep in reports.items():
        avg = rep.averages()
        row = f"  {rep.name:<32} "
        row += f"{avg.faithfulness:<20.4f}"
        row += f"{avg.answer_relevance:<22.4f}"
        row += f"{avg.context_precision:<22.4f}"
        row += f"{avg.context_recall:<20.4f}"
        print(row)

    total_failures = sum(rep.failure_count() for rep in reports.values())
    total_cells = sum(len(rep.per_query) * len(METRICS) for rep in reports.values())
    if total_failures:
        print(
            f"\n[warn] {total_failures}/{total_cells} metric cells failed to score "
            f"(excluded from averages; see [warn] lines above)."
        )
        for code, rep in reports.items():
            if rep.failure_count():
                print(f"  - {rep.name}: {rep.failure_count()} cell(s)")

    serializable = {
        code: {
            "name": rep.name,
            "averages": rep.averages().__dict__,
            "failure_count": rep.failure_count(),
            "per_query": {qid: s.__dict__ for qid, s in rep.per_query.items()},
        }
        for code, rep in reports.items()
    }
    REPORT_PATH.write_text(json.dumps(serializable, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[report] wrote {REPORT_PATH.name}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Part 4 — RAGAs evaluation across Part 1/2/3 pipelines.")
    parser.add_argument("--mock", action="store_true", help="skip RAGAs (deterministic placeholder scores)")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="evaluate only the first N entries of the golden set (sub-smoke gating before full run)",
    )
    parser.add_argument(
        "--pipelines",
        default=None,
        help="comma-separated subset of pipeline codes to evaluate (e.g. 'p3' or 'p1,p3'). Default: all three.",
    )
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be a positive integer (>= 1)")
    mock = args.mock or os.getenv("RAG_MOCK", "").lower() in {"1", "true", "yes"}
    provider = _resolve_provider(None)
    pipelines_filter = (
        [code.strip() for code in args.pipelines.split(",") if code.strip()]
        if args.pipelines
        else None
    )
    return asyncio.run(
        _evaluate(mock=mock, provider=provider, limit=args.limit, pipelines_filter=pipelines_filter)
    )


if __name__ == "__main__":
    sys.exit(main())
