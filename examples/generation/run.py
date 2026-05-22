"""Part 3 — generation pipeline runner.

End-to-end: Part 2 hybrid retrieval (top-20) → cross-encoder rerank
(top-3) → Anthropic Citations API with custom-content document blocks.

  uv run python -m examples.generation.run                 # default Q3 (mock OK)
  uv run python -m examples.generation.run --query "..."   # ad-hoc query
  uv run python -m examples.generation.run --observe-q3    # 3-stage rank diff for Q3 trap

The default invocation runs on Q3 (the trap query from Part 2) so the
chart values in the article can be reproduced.  Mock mode skips the API
calls and the model load — citations are not emitted in mock mode and
the runner says so explicitly.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Make src/ importable so `from rag.reranker import ...` works whether the
# user runs the module directly or via the smoke dispatcher. Mirrors the
# pattern used by `examples/retrieval/run.py` for the root-level `clients`.
REPO_ROOT = Path(__file__).resolve().parents[2]
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
RECALL_K = 20  # hybrid top-k fed into reranker
RERANK_K = 3  # final top-k surfaced to Citations API
DEFAULT_QUERY = "障害対応のエスカレーション基準を教えてください"
DEFAULT_MODEL = "claude-opus-4-7"
TRAP_DOC = "haruna-club-painting"  # Q3 trap from Part 2


@dataclass
class StageResult:
    """One row of the 3-stage rank diff used to validate the article's chart values."""

    stage: str
    trap_rank: int  # 1-indexed; 0 if absent from the inspected window
    top_chunks: list[str]


def _doc_of(chunk_id: str) -> str:
    return chunk_id.split("#", 1)[0]


def _index(mock: bool | None):
    """Load corpus, embed, build BM25 — same shape as examples.retrieval.run."""
    clients = get_clients(mock=mock)
    chunks = chunk_corpus(CORPUS_DIR)
    pairs = [(c.chunk_id, c.text) for c in chunks]
    chunk_matrix = embed_corpus(clients.embed, pairs)
    bm25 = build_bm25(pairs)
    return clients, chunks, chunk_matrix, bm25


def hybrid_top_k(
    query: str,
    chunks: list[ChunkNode],
    chunk_matrix,
    bm25,
    embed_client,
    *,
    filter_draft: bool,
    top_k: int,
) -> list[ChunkNode]:
    """Reproduce Part 2 hybrid+filter, return top_k chunks."""
    dense = dense_rank(embed_client, query, chunk_matrix)
    sparse = bm25_rank(query, bm25)
    fused = rrf_fuse([dense, sparse], k=60, top_k=len(chunks))
    if filter_draft:
        meta = [c.metadata for c in chunks]
        fused = apply_status_filter(fused, meta, exclude={"draft"})
    return [chunks[i] for i in fused[:top_k]]


def rerank_top_k(
    reranker, query: str, candidates: list[ChunkNode], *, top_k: int
) -> list[tuple[ChunkNode, float]]:
    pairs = [(c.chunk_id, c.text) for c in candidates]
    ranking = reranker.rerank(query, pairs, top_k=top_k)
    return [(candidates[i], score) for i, score in ranking]


def _trap_rank(chunks: list[ChunkNode]) -> int:
    """1-indexed rank of the first chunk belonging to TRAP_DOC; 0 if absent."""
    for i, c in enumerate(chunks):
        if _doc_of(c.chunk_id) == TRAP_DOC:
            return i + 1
    return 0


def _to_cited_chunks(reranked: list[tuple[ChunkNode, float]]) -> list[CitedChunk]:
    result: list[CitedChunk] = []
    for chunk, _score in reranked:
        ctx_parts = []
        if status := chunk.metadata.get("status"):
            ctx_parts.append(f"status={status}")
        if version := chunk.metadata.get("version"):
            ctx_parts.append(f"version={version}")
        result.append(
            CitedChunk(
                chunk_id=chunk.chunk_id,
                body=chunk.text,
                context=" ".join(ctx_parts),
            )
        )
    return result


def _format_response(response: Any) -> str:
    """Render Citations-API response to a readable transcript (mock or real)."""
    lines: list[str] = []
    blocks = getattr(response, "content", None)
    if blocks is None:
        # mock generate returns a plain string
        return str(response)
    for block in blocks:
        btype = getattr(block, "type", None)
        if btype == "text":
            text = getattr(block, "text", "")
            citations = getattr(block, "citations", None) or []
            if citations:
                cite_summary = "; ".join(
                    f"[{getattr(cit, 'document_title', '?')} @ {getattr(cit, 'start_block_index', '?')}-{getattr(cit, 'end_block_index', '?')}]"
                    for cit in citations
                )
                lines.append(f"{text}   ←{cite_summary}")
                for cit in citations:
                    snippet = getattr(cit, "cited_text", "")
                    if snippet:
                        lines.append(f"    cited_text: {snippet[:140]}...")
            else:
                lines.append(text)
    return "\n".join(lines)


def _call_anthropic(messages, *, model: str) -> Any:
    """Real API path. Imported lazily so --mock works without API keys."""
    import anthropic  # type: ignore[import-not-found]

    client = anthropic.Anthropic()
    return client.messages.create(
        model=model,
        max_tokens=1024,
        system="あなたはハルナ・テクノロジーズの社内ナレッジに精通したアシスタントです。documents のみを根拠に答え、事実主張ごとに引用してください。",
        messages=messages,
    )


def run_once(query: str, mock: bool | None, model: str) -> int:
    clients, chunks, chunk_matrix, bm25 = _index(mock)
    print(f"[corpus] {len({_doc_of(c.chunk_id) for c in chunks})} docs, {len(chunks)} chunks (mock={mock})")

    hybrid = hybrid_top_k(
        query, chunks, chunk_matrix, bm25, clients.embed, filter_draft=True, top_k=RECALL_K
    )
    print(f"\n[hybrid top-{RECALL_K}]")
    for i, c in enumerate(hybrid, 1):
        marker = "  *trap" if _doc_of(c.chunk_id) == TRAP_DOC else ""
        print(f"  {i:2d}. {c.chunk_id}{marker}")

    reranker = get_reranker(mock=mock)
    reranked = rerank_top_k(reranker, query, hybrid, top_k=RERANK_K)
    print(f"\n[rerank top-{RERANK_K}]")
    for i, (c, score) in enumerate(reranked, 1):
        print(f"  {i}. score={score:.4f}  {c.chunk_id}")

    cited = _to_cited_chunks(reranked)
    messages = build_messages(query, cited)

    print("\n[messages preview]")
    preview = json.dumps(
        [
            {
                "type": block["type"],
                **(
                    {
                        "title": block.get("title"),
                        "context": block.get("context", ""),
                        "n_blocks": len(block["source"]["content"]),
                        "citations_enabled": block["citations"]["enabled"],
                    }
                    if block["type"] == "document"
                    else {"text": block["text"][:80]}
                ),
            }
            for block in messages[0]["content"]
        ],
        ensure_ascii=False,
        indent=2,
    )
    print(preview)

    print("\n[answer]")
    if mock or os.getenv("RAG_MOCK", "").lower() in {"1", "true", "yes"}:
        # `clients.generate.generate` is the mock fallback (no citations in mock)
        flat_prompt = json.dumps(messages, ensure_ascii=False)
        answer = clients.generate.generate(flat_prompt, max_tokens=512)
        print(answer)
        print("\n[note] mock mode does not emit Citations API blocks. Run without --mock for real citations.")
    else:
        response = _call_anthropic(messages, model=model)
        print(_format_response(response))
    return 0


def observe_q3(mock: bool | None) -> int:
    """Reproduce the article's chart-01: trap_doc rank across 3 stages.

    Stage 1 (Part 1): dense-only, no filter.
    Stage 2 (Part 2): hybrid + draft filter.
    Stage 3 (Part 3): + cross-encoder rerank on a wide window (RECALL_K).
    """
    query = DEFAULT_QUERY
    clients, chunks, chunk_matrix, bm25 = _index(mock)

    dense = dense_rank(clients.embed, query, chunk_matrix)
    stage1 = [chunks[i] for i in dense[:RECALL_K]]

    stage2 = hybrid_top_k(
        query, chunks, chunk_matrix, bm25, clients.embed, filter_draft=True, top_k=RECALL_K
    )

    reranker = get_reranker(mock=mock)
    # Rerank the *entire* draft-filtered fused list to see where the trap lands.
    reranked = rerank_top_k(reranker, query, stage2, top_k=len(stage2))
    stage3 = [c for c, _score in reranked]

    results = [
        StageResult("Part 1: dense only", _trap_rank(stage1), [c.chunk_id for c in stage1[:5]]),
        StageResult("Part 2: hybrid+filter", _trap_rank(stage2), [c.chunk_id for c in stage2[:5]]),
        StageResult("Part 3: + cross-encoder rerank", _trap_rank(stage3), [c.chunk_id for c in stage3[:5]]),
    ]

    print(f"[observe-q3] query={query!r} mock={mock}")
    print(f"[observe-q3] trap_doc={TRAP_DOC} (lower rank = closer to the top; 0 = outside the inspected window of {RECALL_K})\n")
    print(f"{'Stage':<36} {'trap rank':>10}  top-5 chunks")
    for r in results:
        top5 = ", ".join(r.top_chunks) if r.top_chunks else "(empty)"
        print(f"{r.stage:<36} {r.trap_rank:>10}  {top5}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Part 3 — generation pipeline with Citations API.")
    parser.add_argument("--query", "-q", default=DEFAULT_QUERY, help="query for the generation pipeline")
    parser.add_argument("--mock", action="store_true", help="use mock clients and skip the cross-encoder model load")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="anthropic model id (real API only)")
    parser.add_argument(
        "--observe-q3",
        action="store_true",
        help="run the 3-stage rank-diff observation used by article chart-01 and exit (no LLM call)",
    )
    args = parser.parse_args()

    mock_flag = True if args.mock else None
    if args.observe_q3:
        return observe_q3(mock=mock_flag)
    return run_once(args.query, mock=mock_flag, model=args.model)


if __name__ == "__main__":
    sys.exit(main())
