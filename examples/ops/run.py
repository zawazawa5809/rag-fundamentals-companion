"""Part 5 — Ops demo: redact, sample, and emit RAG telemetry.

Walks a hard-coded stream of fake user queries (each laced with one or
more PII patterns) through the Part 5 logger to show:

  1. Every PII pattern in src/rag/pii_redactor is caught before write
  2. Sample-rate gating (default 1%, forced to 1.0 in --demo for visibility)
  3. retrieved-chunk *ids only* — bodies never leak unless allow_chunk_bodies
     is explicitly set per call

  uv run python -m examples.ops.run --demo            # sample_rate=1.0, all events
  uv run python -m examples.ops.run                   # default 1%, deterministic seed
  uv run python -m examples.ops.run --allow-bodies    # demonstrate the danger flag
"""

from __future__ import annotations

import argparse
import random
import sys
from io import StringIO
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from rag.logger import LoggerConfig, QueryEvent, RagLogger  # noqa: E402
from rag.pii_redactor import redact_with_report  # noqa: E402

FAKE_STREAM = [
    {
        "query": "経費精算を yamada.taro@haruna.example で出した件、上限内？",
        "retrieved_chunk_ids": ["haruna-expense#月-50000-円までの-経費カテゴリと上限#00"],
        "answer": "月 50,000 円までです。",
        "chunk_body": "経費は月額 50,000 円までで、申請者は yamada.taro@haruna.example などの社内メールから提出する。",
    },
    {
        "query": "障害時の Sev1 連絡先を電話 090-1234-5678 まで教えて",
        "retrieved_chunk_ids": ["haruna-incident-flow#sev1-production-down#00"],
        "answer": "Sev1 は #incident-active で thread を立てます。",
        "chunk_body": "Sev1 は 5 分以内に acknowledge。oncall の番号は 090-1234-5678。",
    },
    {
        "query": "credit card 4242 4242 4242 4242 で支払った請求の問い合わせ先は？",
        "retrieved_chunk_ids": ["haruna-faq-helpdesk#経費#00"],
        "answer": "経費精算は経理部へ。クレジットカード番号は社内チャットに書かないでください。",
        "chunk_body": "カード番号 4242-4242-4242-4242 のような機微情報は redact 対象。",
    },
    {
        "query": "API key sk-thisisafakekey0123456789abcd の権限スコープは？",
        "retrieved_chunk_ids": ["stratus-api-reference#schema-token#00"],
        "answer": "Stratus API key の scope は read / write / admin の 3 段階。",
        "chunk_body": "API key 例: sk-thisisafakekey0123456789abcd / scope は admin。",
    },
    {
        "query": "Pegasus DB の IP 10.0.42.7 にアクセスできない件",
        "retrieved_chunk_ids": ["pegasus-er-diagram#連絡先#00"],
        "answer": "Pegasus 担当チームに #pegasus-support で問い合わせてください。",
        "chunk_body": "Pegasus DB host: 10.0.42.7 (運用 VLAN)。",
    },
]


def _print_section(title: str) -> None:
    print(f"\n=== {title} ===")


def _show_redaction_summary() -> None:
    _print_section("Redaction summary per fake event")
    for i, evt in enumerate(FAKE_STREAM, 1):
        rep = redact_with_report(evt["query"] + " || " + evt["answer"] + " || " + evt["chunk_body"])
        hits_str = ", ".join(f"{k}={v}" for k, v in sorted(rep.hits.items())) or "(none)"
        print(f"  event-{i}: hits={hits_str}")


def _run_logger(sample_rate: float, allow_bodies: bool, seed: int) -> None:
    _print_section(
        f"Logger run (sample_rate={sample_rate}, allow_chunk_bodies={allow_bodies}, seed={seed})"
    )
    random.seed(seed)
    sink = StringIO()
    logger = RagLogger(LoggerConfig(sample_rate=sample_rate, sink=sink, allow_chunk_bodies=allow_bodies))
    emitted = 0
    for evt in FAKE_STREAM:
        ok = logger.log(
            QueryEvent(
                query=evt["query"],
                retrieved_chunk_ids=evt["retrieved_chunk_ids"],
                answer=evt["answer"],
                model="claude-opus-4-7",
                input_tokens=1024,
                output_tokens=128,
                latency_ms=820,
                retrieved_chunk_bodies=[evt["chunk_body"]],
            )
        )
        if ok:
            emitted += 1
    print(sink.getvalue() or "(nothing emitted — sample_rate gated all events)")
    print(f"[summary] emitted={emitted}/{len(FAKE_STREAM)} events")


def main() -> int:
    parser = argparse.ArgumentParser(description="Part 5 — ops demo: PII redaction + sampling logger.")
    parser.add_argument("--demo", action="store_true", help="sample_rate=1.0 so every event is shown")
    parser.add_argument(
        "--allow-bodies",
        action="store_true",
        help="set allow_chunk_bodies=True (dangerous; for teaching only)",
    )
    parser.add_argument("--seed", type=int, default=42, help="random seed for sampling reproducibility")
    parser.add_argument("--mock", action="store_true", help="alias of --demo to fit the smoke dispatcher")
    args = parser.parse_args()

    sample_rate = 1.0 if (args.demo or args.mock) else 0.01

    _show_redaction_summary()
    _run_logger(sample_rate=sample_rate, allow_bodies=args.allow_bodies, seed=args.seed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
