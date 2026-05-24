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

Corpus version (ADR 0004):
  - v1: ハルナ・テクノロジーズ corpus (10 docs, legacy)
  - v2: ナギサ・パートナーズ corpus (15 docs, default; matches the rewritten
        article narrative)
  - selected via RAG_CORPUS_VERSION env var; defaults to v2.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol, TypedDict
from urllib.parse import urlparse, urlunparse

# Load .env at import time so example scripts and tests can rely on env vars
# (RAG_PROVIDER, OLLAMA_*, OPENAI_API_KEY, ANTHROPIC_API_KEY, …) without each
# script having to call load_dotenv() itself. Existing env vars are preserved
# (override=False), so CI and explicit `RAG_PROVIDER=… uv run …` still win.
try:
    from dotenv import load_dotenv

    load_dotenv(override=False)
except ImportError:
    pass

Provider = Literal["anthropic_openai", "ollama"]
DEFAULT_PROVIDER: Provider = "anthropic_openai"

_OLLAMA_DEFAULT_HOST = "http://localhost:11434"
_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})

CorpusVersion = Literal["v1", "v2"]
DEFAULT_CORPUS_VERSION: CorpusVersion = "v2"
_VALID_CORPUS_VERSIONS: frozenset[str] = frozenset({"v1", "v2"})
_REPO_ROOT = Path(__file__).resolve().parent


class OllamaModels(TypedDict):
    gen: str
    embed: str
    judge: str


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

        _verify_ollama_host()  # fail-fast on non-loopback host without opt-in
        self._model = model or _resolve_ollama_models()["gen"]
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

        _verify_ollama_host()  # fail-fast on non-loopback host without opt-in
        self._model = model or _resolve_ollama_models()["embed"]
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


def _resolve_ollama_models() -> OllamaModels:
    """Return generation / embedding / judge model ids in one typed dict.

    Used by `clients.py` itself (gen + embed) and by `examples/evaluate.py`
    (judge) so all three resolution paths share env naming and defaults.
    """
    return {
        "gen": os.getenv("OLLAMA_GEN_MODEL", "qwen3:8b"),
        "embed": os.getenv("OLLAMA_EMBED_MODEL", "qwen3-embedding:0.6b"),
        "judge": os.getenv("OLLAMA_JUDGE_MODEL", "qwen3:8b"),
    }


def _verify_ollama_host() -> tuple[str, str, str]:
    """Validate OLLAMA_HOST and return (raw_host, scheme, hostname).

    Centralises the remote-host opt-in check so both the native Ollama SDK
    (`_OllamaGenerate` / `_OllamaEmbed`) and the OpenAI-compatible eval path
    refuse to send data off-box before any request is made.

    Raises RuntimeError on non-loopback hosts without `ALLOW_REMOTE_OLLAMA=1`.
    """
    raw_host = os.getenv("OLLAMA_HOST", _OLLAMA_DEFAULT_HOST).strip() or _OLLAMA_DEFAULT_HOST
    parsed = urlparse(raw_host if "://" in raw_host else f"http://{raw_host}")
    hostname = (parsed.hostname or "").lower()

    # 0.0.0.0 as a client target reaches the local daemon, so we treat it as
    # loopback for the client; but the value still signals that the daemon
    # itself might be bound to all interfaces, which we cannot inspect.
    if hostname == "0.0.0.0":
        print(
            "[clients] WARNING: OLLAMA_HOST=0.0.0.0 — ensure the Ollama daemon "
            "is bound to loopback (the client cannot verify the daemon bind).",
            file=sys.stderr,
        )
    elif hostname not in _LOOPBACK_HOSTS:
        allow_remote = os.getenv("ALLOW_REMOTE_OLLAMA", "").lower() in {"1", "true", "yes"}
        if not allow_remote:
            raise RuntimeError(
                f"OLLAMA_HOST resolves to non-loopback host {hostname!r}. "
                "Refusing to send evaluation data to a remote Ollama daemon. "
                "Set ALLOW_REMOTE_OLLAMA=1 to opt in (and prefer HTTPS for non-LAN targets)."
            )
        if parsed.scheme != "https":
            print(
                f"[clients] WARNING: OLLAMA_HOST points at non-HTTPS remote host {hostname!r}. "
                "Eval prompts and contexts will be sent in cleartext.",
                file=sys.stderr,
            )
    return raw_host, parsed.scheme, hostname


def _resolve_ollama_openai_base_url() -> str:
    """Return an OpenAI-compatible base URL for the local Ollama daemon.

    Ollama exposes an OpenAI-compatible chat/embedding API at
    `<host>/v1` (https://github.com/ollama/ollama/blob/main/docs/openai.md).
    Host validation is delegated to `_verify_ollama_host()` so the same
    safety guard fires regardless of which transport the caller uses.

    Default: http://localhost:11434/v1
    """
    raw_host, _scheme, _hostname = _verify_ollama_host()
    parsed = urlparse(raw_host if "://" in raw_host else f"http://{raw_host}")
    base_path = (parsed.path or "").rstrip("/")
    if not base_path.endswith("/v1"):
        base_path = f"{base_path}/v1"
    return urlunparse((parsed.scheme, parsed.netloc, base_path, "", "", ""))


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


def _resolve_corpus_version(version: CorpusVersion | None = None) -> CorpusVersion:
    """Pick the corpus version from explicit arg, RAG_CORPUS_VERSION env, or default v2."""
    if version is not None:
        if version not in _VALID_CORPUS_VERSIONS:
            raise ValueError(
                f"corpus version {version!r} is not one of {sorted(_VALID_CORPUS_VERSIONS)}"
            )
        return version
    env = os.getenv("RAG_CORPUS_VERSION", "").strip().lower()
    if env in _VALID_CORPUS_VERSIONS:
        return env  # type: ignore[return-value]
    if env:
        # Unknown value: warn but fall back so a typo does not crash imports.
        print(
            f"[clients] WARNING: RAG_CORPUS_VERSION={env!r} not recognized; "
            f"using default {DEFAULT_CORPUS_VERSION}.",
            file=sys.stderr,
        )
    return DEFAULT_CORPUS_VERSION


def get_corpus_dir(*, version: CorpusVersion | None = None) -> Path:
    """Return the absolute path to the active corpus directory.

    Picks `corpus/v1` or `corpus/v2` based on the explicit `version=` arg or
    the RAG_CORPUS_VERSION env var (default: v2 — the ADR 0004 baseline that
    matches the rewritten article narrative). Raises FileNotFoundError if the
    target directory is missing, so example scripts fail fast instead of
    silently loading zero documents.
    """
    resolved = _resolve_corpus_version(version)
    path = _REPO_ROOT / "corpus" / resolved
    if not path.is_dir():
        raise FileNotFoundError(
            f"corpus directory {path} does not exist. "
            f"Place {resolved} corpus files there or set RAG_CORPUS_VERSION accordingly."
        )
    return path


def get_golden_set_path(*, version: CorpusVersion | None = None) -> Path:
    """Return the absolute path to the active golden_set.jsonl.

    v1 keeps the legacy root location (`golden_set.jsonl`) so existing tags
    and the v1 narrative remain reproducible. v2 lives under the corpus
    directory (`corpus/v2/golden_set.jsonl`) so the corpus and its evaluation
    set are co-located. Raises FileNotFoundError if missing.
    """
    resolved = _resolve_corpus_version(version)
    if resolved == "v1":
        path = _REPO_ROOT / "golden_set.jsonl"
    else:
        path = _REPO_ROOT / "corpus" / resolved / "golden_set.jsonl"
    if not path.is_file():
        raise FileNotFoundError(
            f"golden_set file {path} does not exist for corpus version {resolved}."
        )
    return path


def get_eval_report_path(*, version: CorpusVersion | None = None) -> Path:
    """Return the absolute path where evaluate.py writes its full report.

    The file lives at the repo root so v1 / v2 reports sit side-by-side for
    easy diffing. v1 keeps the legacy `eval_report.json` filename; v2 uses
    `eval_report.v2.json`.
    """
    resolved = _resolve_corpus_version(version)
    if resolved == "v1":
        return _REPO_ROOT / "eval_report.json"
    return _REPO_ROOT / f"eval_report.{resolved}.json"
