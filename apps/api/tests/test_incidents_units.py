from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from app.core.errors import AppError
from app.incidents.repository import decode_cursor, encode_cursor, encode_float_cursor
from app.incidents.service import compute_evidence_checksum


def test_encode_decode_cursor_roundtrip() -> None:
    started_at = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
    item_id = uuid.uuid4()
    cursor = encode_cursor(started_at, item_id)
    decoded_at, decoded_id = decode_cursor(cursor)
    assert decoded_at == started_at
    assert decoded_id == item_id


def test_evidence_checksum_is_stable() -> None:
    checksum_a = compute_evidence_checksum("hello", {"metric_name": "x", "value": 1.0})
    checksum_b = compute_evidence_checksum("hello", {"metric_name": "x", "value": 1.0})
    assert checksum_a == checksum_b


def test_evidence_checksum_normalizes_whitespace() -> None:
    a = compute_evidence_checksum("hello", {})
    b = compute_evidence_checksum("  hello  ", {})
    assert a == b


def test_decode_invalid_cursor_raises() -> None:
    with pytest.raises(ValueError, match="Invalid cursor"):
        decode_cursor("not-a-cursor")
