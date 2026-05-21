"""Dense retrieval wrapper. Thin layer over the shared `clients.embed` interface."""

from __future__ import annotations

import numpy as np

from clients import EmbedClient


def embed_corpus(embed_client: EmbedClient, chunks: list[tuple[str, str]]) -> np.ndarray:
    """Return (N, D) float32 matrix; one row per chunk."""
    vectors = embed_client.embed([text for _, text in chunks])
    return np.array(vectors, dtype=np.float32)


def dense_rank(embed_client: EmbedClient, query: str, chunk_matrix: np.ndarray) -> list[int]:
    """Return chunk indices sorted by cosine similarity, descending."""
    q = np.array(embed_client.embed([query])[0], dtype=np.float32)
    norms = np.linalg.norm(chunk_matrix, axis=1) * np.linalg.norm(q) + 1e-9
    sims = chunk_matrix @ q / norms
    return list(np.argsort(-sims))
