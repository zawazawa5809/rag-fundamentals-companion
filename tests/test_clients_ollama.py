"""Tests for the Ollama provider helpers in clients.py.

These tests don't talk to a running Ollama daemon — they exercise the
URL/model resolution helpers, the loopback safety guard, and verify that
`_build_real_scorers(provider="ollama")` constructs an AsyncOpenAI client
pointed at the Ollama OpenAI-compatible endpoint without invoking it.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from clients import (  # noqa: E402
    _resolve_ollama_models,
    _resolve_ollama_openai_base_url,
)


def test_default_base_url_is_loopback_v1(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    monkeypatch.delenv("ALLOW_REMOTE_OLLAMA", raising=False)
    assert _resolve_ollama_openai_base_url() == "http://localhost:11434/v1"


def test_host_without_scheme_gets_http(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_HOST", "localhost:11434")
    monkeypatch.delenv("ALLOW_REMOTE_OLLAMA", raising=False)
    assert _resolve_ollama_openai_base_url() == "http://localhost:11434/v1"


def test_host_with_v1_suffix_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_HOST", "http://localhost:11434/v1")
    monkeypatch.delenv("ALLOW_REMOTE_OLLAMA", raising=False)
    assert _resolve_ollama_openai_base_url() == "http://localhost:11434/v1"


def test_remote_host_rejected_without_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_HOST", "http://lan-host:11434")
    monkeypatch.delenv("ALLOW_REMOTE_OLLAMA", raising=False)
    with pytest.raises(RuntimeError, match="non-loopback host"):
        _resolve_ollama_openai_base_url()


def test_remote_host_allowed_with_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_HOST", "http://lan-host:11434")
    monkeypatch.setenv("ALLOW_REMOTE_OLLAMA", "1")
    assert _resolve_ollama_openai_base_url() == "http://lan-host:11434/v1"


def test_zero_zero_zero_zero_is_loopback_with_warning(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """0.0.0.0 as a client target reaches the local daemon (loopback for the
    client) but we still warn because the daemon may be exposing all interfaces."""
    monkeypatch.setenv("OLLAMA_HOST", "http://0.0.0.0:11434")
    monkeypatch.delenv("ALLOW_REMOTE_OLLAMA", raising=False)
    assert _resolve_ollama_openai_base_url() == "http://0.0.0.0:11434/v1"
    captured = capsys.readouterr()
    assert "OLLAMA_HOST=0.0.0.0" in captured.err


def test_ollama_generate_construction_fails_on_remote_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Construction of _OllamaGenerate must fail-fast on non-loopback host
    without ALLOW_REMOTE_OLLAMA — so no embed/chat request leaks data even
    when called outside the eval scorer path (e.g. via examples.naive_rag)."""
    from clients import _OllamaGenerate

    monkeypatch.setenv("OLLAMA_HOST", "http://lan-host:11434")
    monkeypatch.delenv("ALLOW_REMOTE_OLLAMA", raising=False)
    with pytest.raises(RuntimeError, match="non-loopback host"):
        _OllamaGenerate()


def test_ollama_embed_construction_fails_on_remote_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from clients import _OllamaEmbed

    monkeypatch.setenv("OLLAMA_HOST", "http://lan-host:11434")
    monkeypatch.delenv("ALLOW_REMOTE_OLLAMA", raising=False)
    with pytest.raises(RuntimeError, match="non-loopback host"):
        _OllamaEmbed()


def test_default_models(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("OLLAMA_GEN_MODEL", "OLLAMA_EMBED_MODEL", "OLLAMA_JUDGE_MODEL"):
        monkeypatch.delenv(key, raising=False)
    models = _resolve_ollama_models()
    assert models == {
        "gen": "qwen3:8b",
        "embed": "qwen3-embedding:0.6b",
        "judge": "qwen3:8b",
    }


def test_judge_model_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_JUDGE_MODEL", "qwen3:14b")
    assert _resolve_ollama_models()["judge"] == "qwen3:14b"


def test_build_real_scorers_ollama_uses_compat_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`_build_real_scorers(provider='ollama')` should pass the Ollama
    base_url and the judge model id into AsyncOpenAI / llm_factory."""
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    monkeypatch.delenv("OLLAMA_JUDGE_MODEL", raising=False)
    monkeypatch.delenv("OLLAMA_EMBED_MODEL", raising=False)
    monkeypatch.setenv("OLLAMA_API_KEY", "test-key")

    sys.path.insert(0, str(REPO_ROOT / "examples"))
    from examples.evaluate import _build_real_scorers  # noqa: E402

    with (
        patch("openai.AsyncOpenAI") as mock_client,
        patch("ragas.llms.llm_factory") as mock_llm,
        patch("ragas.embeddings.base.embedding_factory") as mock_emb,
        patch("ragas.metrics.collections.Faithfulness"),
        patch("ragas.metrics.collections.AnswerRelevancy"),
        patch("ragas.metrics.collections.ContextPrecision"),
        patch("ragas.metrics.collections.ContextRecall"),
    ):
        _build_real_scorers("ollama")

    mock_client.assert_called_once_with(
        base_url="http://localhost:11434/v1", api_key="test-key"
    )
    args, kwargs = mock_llm.call_args
    assert args[0] == "qwen3:8b"
    assert kwargs.get("temperature") == 0
    emb_args, emb_kwargs = mock_emb.call_args
    assert emb_args == ("openai",)
    assert emb_kwargs.get("model") == "qwen3-embedding:0.6b"
