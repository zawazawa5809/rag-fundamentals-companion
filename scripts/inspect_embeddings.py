"""ADR 0004 Phase 2 — corpus v2 embedding behaviour inspection.

Runs the active corpus through one or both embedding models
(OpenAI text-embedding-3-small / Ollama qwen3-embedding:0.6b), produces
chunk × query cos similarity matrices and per-query doc-level trap rank
reports, and verifies that repeated runs are deterministic.

Used during Phase 2 iterative tuning to confirm that:
  - genuine docs surface in the top ranks for happy queries
  - trap docs (surface / semantic / stale) appear at the predicted depths
  - results are stable across multiple runs (embedding determinism check)

Usage::

  uv run python -m scripts.inspect_embeddings                   # both models
  uv run python -m scripts.inspect_embeddings --models ollama   # Ollama only
  uv run python -m scripts.inspect_embeddings --corpus-version v1
  uv run python -m scripts.inspect_embeddings --queries path/to/queries.jsonl

Outputs (key-sorted JSON, 2-space indent):

  output/inspect/v2/similarity_matrix.<model>.json
  output/inspect/v2/trap_rank_report.<model>.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from clients import (  # noqa: E402
    CorpusVersion,
    _resolve_corpus_version,
    get_clients,
    get_corpus_dir,
)

from examples.retrieval.chunker import chunk_corpus  # noqa: E402

# Maps the CLI shorthand to (provider name, embedding model id) for reporting.
MODEL_REGISTRY: dict[str, tuple[str, str]] = {
    "openai": ("anthropic_openai", "text-embedding-3-small"),
    "ollama": ("ollama", "qwen3-embedding:0.6b"),
}

DEFAULT_OUTPUT_DIR = REPO_ROOT / "output" / "inspect"
DEFAULT_RUNS = 3


def _rel(p: Path) -> str:
    """Display path relative to REPO_ROOT when possible, else absolute."""
    try:
        return str(p.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(p)
TOP_K_REPORT = 20  # how many ranked docs to surface per query in the trap report


@dataclass
class QueryEntry:
    qid: str
    query: str
    relevant_docs: list[str] = field(default_factory=list)
    trap_docs: list[str] = field(default_factory=list)
    category: str = "happy"


def _default_queries_path(corpus_version: CorpusVersion) -> Path:
    """Prefer the completed golden_set.jsonl; fall back to Phase 2 draft_queries.jsonl."""
    if corpus_version == "v1":
        return REPO_ROOT / "golden_set.jsonl"
    base = REPO_ROOT / "corpus" / corpus_version
    golden = base / "golden_set.jsonl"
    if golden.is_file():
        return golden
    return base / "draft_queries.jsonl"


def load_queries(path: Path) -> list[QueryEntry]:
    if not path.is_file():
        raise FileNotFoundError(
            f"Queries file not found: {path}. "
            f"Provide --queries or create draft_queries.jsonl in the corpus dir."
        )
    out: list[QueryEntry] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        row = json.loads(raw)
        out.append(
            QueryEntry(
                qid=row["qid"],
                query=row["query"],
                relevant_docs=row.get("relevant_docs", []),
                trap_docs=row.get("trap_docs", []),
                category=row.get("category", "happy"),
            )
        )
    return out


def doc_slug_of(chunk_id: str) -> str:
    return chunk_id.split("#", 1)[0]


def cos_sim(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Compute row-wise cosine sim between matrix `a` (M,d) and vector `b` (d,)."""
    a_norm = np.linalg.norm(a, axis=1) + 1e-9
    b_norm = np.linalg.norm(b) + 1e-9
    return (a @ b) / (a_norm * b_norm)


def embed_chunks(client_embed, chunks: list[tuple[str, str]], batch: int = 64) -> np.ndarray:
    """Embed all chunk texts. Returns (n_chunks, d) float32 matrix."""
    vectors: list[list[float]] = []
    for start in range(0, len(chunks), batch):
        batch_texts = [t for _id, t in chunks[start : start + batch]]
        vectors.extend(client_embed.embed(batch_texts))
    return np.array(vectors, dtype=np.float32)


def embed_query(client_embed, text: str) -> np.ndarray:
    return np.array(client_embed.embed([text])[0], dtype=np.float32)


def doc_ranks_from_chunk_sims(
    chunk_ids: list[str], chunk_sims: np.ndarray
) -> list[tuple[str, float]]:
    """Aggregate chunk-level sims to doc-level (best chunk wins). Returns ranked list desc."""
    best: dict[str, float] = {}
    for chunk_id, sim in zip(chunk_ids, chunk_sims):
        slug = doc_slug_of(chunk_id)
        if slug not in best or sim > best[slug]:
            best[slug] = float(sim)
    return sorted(best.items(), key=lambda kv: kv[1], reverse=True)


def run_model(
    model_key: str,
    corpus_version: CorpusVersion,
    queries: list[QueryEntry],
    runs: int,
    output_dir: Path,
) -> dict[str, Any]:
    """Embed corpus + queries with one model, write per-model artifacts, return summary."""
    provider, model_id = MODEL_REGISTRY[model_key]
    print(f"\n=== {model_key} ({provider}: {model_id}) ===", file=sys.stderr)

    clients = get_clients(provider=provider)  # raises on missing keys / Ollama down
    corpus_dir = get_corpus_dir(version=corpus_version)
    nodes = chunk_corpus(corpus_dir)
    chunks = [(n.chunk_id, n.text) for n in nodes]
    chunk_ids = [cid for cid, _ in chunks]
    print(
        f"chunks: {len(chunks)} from {_rel(corpus_dir)}",
        file=sys.stderr,
    )

    chunk_matrix = embed_chunks(clients.embed, chunks)
    print(f"chunk embeddings shape: {chunk_matrix.shape}", file=sys.stderr)

    sim_payload: dict[str, Any] = {
        "model": model_id,
        "provider": provider,
        "corpus_version": corpus_version,
        "n_chunks": len(chunks),
        "queries": {},
    }
    rank_payload: dict[str, Any] = {
        "model": model_id,
        "provider": provider,
        "corpus_version": corpus_version,
        "runs_compared": runs,
        "queries": {},
    }

    all_consistent = True

    for q in queries:
        # Embed query `runs` times, compare ranks for determinism.
        per_run_ranks: list[list[str]] = []
        last_sims: np.ndarray | None = None
        for _ in range(runs):
            qvec = embed_query(clients.embed, q.query)
            sims = cos_sim(chunk_matrix, qvec)
            doc_ranked = doc_ranks_from_chunk_sims(chunk_ids, sims)
            per_run_ranks.append([slug for slug, _s in doc_ranked])
            last_sims = sims

        # Determinism: every run should yield the same doc rank ordering.
        consistent = all(r == per_run_ranks[0] for r in per_run_ranks[1:])
        if not consistent:
            all_consistent = False
            print(
                f"[warn] qid={q.qid} ranks differ across {runs} runs",
                file=sys.stderr,
            )

        assert last_sims is not None
        doc_ranked = doc_ranks_from_chunk_sims(chunk_ids, last_sims)
        doc_ranks_map = {slug: i + 1 for i, (slug, _s) in enumerate(doc_ranked)}

        # similarity matrix payload — record top-K per query to keep file size bounded.
        chunk_sim_pairs = sorted(
            ((cid, float(s)) for cid, s in zip(chunk_ids, last_sims)),
            key=lambda kv: kv[1],
            reverse=True,
        )[:TOP_K_REPORT]
        sim_payload["queries"][q.qid] = {
            "query": q.query,
            "category": q.category,
            "top_chunks": dict(chunk_sim_pairs),
        }

        relevant_top = (
            min((doc_ranks_map.get(d, 9999) for d in q.relevant_docs), default=None)
            if q.relevant_docs
            else None
        )
        trap_ranks = {d: doc_ranks_map.get(d, 0) for d in q.trap_docs}

        rank_payload["queries"][q.qid] = {
            "query": q.query,
            "category": q.category,
            "relevant_docs": q.relevant_docs,
            "trap_docs": q.trap_docs,
            "relevant_top_rank": relevant_top,
            "trap_ranks": trap_ranks,
            "doc_ranks": dict(list(doc_ranks_map.items())[:TOP_K_REPORT]),
            "consistent_across_runs": consistent,
        }

    rank_payload["all_runs_consistent"] = all_consistent

    output_dir.mkdir(parents=True, exist_ok=True)
    sim_path = output_dir / f"similarity_matrix.{model_key}.json"
    rank_path = output_dir / f"trap_rank_report.{model_key}.json"
    sim_path.write_text(json.dumps(sim_payload, ensure_ascii=False, indent=2, sort_keys=True))
    rank_path.write_text(json.dumps(rank_payload, ensure_ascii=False, indent=2, sort_keys=True))
    print(f"wrote {_rel(sim_path)}", file=sys.stderr)
    print(f"wrote {_rel(rank_path)}", file=sys.stderr)

    summarize_to_stdout(model_key, rank_payload)
    return rank_payload


def summarize_to_stdout(model_key: str, rank_payload: dict[str, Any]) -> None:
    """Print a one-line per query summary so iterative tuning is fast."""
    print(f"\n--- {model_key} summary ---")
    print(f"{'qid':<6}{'category':<8}{'relevant_top':<14}trap_ranks")
    for qid, qd in rank_payload["queries"].items():
        rt = qd["relevant_top_rank"] if qd["relevant_top_rank"] else "—"
        trap_repr = ", ".join(f"{d}={r if r else 'OOR'}" for d, r in qd["trap_ranks"].items()) or "—"
        print(f"{qid:<6}{qd['category']:<8}{str(rt):<14}{trap_repr}")
    if not rank_payload.get("all_runs_consistent", True):
        print(f"  ⚠ {model_key}: ranks were NOT identical across runs")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--corpus-version",
        choices=["v1", "v2"],
        default=None,
        help="override RAG_CORPUS_VERSION (default: env or v2)",
    )
    parser.add_argument(
        "--models",
        default="openai,ollama",
        help="comma-separated subset of {openai,ollama}; default: both",
    )
    parser.add_argument(
        "--queries",
        type=Path,
        default=None,
        help="path to a queries jsonl file (default: corpus/<ver>/draft_queries.jsonl)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=DEFAULT_RUNS,
        help=f"number of times to re-embed each query for determinism check (default: {DEFAULT_RUNS})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help=f"output dir; default: {DEFAULT_OUTPUT_DIR.relative_to(REPO_ROOT)}/<corpus-version>",
    )
    args = parser.parse_args()

    corpus_version = _resolve_corpus_version(args.corpus_version)
    queries_path = args.queries or _default_queries_path(corpus_version)
    output_dir = args.output_dir or (DEFAULT_OUTPUT_DIR / corpus_version)

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    unknown = [m for m in models if m not in MODEL_REGISTRY]
    if unknown:
        parser.error(f"unknown model(s): {unknown}. choose from {sorted(MODEL_REGISTRY)}")

    queries = load_queries(queries_path)
    print(f"corpus_version: {corpus_version}", file=sys.stderr)
    print(f"queries: {len(queries)} from {_rel(queries_path)}", file=sys.stderr)
    print(f"models: {models}", file=sys.stderr)
    print(f"output: {_rel(output_dir)}", file=sys.stderr)

    for model_key in models:
        try:
            run_model(model_key, corpus_version, queries, args.runs, output_dir)
        except (RuntimeError, FileNotFoundError, ConnectionError) as e:
            print(f"[skip] {model_key} failed: {e}", file=sys.stderr)
            continue

    return 0


if __name__ == "__main__":
    sys.exit(main())
