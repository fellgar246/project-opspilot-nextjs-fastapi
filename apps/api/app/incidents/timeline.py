from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.incidents.models import Evidence, Hypothesis
from app.incidents.repository import list_notes, list_status_history

TimelineKind = Literal[
    "status_change",
    "note",
    "evidence_collected",
    "hypothesis_created",
    "action_proposed",
    "approval_decided",
    "action_executed",
    "agent_event",
]


@dataclass(frozen=True)
class TimelineEntry:
    id: uuid.UUID
    occurred_at: datetime
    kind: TimelineKind
    actor_type: str
    actor_id: uuid.UUID | None
    title: str
    description: str | None
    reference: dict[str, Any] | None


TimelineProvider = Callable[[AsyncSession, uuid.UUID], Awaitable[list[TimelineEntry]]]


async def _status_change_provider(
    session: AsyncSession, incident_id: uuid.UUID
) -> list[TimelineEntry]:
    entries: list[TimelineEntry] = []
    for record in await list_status_history(session, incident_id):
        description: str | None
        if record.from_status is None:
            title = "Incident created"
            description = record.reason or f"Status set to {record.to_status.value}"
        else:
            title = f"Status changed to {record.to_status.value}"
            description = record.reason
        entries.append(
            TimelineEntry(
                id=record.id,
                occurred_at=record.occurred_at,
                kind="status_change",
                actor_type=record.actor_type,
                actor_id=record.actor_id,
                title=title,
                description=description,
                reference={
                    "from_status": record.from_status.value if record.from_status else None,
                    "to_status": record.to_status.value,
                },
            )
        )
    return entries


async def _note_provider(session: AsyncSession, incident_id: uuid.UUID) -> list[TimelineEntry]:
    return [
        TimelineEntry(
            id=note.id,
            occurred_at=note.created_at,
            kind="note",
            actor_type=note.actor_type,
            actor_id=note.actor_id,
            title="Manual note",
            description=note.content,
            reference={"note_id": str(note.id)},
        )
        for note in await list_notes(session, incident_id)
    ]


async def _evidence_provider(session: AsyncSession, incident_id: uuid.UUID) -> list[TimelineEntry]:
    result = await session.execute(
        select(Evidence)
        .where(Evidence.incident_id == incident_id)
        .order_by(Evidence.observed_at, Evidence.id)
    )
    return [
        TimelineEntry(
            id=evidence.id,
            occurred_at=evidence.collected_at,
            kind="evidence_collected",
            actor_type="system",
            actor_id=None,
            title=evidence.title,
            description=evidence.content[:500] if evidence.content else None,
            reference={
                "evidence_id": str(evidence.id),
                "source_type": evidence.source_type.value,
                "source_reference": evidence.source_reference,
            },
        )
        for evidence in result.scalars().all()
    ]


async def _hypothesis_provider(
    session: AsyncSession, incident_id: uuid.UUID
) -> list[TimelineEntry]:
    result = await session.execute(
        select(Hypothesis)
        .where(Hypothesis.incident_id == incident_id)
        .order_by(Hypothesis.created_at, Hypothesis.id)
    )
    return [
        TimelineEntry(
            id=hypothesis.id,
            occurred_at=hypothesis.created_at,
            kind="hypothesis_created",
            actor_type="system",
            actor_id=None,
            title="Hypothesis created",
            description=hypothesis.statement,
            reference={
                "hypothesis_id": str(hypothesis.id),
                "confidence": hypothesis.confidence,
                "status": hypothesis.status.value,
            },
        )
        for hypothesis in result.scalars().all()
    ]


TIMELINE_PROVIDERS: list[TimelineProvider] = [
    _status_change_provider,
    _note_provider,
    _evidence_provider,
    _hypothesis_provider,
]


async def assemble_timeline(session: AsyncSession, incident_id: uuid.UUID) -> list[TimelineEntry]:
    entries: list[TimelineEntry] = []
    for provider in TIMELINE_PROVIDERS:
        entries.extend(await provider(session, incident_id))
    entries.sort(key=lambda entry: (entry.occurred_at, entry.id))
    return entries
