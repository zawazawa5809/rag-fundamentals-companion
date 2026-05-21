"""BM25 + dense + Reciprocal Rank Fusion.

This module is intentionally minimal — it implements the retrieval logic
discussed in Part 2 of the series, not a production search engine. For
real workloads, use `bm25s` (SciPy-sparse, faster) and a vector DB.
"""

from __future__ import annotations

import re

from rank_bm25 import BM25Okapi  # type: ignore[import-untyped]


_LATIN_RE = re.compile(r"[A-Za-z0-9]+")
_JA_RUN_RE = re.compile(r"[一-龯ぁ-んァ-ヴー]+")


def tokenize(text: str) -> list[str]:
    """Cheap tokenizer: Latin words + overlapping Japanese 2-grams (no mecab/sudachi)."""
    text = text.lower()
    tokens = _LATIN_RE.findall(text)
    for m in _JA_RUN_RE.finditer(text):
        run = m.group()
        tokens.extend(run[i : i + 2] for i in range(max(len(run) - 1, 1)))
    return tokens


def build_bm25(chunks: list[tuple[str, str]]) -> BM25Okapi:
    """Pre-tokenize the corpus once and return a reusable index."""
    return BM25Okapi([tokenize(text) for _, text in chunks])


def bm25_rank(query: str, bm25: BM25Okapi) -> list[int]:
    scores = bm25.get_scores(tokenize(query))
    return sorted(range(len(scores)), key=lambda i: -scores[i])


def rrf_fuse(rankings: list[list[int]], *, k: int = 60, top_k: int = 5) -> list[int]:
    """Combine multiple rank lists by Reciprocal Rank Fusion (Cormack et al., 2009)."""
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, idx in enumerate(ranking):
            scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores, key=lambda i: -scores[i])[:top_k]


def apply_status_filter(indices: list[int], chunk_meta: list[dict], *, exclude: set[str]) -> list[int]:
    """Drop chunks whose metadata['status'] matches any value in `exclude`."""
    return [i for i in indices if chunk_meta[i].get("status") not in exclude]
