"""Smoke test dispatcher used by .github/workflows/smoke-tag.yml.

A push to a `part-NN` tag (e.g. `part-01`) triggers the workflow, which then
calls:

    uv run python scripts/smoke_part.py --part 01 --mock

Each Part adds its own row to MAPPING. Missing rows fail loudly so a stale
tag never silently passes.
"""

from __future__ import annotations

import argparse
import subprocess
import sys

# part code (zero-padded) -> python module
MAPPING: dict[str, str] = {
    "01": "examples.naive_rag",
    "02": "examples.retrieval.run",
    "03": "examples.generation.run",
    # "04": "examples.evaluate",        # added in Part 4
    # "05": "examples.ops.run",         # added in Part 5
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test dispatcher for part-NN tags.")
    parser.add_argument("--part", required=True, help="part code, zero-padded (e.g. 01)")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="run the example in mock mode (no API keys required)",
    )
    args = parser.parse_args()

    if args.part not in MAPPING:
        print(f"[smoke] unknown part {args.part!r}; known: {sorted(MAPPING)}", file=sys.stderr)
        return 2

    module = MAPPING[args.part]
    cmd = ["python", "-m", module]
    if args.mock:
        cmd.append("--mock")
    print(f"[smoke] running: {' '.join(cmd)}")

    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        print(f"[smoke] FAIL part={args.part} module={module} exit={result.returncode}")
    else:
        print(f"[smoke] OK part={args.part} module={module}")
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
