from __future__ import annotations

from pathlib import Path

from opspilot.tools.sanitize import UNTRUSTED_END, UNTRUSTED_START, sanitize_text

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_sanitize_wraps_untrusted_content() -> None:
    result = sanitize_text("hello world")
    assert result.text.startswith(UNTRUSTED_START)
    assert result.text.endswith(UNTRUSTED_END)
    assert "hello world" in result.text


def test_malicious_runbook_is_flagged() -> None:
    path = REPO_ROOT / "simulator/data/runbooks/RB-015-prompt-injection.md"
    content = path.read_text(encoding="utf-8")
    result = sanitize_text(content)
    assert result.suspicious
    assert "IGNORE PREVIOUS INSTRUCTIONS" not in result.text or UNTRUSTED_START in result.text


def test_secrets_redacted_in_sanitized_content() -> None:
    result = sanitize_text("token=sk-abcdefghijklmnopqrstuvwxyz123456")
    assert "[REDACTED]" in result.text
    assert "sk-abc" not in result.text
