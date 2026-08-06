from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.events.bus import publish_event
from app.events.models import InvestigationEvent, InvestigationEventType
from sqlalchemy.exc import IntegrityError


@pytest.mark.asyncio
async def test_publish_event_retries_on_seq_conflict(monkeypatch: pytest.MonkeyPatch) -> None:
    incident_id = uuid.uuid4()
    session = AsyncMock()
    seq_calls = {"n": 0}

    async def fake_next_seq(
        _session: object, _incident_id: uuid.UUID, *, max_retries: int = 5
    ) -> int:
        seq_calls["n"] += 1
        return seq_calls["n"]

    monkeypatch.setattr("app.events.bus._next_seq", fake_next_seq)
    monkeypatch.setattr("app.events.bus.redact_copy", lambda payload: payload)
    monkeypatch.setattr("app.events.bus.get_redis", lambda: AsyncMock(publish=AsyncMock()))

    flush_count = {"n": 0}

    async def fake_flush() -> None:
        flush_count["n"] += 1
        if flush_count["n"] == 1:
            raise IntegrityError("duplicate seq", params=None, orig=Exception())

    session.flush = fake_flush
    session.add = MagicMock()

    event = await publish_event(
        session,
        incident_id=incident_id,
        agent_run_id=uuid.uuid4(),
        event_type=InvestigationEventType.NODE_STARTED,
        payload={"node": "collect_metrics"},
    )

    assert isinstance(event, InvestigationEvent)
    assert flush_count["n"] == 2
    assert seq_calls["n"] == 2


@pytest.mark.asyncio
async def test_list_events_after_seq_orders_by_sequence(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.events.bus import list_events_after_seq

    incident_id = uuid.uuid4()
    events = [
        InvestigationEvent(
            id=uuid.uuid4(),
            incident_id=incident_id,
            agent_run_id=uuid.uuid4(),
            seq=2,
            type="node_completed",
            occurred_at=datetime.now(UTC),
            payload={},
        ),
        InvestigationEvent(
            id=uuid.uuid4(),
            incident_id=incident_id,
            agent_run_id=uuid.uuid4(),
            seq=3,
            type="node_started",
            occurred_at=datetime.now(UTC),
            payload={},
        ),
    ]

    class _Result:
        def scalars(self) -> _Result:
            return self

        def all(self) -> list[InvestigationEvent]:
            return events

    session = AsyncMock()
    session.execute = AsyncMock(return_value=_Result())

    listed = await list_events_after_seq(session, incident_id=incident_id, after_seq=1)
    assert [item.seq for item in listed] == [2, 3]
