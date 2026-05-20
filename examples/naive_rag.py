"""Part 1 placeholder. The real ~80 line implementation lands when the
Part 1 article (`rag-naive-baseline`) is written.

For now this file exists so:
  * the `part-01` tag has something to point at
  * `scripts/smoke_part.py --part 01 --mock` returns 0 in CI

When Part 1 ships, this body is replaced with the actual chunker + embedder
+ retriever + generator stack described in the article.
"""

from __future__ import annotations

import argparse
import sys

from clients import get_clients


def main() -> int:
    parser = argparse.ArgumentParser(description="Part 1 — naive RAG (placeholder).")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="use the mock LLM / embedding clients (no API keys required)",
    )
    args = parser.parse_args()

    clients = get_clients(mock=args.mock)
    answer = clients.generate.generate(
        "Hello from Part 1 scaffold. Replace me when rag-naive-baseline ships.",
        max_tokens=32,
    )
    print(answer)
    return 0


if __name__ == "__main__":
    sys.exit(main())
