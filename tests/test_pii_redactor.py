"""Part 5 — Tests for the regex-based PII redactor.

The fixtures cover every detector class in src/rag/pii_redactor with
both positive and negative cases. Failures here are *blocking* because
the article tells readers to depend on this module as a teaching
baseline; silent regressions would propagate to copy-paste users.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from rag.pii_redactor import luhn_valid, redact, redact_with_report  # noqa: E402


def test_email_is_redacted() -> None:
    out = redact("ご連絡先: alice.smith+test@example.co.jp")
    assert "alice" not in out
    assert "[REDACTED_EMAIL]" in out


def test_phone_jp_is_redacted() -> None:
    out = redact("緊急連絡: 03-1234-5678 / 090-0000-1111")
    assert "1234" not in out
    assert out.count("[REDACTED_PHONE]") == 2


def test_phone_intl_is_redacted() -> None:
    out = redact("Call +1 415 555 1212 outside hours")
    assert "555" not in out
    assert "[REDACTED_PHONE]" in out


def test_credit_card_pattern_is_redacted() -> None:
    out = redact("カード 4242 4242 4242 4242 で支払い")
    assert "4242" not in out
    assert "[REDACTED_CC]" in out


def test_api_key_patterns_are_redacted() -> None:
    out = redact("anthropic sk-thisisafakekey0123456789abcd / slack xoxb-1111-2222-thisisaslackbottoken")
    assert "sk-thisisafake" not in out
    assert "xoxb-1111-2222" not in out
    assert out.count("[REDACTED_KEY]") == 2


def test_ipv4_is_redacted() -> None:
    out = redact("internal host 10.0.42.7 unreachable")
    assert "10.0.42.7" not in out
    assert "[REDACTED_IP]" in out


def test_negative_no_pii_unchanged() -> None:
    text = "今日は晴れです。Stratus の Sev1 は 5 分以内に acknowledge する。"
    assert redact(text) == text


def test_idempotent() -> None:
    one = redact("email a@b.co / phone 03-1234-5678")
    two = redact(one)
    assert one == two


def test_report_counts_each_detector() -> None:
    rep = redact_with_report(
        "two emails a@b.co and c@d.co; one phone 090-1111-2222; one ip 10.0.0.1"
    )
    assert rep.hits.get("email") == 2
    assert rep.hits.get("phone_jp") == 1
    assert rep.hits.get("ipv4") == 1


def test_luhn_valid_examples() -> None:
    # 4242... is a well-known Stripe test card; passes Luhn.
    assert luhn_valid("4242 4242 4242 4242") is True
    # A digit run that isn't a real card should fail Luhn.
    assert luhn_valid("1234 5678 9012 3456") is False
    # Too short
    assert luhn_valid("1234") is False
