"""Part 1 — Naive RAG baseline (~80 LOC).

A deliberately minimal RAG pipeline: load markdown corpus → fixed-size
chunking with overlap → OpenAI embedding → cosine top-k retrieval →
Anthropic Claude generation.

This is intentionally NOT production-ready. Part 2 onward improves each
stage and measures the lift.

Run:
  uv run python -m examples.naive_rag --query "Cumulus Labs の NSM は？"
  uv run python -m examples.naive_rag --mock   # no API keys needed
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np

from clients import get_clients, get_corpus_dir

CORPUS_DIR = get_corpus_dir()
CHUNK_SIZE = 600
CHUNK_OVERLAP = 100
TOP_K = 3


def load_corpus(path: Path) -> list[tuple[str, str]]:
    """Return [(doc_id, body), ...] from .md files (CC0 header stripped)."""
    docs: list[tuple[str, str]] = []
    for md in sorted(path.glob("*.md")):
        if md.name == "SOURCES.md":
            continue
        body = md.read_text(encoding="utf-8")
        body = re.sub(r"^<!--.*?-->\s*", "", body, flags=re.DOTALL).strip()
        docs.append((md.stem, body))
    return docs


def chunk(docs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Fixed-size sliding window. Returns [(chunk_id, text), ...]."""
    out: list[tuple[str, str]] = []
    step = CHUNK_SIZE - CHUNK_OVERLAP
    for doc_id, body in docs:
        n = max(len(body) - CHUNK_OVERLAP, 1)
        for i, start in enumerate(range(0, n, step)):
            piece = body[start : start + CHUNK_SIZE]
            if piece.strip():
                out.append((f"{doc_id}#{i:02d}", piece))
    return out


def cosine_topk(query_vec: list[float], doc_vecs: list[list[float]], k: int) -> list[tuple[int, float]]:
    q = np.array(query_vec, dtype=np.float32)
    M = np.array(doc_vecs, dtype=np.float32)
    sims = M @ q / (np.linalg.norm(M, axis=1) * np.linalg.norm(q) + 1e-9)
    idx = np.argsort(-sims)[:k]
    return [(int(i), float(sims[i])) for i in idx]


def build_prompt(query: str, retrieved: list[tuple[str, str, float]]) -> str:
    ctx = "\n\n".join(f"### {cid}\n{txt}" for cid, txt, _ in retrieved)
    return (
        "<context>\n"
        f"{ctx}\n"
        "</context>\n\n"
        f"<question>{query}</question>\n\n"
        "上の context のみを根拠に、3-4 文で答えてください。"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Part 1 — naive RAG baseline.")
    parser.add_argument("--query", "-q", default="Cumulus Labs の North Star Metric は？")
    parser.add_argument("--mock", action="store_true", help="use mock clients")
    parser.add_argument("--corpus", type=Path, default=CORPUS_DIR)
    args = parser.parse_args()

    clients = get_clients(mock=args.mock)
    docs = load_corpus(args.corpus)
    chunks = chunk(docs)
    print(f"[corpus] {len(docs)} docs, {len(chunks)} chunks")

    doc_vecs = clients.embed.embed([c[1] for c in chunks])
    q_vec = clients.embed.embed([args.query])[0]
    hits = cosine_topk(q_vec, doc_vecs, TOP_K)

    retrieved = [(chunks[i][0], chunks[i][1], score) for i, score in hits]
    print("[retrieve] top-k:")
    for cid, _, score in retrieved:
        print(f"  {score:.4f}  {cid}")

    prompt = build_prompt(args.query, retrieved)
    answer = clients.generate.generate(prompt, max_tokens=512)
    print("\n[answer]")
    print(answer)
    return 0


if __name__ == "__main__":
    sys.exit(main())
