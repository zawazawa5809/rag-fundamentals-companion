"""Part 2 — heading-aware chunker with metadata preservation.

Splits each markdown doc by H2/H3 headings (preserving heading path) and
extracts soft metadata from the blockquote header pattern used across this
series' corpus (e.g. `> Document version: **v3.0** / 最終更新: ...`).

Output node carries:

  - `chunk_id`   {doc_id}#{heading_slug}#{seq}
  - `text`       chunk body (header lines stripped on request)
  - `metadata`   {version, status, updated_at, owner, heading_path}

`status` is heuristically set to `draft` when the document body contains a
literal warning like 「承認されていない」「ドラフト」 inside a blockquote, and
to `active` otherwise.

This is intentionally a teaching implementation — production users should
prefer `langchain_text_splitters.MarkdownHeaderTextSplitter` or LlamaIndex
hierarchical parsers (see references in the article).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

CHUNK_TARGET = 600
CHUNK_OVERLAP = 80

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
_BLOCKQUOTE_RE = re.compile(r"^>\s?(.*)$", re.MULTILINE)
_VERSION_RE = re.compile(r"version[:\s]*\**\s*((?:draft\s+)?v?[0-9][0-9a-zA-Z.]*)", re.IGNORECASE)
_UPDATED_RE = re.compile(r"(?:最終更新|最終改訂|updated|更新日)[:\s]*\**\s*([0-9]{4}\s*年\s*[0-9]{1,2}\s*月\s*[0-9]{1,2}\s*日|[0-9]{4}-[0-9]{2}-[0-9]{2})")
_OWNER_RE = re.compile(r"\(([^)]+部)\)|\(([^)]+チーム)\)|\(([^)]+ 幹事[^)]*)\)")
_DRAFT_WORDS = ("承認されていない", "ドラフト", "draft v")


@dataclass
class ChunkNode:
    chunk_id: str
    text: str
    metadata: dict = field(default_factory=dict)


def _slugify_heading(heading: str) -> str:
    s = heading.strip().lower()
    s = re.sub(r"[^a-z0-9一-龯ぁ-んァ-ヴー\s-]", "", s)
    s = re.sub(r"\s+", "-", s).strip("-")
    return s[:40] or "section"


def _extract_metadata(body: str) -> dict:
    bq_blocks = "\n".join(m.group(1) for m in _BLOCKQUOTE_RE.finditer(body[:1500]))
    version = None
    if m := _VERSION_RE.search(bq_blocks):
        version = m.group(1).strip().rstrip(".")
    updated = None
    if m := _UPDATED_RE.search(bq_blocks):
        updated = m.group(1).strip()
    owner = None
    if m := _OWNER_RE.search(bq_blocks):
        owner = next((g for g in m.groups() if g), None)
    status = "draft" if any(w in bq_blocks for w in _DRAFT_WORDS) else "active"
    return {"version": version, "status": status, "updated_at": updated, "owner": owner}


def _split_by_headings(body: str) -> list[tuple[list[str], str]]:
    """Return [(heading_path, section_text), ...] where heading_path is the H1>H2>H3 trail."""
    matches = list(_HEADING_RE.finditer(body))
    if not matches:
        return [([], body)]
    sections: list[tuple[list[str], str]] = []
    path: list[str] = []
    for i, m in enumerate(matches):
        level = len(m.group(1))
        title = m.group(2)
        while len(path) >= level:
            path.pop()
        path.append(title)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        text = body[start:end].strip()
        if text:
            sections.append((list(path), text))
    return sections


def _slide(text: str, target: int = CHUNK_TARGET, overlap: int = CHUNK_OVERLAP) -> list[str]:
    if len(text) <= target:
        return [text]
    out: list[str] = []
    step = target - overlap
    for start in range(0, max(len(text) - overlap, 1), step):
        piece = text[start : start + target]
        if piece.strip():
            out.append(piece)
    return out


def chunk_document(doc_id: str, body: str) -> list[ChunkNode]:
    body = re.sub(r"^<!--.*?-->\s*", "", body, flags=re.DOTALL).strip()
    meta = _extract_metadata(body)
    sections = _split_by_headings(body)
    nodes: list[ChunkNode] = []
    for heading_path, text in sections:
        slug = _slugify_heading(heading_path[-1]) if heading_path else "intro"
        # Prefix the heading path into the indexed text so BM25/dense can match
        # terms that only appear in the heading (e.g. "手当" in a section
        # titled 「リモートワーク手当」).
        heading_prefix = " > ".join(heading_path) + "\n" if heading_path else ""
        for seq, piece in enumerate(_slide(text)):
            chunk_id = f"{doc_id}#{slug}#{seq:02d}"
            nodes.append(
                ChunkNode(
                    chunk_id=chunk_id,
                    text=heading_prefix + piece,
                    metadata={**meta, "heading_path": heading_path},
                )
            )
    return nodes


def chunk_corpus(corpus_dir: Path) -> list[ChunkNode]:
    nodes: list[ChunkNode] = []
    for md in sorted(corpus_dir.glob("*.md")):
        if md.name == "SOURCES.md":
            continue
        nodes.extend(chunk_document(md.stem, md.read_text(encoding="utf-8")))
    return nodes
