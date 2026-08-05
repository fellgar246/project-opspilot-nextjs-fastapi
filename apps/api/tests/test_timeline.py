from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.incidents.models import IncidentStatus
from app.incidents.timeline import TimelineEntry, assemble_timeline


@pytest.mark.asyncio
async def test_assemble_timeline_sorts_by_occurred_at_then_id(monkeypatch: pytest.MonkeyPatch) -> None:
    fixed = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    id_a = uuid.UUID("00000000-0000-0000-0000-000000000001")
    id_b = uuid.UUID("00000000-0000-0000-0000-000000000002")

    async def provider_a(session, incident_id):
        return [
            TimelineEntry(
                id=id_b,
                occurred_at=fixed,
                kind="note",
                actor_type="user",
                actor_id=None,
                title="B",
                description=None,
                reference=None,
            )
        ]

    async def provider_b(session, incident_id):
        return [
            TimelineEntry(
                id=id_a,
                occurred_at=fixed,
                kind="status_change",
                actor_type="user",
                actor_id=None,
                title="A",
                description=None,
                reference={"to_status": IncidentStatus.OPEN.value},
            )
        ]

    monkeypatch.setattr("app.incidents.timeline.TIMELINE_PROVIDERS", [provider_a, provider_b])
    session = AsyncMock()
    timeline = await assemble_timeline(session, uuid.uuid4())
    assert [entry.id for entry in timeline] == [id_a, id_b]
