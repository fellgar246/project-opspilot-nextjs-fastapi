from __future__ import annotations

import re
from dataclasses import dataclass, field

from opspilot.tools.redaction import redact

UNTRUSTED_START = "<<<UNTRUSTED_EXTERNAL_DATA>>>"
UNTRUSTED_END = "<<<END_UNTRUSTED_EXTERNAL_DATA>>>"

CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
ROLE_MARKERS = re.compile(
    r"(?i)(ignore (all )?previous instructions|you are now|system:|assistant:|user:|<\|im_start\|>)"
)
INJECTION_PATTERNS = [
    re.compile(r"(?i)ignore previous instructions"),
    re.compile(r"(?i)execute:\s*"),
    re.compile(r"(?i)\$\{?SECRETS?\}?"),
    re.compile(r"(?i)curl\s+http"),
]


@dataclass
class SanitizeResult:
    text: str
    suspicious: bool = False
    reasons: list[str] = field(default_factory=list)


def _detect_suspicious(text: str) -> list[str]:
    reasons: list[str] = []
    if ROLE_MARKERS.search(text):
        reasons.append("role_marker")
    for pattern in INJECTION_PATTERNS:
        if pattern.search(text):
            reasons.append(f"pattern:{pattern.pattern[:30]}")
    return reasons


def sanitize_text(text: str) -> SanitizeResult:
    reasons = _detect_suspicious(text)
    cleaned = CONTROL_CHARS.sub("", text)
    cleaned = redact(cleaned)
    wrapped = f"{UNTRUSTED_START}\n{cleaned}\n{UNTRUSTED_END}"
    return SanitizeResult(text=wrapped, suspicious=bool(reasons), reasons=reasons)


def sanitize_value(value: object) -> tuple[object, list[str]]:
    reasons: list[str] = []
    if isinstance(value, str):
        result = sanitize_text(value)
        return result.text, result.reasons
    if isinstance(value, dict):
        out: dict[str, object] = {}
        for key, item in value.items():
            sanitized, item_reasons = sanitize_value(item)
            out[key] = sanitized
            reasons.extend(item_reasons)
        return out, reasons
    if isinstance(value, list):
        out_list: list[object] = []
        for item in value:
            sanitized, item_reasons = sanitize_value(item)
            out_list.append(sanitized)
            reasons.extend(item_reasons)
        return out_list, reasons
    return value, reasons
