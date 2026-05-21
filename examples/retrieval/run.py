"""Part 2 — retrieval pipeline runner.

Compares Part 1 baseline (dense top-k) against Part 2 (metadata-preserving
chunking + BM25/dense hybrid via RRF + optional status filter) on three
illustrative queries from the corpus.

  uv run python -m examples.retrieval.run                # full eval (mock OK)
  uv run python -m examples.retrieval.run --query "..."  # ad-hoc query
  uv run python -m examples.retrieval.run --no-filter    # disable status filter

The --mock mode uses deterministic stub clients (no API keys needed) so the
script always exits 0 on CI. Real numbers require API credentials and are
reported by the runner in the same format.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from clients import get_clients

from examples.retrieval.chunker import ChunkNode, chunk_corpus
from examples.retrieval.embedder import dense_rank, embed_corpus
from examples.retrieval.hybrid import apply_status_filter, bm25_rank, build_bm25, rrf_fuse

CORPUS_DIR = Path(__file__).resolve().parents[2] / "corpus"
TOP_K = 5

GOLDEN = [
    {
        "qid": "Q1",
        "query": "Stratus の認証は現行どう動いている？",
        "relevant_docs": {"stratus-architecture-v3", "stratus-postmortem-2024-06"},
        "note": "現行 (v3) の Auth Service 設計と、過去 post-mortem の Auth 言及。draft は未承認のため非 relevant",
    },
    {
        "qid": "Q2",
        "query": "テレワーク手当はいくら？",
        "relevant_docs": {"haruna-remote-work"},
        "note": "corpus は「リモートワーク」「在宅勤務」表記。query 側「テレワーク」は corpus 未収語 — dense の意味類似 + BM25 の手当表層で hybrid 効果が見える",
    },
    {
        "qid": "Q3",
        "query": "障害対応のエスカレーション基準を教えてください",
        "relevant_docs": {"haruna-incident-flow"},
        "note": "trap (お絵描き同好会の Next Action 構造) を hybrid で押し出せるか",
    },
]


def doc_of(chunk_id: str) -> str:
    return chunk_id.split("#", 1)[0]


def recall_at_k(retrieved_chunks: list[ChunkNode], relevant_docs: set[str]) -> float:
    retrieved_docs = {doc_of(c.chunk_id) for c in retrieved_chunks}
    hit = retrieved_docs & relevant_docs
    return len(hit) / max(len(relevant_docs), 1)


def baseline_dense(query: str, chunks: list[ChunkNode], chunk_matrix, embed_client) -> list[ChunkNode]:
    ranking = dense_rank(embed_client, query, chunk_matrix)
    return [chunks[i] for i in ranking[:TOP_K]]


def part2_hybrid(
    query: str,
    chunks: list[ChunkNode],
    chunk_matrix,
    bm25,
    embed_client,
    *,
    filter_draft: bool,
) -> list[ChunkNode]:
    dense = dense_rank(embed_client, query, chunk_matrix)
    sparse = bm25_rank(query, bm25)
    # Fuse the full ranking, then filter, then slice — otherwise draft chunks
    # in the head can starve the top-K of active candidates.
    fused = rrf_fuse([dense, sparse], k=60, top_k=len(chunks))
    if filter_draft:
        meta = [c.metadata for c in chunks]
        fused = apply_status_filter(fused, meta, exclude={"draft"})
    return [chunks[i] for i in fused[:TOP_K]]


def fmt_chunks(chunks: list[ChunkNode]) -> str:
    return "\n".join(
        f"    {c.chunk_id}  status={(c.metadata.get('status') or '-'):<6} version={c.metadata.get('version')}"
        for c in chunks
    )


def _index(mock: bool | None):
    """Load corpus, embed it, and build the BM25 index once."""
    clients = get_clients(mock=mock)
    chunks = chunk_corpus(CORPUS_DIR)
    pairs = [(c.chunk_id, c.text) for c in chunks]
    chunk_matrix = embed_corpus(clients.embed, pairs)
    bm25 = build_bm25(pairs)
    return clients, chunks, chunk_matrix, bm25


def evaluate(filter_draft: bool, mock: bool | None) -> int:
    clients, chunks, chunk_matrix, bm25 = _index(mock)
    print(f"[corpus] {len({doc_of(c.chunk_id) for c in chunks})} docs, {len(chunks)} chunks (filter_draft={filter_draft}, mock={mock})\n")

    avg_b, avg_h = 0.0, 0.0
    for item in GOLDEN:
        baseline = baseline_dense(item["query"], chunks, chunk_matrix, clients.embed)
        hybrid = part2_hybrid(item["query"], chunks, chunk_matrix, bm25, clients.embed, filter_draft=filter_draft)
        rb = recall_at_k(baseline, item["relevant_docs"])
        rh = recall_at_k(hybrid, item["relevant_docs"])
        avg_b += rb
        avg_h += rh
        print(f"[{item['qid']}] {item['query']}")
        print(f"  baseline (dense)  Recall@{TOP_K}={rb:.2f}")
        print(fmt_chunks(baseline))
        print(f"  hybrid+filter     Recall@{TOP_K}={rh:.2f}")
        print(fmt_chunks(hybrid))
        print()
    n = len(GOLDEN)
    print(f"[summary] avg Recall@{TOP_K}  baseline={avg_b / n:.2f}  hybrid={avg_h / n:.2f}")
    return 0


def ad_hoc(query: str, filter_draft: bool, mock: bool | None) -> int:
    clients, chunks, chunk_matrix, bm25 = _index(mock)
    hybrid = part2_hybrid(query, chunks, chunk_matrix, bm25, clients.embed, filter_draft=filter_draft)
    print(f"[query] {query}")
    print(fmt_chunks(hybrid))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Part 2 — hybrid retrieval evaluation.")
    parser.add_argument("--query", "-q", help="Run a single ad-hoc query (skips golden set evaluation).")
    parser.add_argument("--no-filter", action="store_true", help="Disable status=draft filtering.")
    parser.add_argument("--mock", action="store_true", help="Use mock embedding client (no API keys). Without this flag, RAG_MOCK env is honored.")
    args = parser.parse_args()

    filter_draft = not args.no_filter
    mock_flag = True if args.mock else None
    if args.query:
        return ad_hoc(args.query, filter_draft=filter_draft, mock=mock_flag)
    return evaluate(filter_draft=filter_draft, mock=mock_flag)


if __name__ == "__main__":
    sys.exit(main())
