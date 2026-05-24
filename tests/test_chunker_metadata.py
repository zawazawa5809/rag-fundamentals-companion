"""Part 2 chunker — metadata extraction (status: draft / archived / active).

Pure-Python, no Ollama: verifies the v2 corpus' stale-trap archive docs are
tagged `status=archived` while current docs that merely *reference* an archive
stay `active`, so Part 5's status/freshness filter has correct metadata to act on.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from examples.retrieval.chunker import _extract_metadata, chunk_corpus  # noqa: E402

CORPUS_V2 = REPO_ROOT / "corpus" / "v2"


def _status_of(body: str) -> str:
    return _extract_metadata(body)["status"]


def test_archive_self_label_is_archived():
    body = (
        "<!-- License: CC0-1.0 -->\n# Mirage アーキテクチャ v2 (旧版)\n\n"
        "> ⚠️ **Archive 注記**: 2025 年 3 月の v3 移行で全面刷新。"
        "本書類は履歴参照のために archive されています。\n"
    )
    assert _status_of(body) == "archived"


def test_current_doc_referencing_archive_stays_active():
    # v3 mentions 「v2 は … に archive 済」 — must NOT be flagged archived.
    body = (
        "<!-- License: CC0-1.0 -->\n# Mirage アーキテクチャ v3.2 (現行)\n\n"
        "> 最終更新: 2025 年 3 月 18 日\n"
        "> v2 → v3 移行完了、本番稼働中。v2 は `mirage-architecture-v2-archive.md` に archive 済\n"
    )
    assert _status_of(body) == "active"


def test_draft_still_takes_precedence():
    body = "# X\n\n> 本書はまだ承認されていないドラフト である\n"
    assert _status_of(body) == "draft"


def test_v2_corpus_exactly_two_archived_docs():
    """The v2 corpus has exactly two stale-trap archive docs."""
    if not CORPUS_V2.is_dir():
        return  # corpus not present in this checkout; skip silently
    archived = {
        node.chunk_id.split("#", 1)[0]
        for node in chunk_corpus(CORPUS_V2)
        if node.metadata.get("status") == "archived"
    }
    assert archived == {"mirage-architecture-v2-archive", "nagisa-expense-2023-archive"}, archived
