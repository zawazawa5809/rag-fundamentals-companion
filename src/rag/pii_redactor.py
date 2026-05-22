"""Part 5 — Teaching-grade PII redactor.

Six regex-based detectors covering the easy wins. Production users should
swap this for `presidio` (Microsoft) or a paid PII service — regex never
catches names, addresses, or domain-specific identifiers (medical record
numbers, internal tenant IDs, etc.).

What this redactor IS for:
  - Showing the shape of an ingest / retrieval / output redaction pass
  - Covering the easy classes (email, phone, credit-card-shaped, etc.) so
    that example logs in CI / docs do not accidentally contain real-looking
    PII

What this redactor IS NOT:
  - A replacement for a proper NER-backed PII detector in production
  - HIPAA / GDPR / APPI compliance (consult your legal team)
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Detector definitions: (name, compiled_pattern, replacement)
# Order matters slightly — longer / more specific patterns first so that
# e.g. credit-card-shaped digit runs are not partly matched by the
# generic phone-number rule.
_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    (
        "credit_card",
        re.compile(r"\b(?:\d[ -]?){13,19}\b"),
        "[REDACTED_CC]",
    ),
    (
        "email",
        re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
        "[REDACTED_EMAIL]",
    ),
    (
        "phone_jp",
        re.compile(r"\b0\d{1,4}-\d{1,4}-\d{3,4}\b"),
        "[REDACTED_PHONE]",
    ),
    (
        "phone_intl",
        re.compile(r"\+\d{1,3}[ -]?\d{1,4}[ -]?\d{3,4}[ -]?\d{3,4}\b"),
        "[REDACTED_PHONE]",
    ),
    (
        "api_key",
        re.compile(r"\b(?:sk-[A-Za-z0-9]{20,}|xoxb-[A-Za-z0-9-]{20,}|ghp_[A-Za-z0-9]{20,})\b"),
        "[REDACTED_KEY]",
    ),
    (
        "ipv4",
        re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
        "[REDACTED_IP]",
    ),
]


@dataclass
class RedactionReport:
    redacted: str
    hits: dict[str, int]  # detector name -> count


def redact(text: str) -> str:
    """Run all 6 detectors on `text` and return the redacted string.

    Idempotent (running twice produces the same output).
    """
    return redact_with_report(text).redacted


def redact_with_report(text: str) -> RedactionReport:
    """Like `redact` but also returns a per-detector hit count."""
    out = text
    hits: dict[str, int] = {}
    for name, pattern, replacement in _PATTERNS:
        count = 0

        def _sub(_m: re.Match[str], _name=name, _replacement=replacement) -> str:
            nonlocal count
            count += 1
            return _replacement

        out = pattern.sub(_sub, out)
        if count:
            hits[name] = count
    return RedactionReport(redacted=out, hits=hits)


def luhn_valid(number: str) -> bool:
    """Optional companion to credit_card: validate Luhn checksum.

    The redactor itself does not enforce Luhn (digit-run matches alone
    cover the common false positives well enough for teaching). Callers
    that need lower false-positive rates can post-filter using this.
    """
    digits = [int(c) for c in number if c.isdigit()]
    if len(digits) < 13:
        return False
    checksum = 0
    parity = len(digits) % 2
    for i, d in enumerate(digits):
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0
