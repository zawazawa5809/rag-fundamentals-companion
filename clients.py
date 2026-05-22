"""Thin provider interfaces used across every Part.

`generate()` and `embed()` both go through this single file so that
swapping providers, mocking for CI, and per-Part smoke tests stay
trivial. Each Part imports `get_clients(mock=..., provider=...)` and
never instantiates SDK clients directly.

Three provider modes:
  - mock                  — deterministic stub, no deps required
  - anthropic_openai      — Anthropic Claude + OpenAI embeddings (default;
                            matches the article narrative for Part 1-5)
  - ollama                — Ollama-served Qwen3 (free local alternative;
                            see ADR 0003 for model selection rationale)

Resolution order for provider:
  1. explicit `provider=` argument
  2. RAG_PROVIDER env var (`anthropic_openai` | `ollama`)
  3. default: `anthropic_openai`

Mock takes precedence over provider — if mock is enabled, the provider
choice is ignored.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal, Protocol

Provider = Literal["anthropic_openai", "ollama"]
DEFAULT_PROVIDER: Provider = "anthropic_openai"


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


class _OllamaGenerate:
    """Ollama-served generation. Default model is Qwen3 8B (Apache 2.0).

    Model can be overridden via OLLAMA_GEN_MODEL env var. Host defaults to
    http://localhost:11434 but honors OLLAMA_HOST so readers running
    Ollama on a remote machine can point at it.
    """

    def __init__(self, model: str | None = None) -> None:
        from ollama import Client

        self._model = model or os.getenv("OLLAMA_GEN_MODEL", "qwen3:8b")
        self._client = Client(host=os.getenv("OLLAMA_HOST"))

    def generate(self, prompt: str, *, max_tokens: int = 1024) -> str:
        response = self._client.chat(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            options={"num_predict": max_tokens},
        )
        return response.message.content or ""


class _OllamaEmbed:
    """Ollama-served embeddings. Default model is qwen3-embedding 0.6B.

    qwen3-embedding ranks #1 on the MTEB multilingual leaderboard
    (8B variant, June 2025). The 0.6B variant is the lightest of the
    family and runs comfortably on a 16 GB Mac alongside qwen3:8b.
    """

    def __init__(self, model: str | None = None) -> None:
        from ollama import Client

        self._model = model or os.getenv("OLLAMA_EMBED_MODEL", "qwen3-embedding:0.6b")
        self._client = Client(host=os.getenv("OLLAMA_HOST"))

    def embed(self, texts: list[str]) -> list[list[float]]:
        # `ollama.embed` accepts a list and returns one vector per input,
        # mirroring the OpenAI batch shape so callers don't branch on provider.
        response = self._client.embed(model=self._model, input=texts)
        return [list(v) for v in response.embeddings]


def _resolve_provider(provider: Provider | None) -> Provider:
    if provider is not None:
        return provider
    env = os.getenv("RAG_PROVIDER", "").strip().lower()
    if env in {"ollama"}:
        return "ollama"
    if env in {"anthropic_openai", "anthropic+openai", "default", ""}:
        return "anthropic_openai"
    # Unknown value — fall back to the documented default rather than crashing
    # at import time. The runner will still print the resolved provider.
    return DEFAULT_PROVIDER


def get_clients(*, mock: bool | None = None, provider: Provider | None = None) -> Clients:
    """Return generate/embed clients.

    Resolution order:
      1. mock= argument (forces mock if True)
      2. RAG_MOCK env (`1`/`true`/`yes` enables mock)
      3. provider= argument
      4. RAG_PROVIDER env (`anthropic_openai` (default) | `ollama`)

    See ADR 0003 for the provider matrix and model selection rationale.
    """
    if mock is None:
        env = os.getenv("RAG_MOCK", "").lower()
        mock = env in {"1", "true", "yes"}
    if mock:
        return Clients(generate=_MockGenerate(), embed=_MockEmbed())
    resolved = _resolve_provider(provider)
    if resolved == "ollama":
        return Clients(generate=_OllamaGenerate(), embed=_OllamaEmbed())
    return Clients(generate=_AnthropicGenerate(), embed=_OpenAIEmbed())
