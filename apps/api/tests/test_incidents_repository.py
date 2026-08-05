from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.incidents.models import Incident, IncidentSeverity, IncidentSource, IncidentStatus
from app.incidents.repository import (
    decode_cursor,
    decode_float_cursor,
    encode_cursor,
    encode_float_cursor,
    list_incidents,
    list_notes,
    list_status_history,
)


def _incident() -> Incident:
    now = datetime.now(UTC)
    return Incident(
        id=uuid.uuid4(),
        title="Test",
        description="Test",
        severity=IncidentSeverity.SEV3,
        status=IncidentStatus.OPEN,
        source=IncidentSource.MANUAL,
        started_at=now,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_list_incidents_returns_cursor_page() -> None:
    session = AsyncMock()
    incident = _incident()

    list_result = MagicMock()
    list_result.scalars = MagicMock(return_value=MagicMock(unique=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[incident])))))

    count_result = MagicMock()
    count_result.scalar_one = MagicMock(return_value=1)

    session.execute = AsyncMock(side_effect=[list_result, count_result])

    page = await list_incidents(session, limit=50)
    assert page.total_estimate == 1
    assert page.items[0].title == "Test"


@pytest.mark.asyncio
async def test_list_incidents_with_next_cursor() -> None:
    session = AsyncMock()
    incidents = [_incident() for _ in range(3)]

    list_result = MagicMock()
    list_result.scalars = MagicMock(
        return_value=MagicMock(unique=MagicMock(return_value=MagicMock(all=MagicMock(return_value=incidents))))
    )
    count_result = MagicMock()
    count_result.scalar_one = MagicMock(return_value=3)
    session.execute = AsyncMock(side_effect=[list_result, count_result])

    page = await list_incidents(session, limit=2)
    assert len(page.items) == 2
    assert page.next_cursor is not None


@pytest.mark.asyncio
async def test_list_status_history_and_notes() -> None:
    session = AsyncMock()
    empty = MagicMock()
    empty.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
    session.execute = AsyncMock(return_value=empty)

    assert await list_status_history(session, uuid.uuid4()) == []
    assert await list_notes(session, uuid.uuid4()) == []


def test_float_cursor_roundtrip() -> None:
    item_id = uuid.uuid4()
    cursor = encode_float_cursor(0.85, item_id)
    confidence, decoded_id = decode_float_cursor(cursor)
    assert confidence == 0.85
    assert decoded_id == item_id


def test_decode_cursor_invalid() -> None:
    with pytest.raises(ValueError):
        decode_cursor("bad")
