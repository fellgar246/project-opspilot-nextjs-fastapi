from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

REDACTED = "[REDACTED]"

SENSITIVE_KEYS = {
    "password",
    "password_hash",
    "token",
    "access_token",
    "refresh_token",
    "authorization",
    "api_key",
    "secret",
    "ssn",
    "credit_card",
}

EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_PATTERN = re.compile(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b")


def _redact_string(value: str) -> str:
    redacted = EMAIL_PATTERN.sub(REDACTED, value)
    return PHONE_PATTERN.sub(REDACTED, redacted)


def redact(payload: Any) -> Any:
    if payload is None:
        return None
    if isinstance(payload, dict):
        result: dict[str, Any] = {}
        for key, value in payload.items():
            if key.lower() in SENSITIVE_KEYS:
                result[key] = REDACTED
            else:
                result[key] = redact(value)
        return result
    if isinstance(payload, list):
        return [redact(item) for item in payload]
    if isinstance(payload, str):
        return _redact_string(payload)
    return payload


def redact_copy(payload: Any) -> Any:
    return redact(deepcopy(payload))
