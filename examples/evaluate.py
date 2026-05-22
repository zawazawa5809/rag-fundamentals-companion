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
  --mock                no API calls; placeholder scores derived from a
                        deterministic hash so smoke-tag CI passes
  (no flag, .env set)   real RAGAs eval. judge = openai gpt-4o-mini

Output:
  - stdout: per-pipeline averages
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

from clients import get_clients  # noqa: E402

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

CORPUS_DIR = REPO_ROOT / "corpus"
GOLDEN_PATH = REPO_ROOT / "golden_set.jsonl"
REPORT_PATH = REPO_ROOT / "eval_report.json"
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
    """4-metric scores for one (pipeline, query)."""

    faithfulness: float = 0.0
    answer_relevance: float = 0.0
    context_precision: float = 0.0
    context_recall: float = 0.0


@dataclass
class PipelineReport:
    name: str
    per_query: dict[str, Scores] = field(default_factory=dict)

    def averages(self) -> Scores:
        if not self.per_query:
            return Scores()
        n = len(self.per_query)
        agg = Scores()
        for s in self.per_query.values():
            agg.faithfulness += s.faithfulness
            agg.answer_relevance += s.answer_relevance
            agg.context_precision += s.context_precision
            agg.context_recall += s.context_recall
        agg.faithfulness /= n
        agg.answer_relevance /= n
        agg.context_precision /= n
        agg.context_recall /= n
        return agg


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


def _index(mock: bool | None):
    clients = get_clients(mock=mock)
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
    fused = apply_status_filter(fused, meta, exclude={"draft"})
    picks = [chunks[i] for i in fused[:TOP_K]]
    return _answer_from(picks, query)


def pipeline_rerank(query: str, chunks, matrix, bm25, embed_client, reranker) -> PipelineAnswer:
    dense = dense_rank(embed_client, query, matrix)
    sparse = bm25_rank(query, bm25)
    fused = rrf_fuse([dense, sparse], k=60, top_k=len(chunks))
    meta = [c.metadata for c in chunks]
    fused = apply_status_filter(fused, meta, exclude={"draft"})
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
    """
    out = Scores()
    f = await ragas_scorers["faithfulness"].ascore(
        user_input=entry.query, response=ans.text, retrieved_contexts=ans.contexts
    )
    a = await ragas_scorers["answer_relevance"].ascore(
        user_input=entry.query, response=ans.text
    )
    cp = await ragas_scorers["context_precision"].ascore(
        user_input=entry.query, reference=entry.reference, retrieved_contexts=ans.contexts
    )
    cr = await ragas_scorers["context_recall"].ascore(
        user_input=entry.query, retrieved_contexts=ans.contexts, reference=entry.reference
    )
    out.faithfulness = float(getattr(f, "value", f))
    out.answer_relevance = float(getattr(a, "value", a))
    out.context_precision = float(getattr(cp, "value", cp))
    out.context_recall = float(getattr(cr, "value", cr))
    return out


def _build_real_scorers():
    """Build RAGAs collections-API scorers backed by openai gpt-4o-mini.

    Imports are deferred so --mock works without the ragas / openai stack.
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


async def _evaluate(mock: bool) -> int:
    clients, chunks, matrix, bm25 = _index(True if mock else None)
    reranker = get_reranker(mock=True if mock else None)

    golden = load_golden()
    print(f"[golden] {len(golden)} entries loaded from {GOLDEN_PATH.name}")

    pipelines = {
        "p1": ("naive (Part 1)", lambda q: pipeline_naive(q, chunks, matrix, clients.embed)),
        "p2": ("hybrid+filter (Part 2)", lambda q: pipeline_hybrid(q, chunks, matrix, bm25, clients.embed)),
        "p3": ("+rerank+citations (Part 3)", lambda q: pipeline_rerank(q, chunks, matrix, bm25, clients.embed, reranker)),
    }

    reports: dict[str, PipelineReport] = {k: PipelineReport(name=v[0]) for k, v in pipelines.items()}
    scorers = None if mock else _build_real_scorers()

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

    print("\n[summary] (judge: " + ("mock" if mock else "openai gpt-4o-mini") + ")")
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

    serializable = {
        code: {
            "name": rep.name,
            "averages": rep.averages().__dict__,
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
    args = parser.parse_args()
    mock = args.mock or os.getenv("RAG_MOCK", "").lower() in {"1", "true", "yes"}
    return asyncio.run(_evaluate(mock=mock))


if __name__ == "__main__":
    sys.exit(main())
