from __future__ import annotations

import pytest
from app.audit.redaction import REDACTED, redact


@pytest.mark.parametrize(
    ("payload", "expected_fragment"),
    [
        ({"password": "secret123"}, REDACTED),
        ({"access_token": "jwt-value"}, REDACTED),
        ({"authorization": "Bearer abc"}, REDACTED),
        ({"nested": {"refresh_token": "token"}}, REDACTED),
        ({"email": "user@example.com"}, REDACTED),
        ({"phone": "555-123-4567"}, REDACTED),
        ({"note": "contact user@example.com today"}, REDACTED),
    ],
)
def test_redact_sensitive_values(payload: dict[str, object], expected_fragment: str) -> None:
    result = redact(payload)
    serialized = str(result)
    assert expected_fragment in serialized
    if "password" in payload:
        assert payload["password"] not in serialized


def test_redact_preserves_safe_fields() -> None:
    payload = {"incident_id": "abc-123", "status": "open"}
    assert redact(payload) == payload
