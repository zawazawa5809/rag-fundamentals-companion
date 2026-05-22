"""Part 3 — cross-encoder reranker (ms-marco-MiniLM-L-6-v2 wrapper).

Takes the top-k output of Part 2 hybrid retrieval and re-scores each
(query, chunk) pair with a cross-encoder so the relevance signal sees
both sides at once (cross-attention) instead of independent embeddings.

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


class _CrossEncoderReranker:
    """Thin wrapper around `sentence-transformers/cross-encoder/ms-marco-MiniLM-L-6-v2`.

    Loaded lazily on first call so that --mock paths never trigger the
    sentence-transformers import chain (which pulls torch / transformers).
    """

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2") -> None:
        self._model_name = model_name
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
