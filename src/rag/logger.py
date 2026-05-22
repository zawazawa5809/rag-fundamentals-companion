"""Part 5 — Sampling + PII-redacting RAG event logger.

A teaching-grade JSON-line logger that wraps three production essentials
into one tiny module:

  1. Opt-in sampling (default rate 1%; set RAG_LOG_SAMPLE_RATE=1.0 to
     capture everything during debugging)
  2. Per-field PII redaction (uses src/rag/pii_redactor)
  3. retrieved-chunk-id-only logging (chunk *bodies* are never written
     unless the caller explicitly opts in for a single event)

For real systems prefer the OpenTelemetry Collector with a custom
redaction processor, or a SIEM with PII scrubbing in-pipeline. This
module exists so the Part 5 example runs end-to-end without external
infra.
"""

from __future__ import annotations

import json
import os
import random
import sys
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TextIO

from rag.pii_redactor import redact


@dataclass
class LoggerConfig:
    sample_rate: float = 0.01
    retention_days: int = 30  # informational only — enforcement is the storage tier's job
    sink: TextIO | None = None  # default: sys.stdout
    allow_chunk_bodies: bool = False  # set True per call for explicit debug, never as default


@dataclass
class QueryEvent:
    query: str
    retrieved_chunk_ids: list[str]
    answer: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    retrieved_chunk_bodies: Iterable[str] | None = None  # only emitted if allow_chunk_bodies=True
    extra: dict[str, Any] = field(default_factory=dict)


def _resolve_sample_rate(cfg: LoggerConfig) -> float:
    env = os.getenv("RAG_LOG_SAMPLE_RATE")
    if env is not None:
        try:
            return max(0.0, min(1.0, float(env)))
        except ValueError:
            pass
    return cfg.sample_rate


class RagLogger:
    """Stateless wrapper; one instance can be shared across requests."""

    def __init__(self, config: LoggerConfig | None = None) -> None:
        self._cfg = config or LoggerConfig()

    def log(self, event: QueryEvent, *, force: bool = False) -> bool:
        """Maybe emit `event` to the sink.

        Returns True iff the event was emitted. Callers should treat the
        return value as advisory (e.g. for metrics on sampling).

        `force=True` bypasses sampling — use only for known-anomalous
        events (errors, sev1 incident traces) where you've already
        decided sampling does not apply.
        """
        rate = _resolve_sample_rate(self._cfg)
        if not force and random.random() >= rate:
            return False
        record = self._serialize(event)
        sink = self._cfg.sink or sys.stdout
        sink.write(json.dumps(record, ensure_ascii=False) + "\n")
        sink.flush()
        return True

    def _serialize(self, event: QueryEvent) -> dict[str, Any]:
        rec: dict[str, Any] = {
            "ts": int(time.time()),
            "event": "rag.query",
            "query": redact(event.query),
            "answer_excerpt": redact(event.answer[:200]),
            "retrieved_chunk_ids": list(event.retrieved_chunk_ids),
            "model": event.model,
            "gen_ai.usage.input_tokens": event.input_tokens,
            "gen_ai.usage.output_tokens": event.output_tokens,
            "latency_ms": event.latency_ms,
        }
        if event.extra:
            rec["extra"] = {k: redact(str(v)) for k, v in event.extra.items()}
        if self._cfg.allow_chunk_bodies and event.retrieved_chunk_bodies is not None:
            rec["retrieved_chunk_bodies"] = [redact(b) for b in event.retrieved_chunk_bodies]
        return rec


def file_logger(path: Path, *, sample_rate: float = 0.01) -> RagLogger:
    """Convenience: open `path` in append-mode and return a logger.

    Caller owns the file lifetime; for short-lived scripts that's fine.
    Long-running daemons should manage the file handle themselves so
    that log-rotation / SIGHUP semantics stay explicit.
    """
    sink = open(path, "a", encoding="utf-8")  # noqa: SIM115
    return RagLogger(LoggerConfig(sample_rate=sample_rate, sink=sink))
