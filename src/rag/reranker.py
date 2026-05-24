"""Part 3 — cross-encoder reranker (multilingual bge-reranker-v2-m3 wrapper).

Takes the top-k output of Part 2 hybrid retrieval and re-scores each
(query, chunk) pair with a cross-encoder so the relevance signal sees
both sides at once (cross-attention) instead of independent embeddings.

Default model is `BAAI/bge-reranker-v2-m3` — a **multilingual** cross-encoder.
The earlier `cross-encoder/ms-marco-MiniLM-L-6-v2` is English-only (MS MARCO);
on this Japanese corpus it reranked near-randomly and *degraded* aggregate
RAGAs scores (Part 4 measurement caught it — the eyeball trap test in Part 3
looked fine while context recall regressed). Override with `RAG_RERANKER_MODEL`.

The reason this is a separate module (not under examples/generation/) is
that Part 4 evaluation reuses the exact same reranker — we want one
deterministic interface for ranking improvements across Parts.

Mock mode skips the model load entirely and preserves the input order,
so CI and readers without GPUs/internet can still observe the wiring.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol


class Reranker(Protocol):
    def rerank(self, query: str, candidates: list[tuple[str, str]], *, top_k: int) -> list[tuple[int, float]]:
        """Return [(original_index, score), ...] sorted by descending score, length ≤ top_k."""
        ...


@dataclass
class _MockReranker:
    """Preserves input order; score is a monotonically decreasing dummy value."""

    def rerank(
        self, query: str, candidates: list[tuple[str, str]], *, top_k: int
    ) -> list[tuple[int, float]]:
        return [(i, 1.0 - i * 0.01) for i in range(min(top_k, len(candidates)))]


_DEFAULT_RERANKER = "BAAI/bge-reranker-v2-m3"


class _CrossEncoderReranker:
    """Thin wrapper around a sentence-transformers CrossEncoder.

    Default `BAAI/bge-reranker-v2-m3` (multilingual). Loaded lazily on first
    call so that --mock paths never trigger the sentence-transformers import
    chain (which pulls torch / transformers).
    """

    def __init__(self, model_name: str | None = None) -> None:
        self._model_name = model_name or os.getenv("RAG_RERANKER_MODEL", _DEFAULT_RERANKER)
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self._model_name)
        return self._model

    def rerank(
        self, query: str, candidates: list[tuple[str, str]], *, top_k: int
    ) -> list[tuple[int, float]]:
        if not candidates:
            return []
        model = self._load()
        pairs = [[query, text] for _, text in candidates]
        scores = model.predict(pairs)
        ranked = sorted(enumerate(scores), key=lambda x: -float(x[1]))
        return [(i, float(s)) for i, s in ranked[:top_k]]


def get_reranker(*, mock: bool | None = None) -> Reranker:
    """Return a Reranker instance.

    Resolution order for `mock` mirrors `clients.get_clients`:
      1. explicit argument
      2. RAG_MOCK env var (`1` / `true` / `yes` enables mock)
      3. default: real CrossEncoder (downloads model on first call)
    """
    if mock is None:
        env = os.getenv("RAG_MOCK", "").lower()
        mock = env in {"1", "true", "yes"}
    if mock:
        return _MockReranker()
    return _CrossEncoderReranker()
