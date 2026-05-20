"""Thin provider interfaces used across every Part.

Both `generate()` (Anthropic Claude) and `embed()` (OpenAI) go through this
single file so that swapping providers, mocking for CI, and per-Part smoke
tests stay trivial. Each Part imports `get_clients(mock=...)` and never
instantiates SDK clients directly.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol


class GenerateClient(Protocol):
    def generate(self, prompt: str, *, max_tokens: int = 1024) -> str: ...


class EmbedClient(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


@dataclass
class Clients:
    generate: GenerateClient
    embed: EmbedClient


class _MockGenerate:
    """Returns a deterministic stub so CI / readers without API keys can run examples."""

    def generate(self, prompt: str, *, max_tokens: int = 1024) -> str:
        head = prompt.strip().splitlines()[0][:60] if prompt.strip() else ""
        return f"[mock-answer] (echoing: {head!r}, max_tokens={max_tokens})"


class _MockEmbed:
    """Deterministic 8-dim embeddings derived from a stable hash of the input."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        import hashlib

        vectors: list[list[float]] = []
        for t in texts:
            digest = hashlib.sha256(t.encode("utf-8")).digest()
            vec = [b / 255.0 for b in digest[:8]]
            vectors.append(vec)
        return vectors


class _AnthropicGenerate:
    def __init__(self, model: str = "claude-sonnet-4-6") -> None:
        from anthropic import Anthropic

        self._model = model
        self._client = Anthropic()

    def generate(self, prompt: str, *, max_tokens: int = 1024) -> str:
        msg = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in msg.content if block.type == "text")


class _OpenAIEmbed:
    def __init__(self, model: str = "text-embedding-3-small") -> None:
        from openai import OpenAI

        self._model = model
        self._client = OpenAI()

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = self._client.embeddings.create(model=self._model, input=texts)
        return [d.embedding for d in response.data]


def get_clients(*, mock: bool | None = None) -> Clients:
    """Return generate/embed clients.

    Resolution order for `mock`:
      1. explicit argument
      2. RAG_MOCK env var (`1` / `true` enables mock)
      3. default: real clients (requires ANTHROPIC_API_KEY and OPENAI_API_KEY)
    """
    if mock is None:
        env = os.getenv("RAG_MOCK", "").lower()
        mock = env in {"1", "true", "yes"}
    if mock:
        return Clients(generate=_MockGenerate(), embed=_MockEmbed())
    return Clients(generate=_AnthropicGenerate(), embed=_OpenAIEmbed())
