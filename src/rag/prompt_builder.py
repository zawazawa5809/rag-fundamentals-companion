"""Part 3 — Anthropic Citations API document blocks builder.

Converts a list of reranked chunks into the `messages.create` content
array shape that Citations API expects:

    [
      {
        "type": "document",
        "source": {"type": "content", "content": [{"type": "text", "text": chunk.body}]},
        "title": chunk_id,
        "context": "status=active version=v3.0",
        "citations": {"enabled": True},
      },
      ...,
      {"type": "text", "text": query},
    ]

Why `custom content` (not `text` source)?  Part 1-2 established that the
chunk_id is the unit of observability across the series.  Custom content
emits `start_block_index` which maps 1:1 to the chunk_id we attach as
`title`, so downstream UI / eval code can trace a citation back to a
chunk without re-tokenizing.

This module is `src/rag/` (not under `examples/generation/`) because
Part 4 evaluation needs to build the same documents block — keeping it
shared avoids accidental drift between the article example and the
benchmark.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

SYSTEM_PROMPT = (
    "あなたはハルナ・テクノロジーズの社内ナレッジに精通したアシスタントです。"
    "回答は必ず提供された documents のみを根拠とし、事実を述べるたびに該当する chunk を引用してください。"
    "documents に答えがない場合は『提供された資料からは判断できません』と明示してください。"
)


@dataclass(frozen=True)
class CitedChunk:
    """A chunk reranked to top-k, carrying just what Citations API needs.

    `body` is the verbatim text that will live inside the citation source.
    `context` is metadata passed to the model but never quoted in
    `cited_text` (per Anthropic docs), so it is safe to expose
    document-level status/version here.
    """

    chunk_id: str
    body: str
    context: str = ""


def _document_block(chunk: CitedChunk) -> dict[str, Any]:
    block: dict[str, Any] = {
        "type": "document",
        "source": {
            "type": "content",
            "content": [{"type": "text", "text": chunk.body}],
        },
        "title": chunk.chunk_id,
        "citations": {"enabled": True},
    }
    if chunk.context:
        block["context"] = chunk.context
    return block


def build_messages(query: str, chunks: Sequence[CitedChunk]) -> list[dict[str, Any]]:
    """Build the `messages` array for `client.messages.create(...)`.

    All-or-none: every document block has `citations.enabled = True`.
    Mixing enabled/disabled documents in one request raises 400 from the API.
    """
    content: list[dict[str, Any]] = [_document_block(c) for c in chunks]
    content.append({"type": "text", "text": query})
    return [{"role": "user", "content": content}]
