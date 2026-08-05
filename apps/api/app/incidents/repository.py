from __future__ import annotations

import base64
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import Select, func, or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.incidents.models import (
    Evidence,
    Hypothesis,
    Incident,
    IncidentNote,
    IncidentService,
    IncidentSeverity,
    IncidentStatus,
    IncidentStatusHistory,
    Service,
)


@dataclass(frozen=True)
class CursorPage[T]:
    items: list[T]
    next_cursor: str | None
    total_estimate: int


def encode_cursor(started_at: datetime, item_id: uuid.UUID) -> str:
    raw = f"{started_at.isoformat()}|{item_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def encode_float_cursor(value: float, item_id: uuid.UUID) -> str:
    raw = f"{value}|{item_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def decode_float_cursor(cursor: str) -> tuple[float, uuid.UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        value_str, item_id_str = raw.split("|", 1)
        return float(value_str), uuid.UUID(item_id_str)
    except (ValueError, TypeError) as exc:
        raise ValueError("Invalid cursor") from exc


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        started_at_str, item_id_str = raw.split("|", 1)
        return datetime.fromisoformat(started_at_str), uuid.UUID(item_id_str)
    except (ValueError, TypeError) as exc:
        raise ValueError("Invalid cursor") from exc


def _apply_incident_filters(
    query: Select[Any],
    *,
    status: IncidentStatus | None,
    severity: IncidentSeverity | None,
    service_id: uuid.UUID | None,
    started_from: datetime | None,
    started_to: datetime | None,
    search: str | None,
) -> Select[Any]:
    if status is not None:
        query = query.where(Incident.status == status)
    if severity is not None:
        query = query.where(Incident.severity == severity)
    if service_id is not None:
        query = query.join(IncidentService).where(IncidentService.service_id == service_id)
    if started_from is not None:
        query = query.where(Incident.started_at >= started_from)
    if started_to is not None:
        query = query.where(Incident.started_at <= started_to)
    if search:
        pattern = f"%{search}%"
        query = query.where(or_(Incident.title.ilike(pattern), Incident.description.ilike(pattern)))
    return query


async def list_incidents(
    session: AsyncSession,
    *,
    status: IncidentStatus | None = None,
    severity: IncidentSeverity | None = None,
    service_id: uuid.UUID | None = None,
    started_from: datetime | None = None,
    started_to: datetime | None = None,
    search: str | None = None,
    cursor: str | None = None,
    limit: int = 50,
) -> CursorPage[Incident]:
    limit = min(max(limit, 1), 100)

    base_query = select(Incident).options(selectinload(Incident.service_links))
    count_query = select(func.count(func.distinct(Incident.id))).select_from(Incident)

    base_query = _apply_incident_filters(
        base_query,
        status=status,
        severity=severity,
        service_id=service_id,
        started_from=started_from,
        started_to=started_to,
        search=search,
    )
    count_query = _apply_incident_filters(
        count_query,
        status=status,
        severity=severity,
        service_id=service_id,
        started_from=started_from,
        started_to=started_to,
        search=search,
    )

    if cursor is not None:
        cursor_started_at, cursor_id = decode_cursor(cursor)
        base_query = base_query.where(
            tuple_(Incident.started_at, Incident.id) < (cursor_started_at, cursor_id)
        )

    base_query = base_query.order_by(Incident.started_at.desc(), Incident.id.desc()).limit(
        limit + 1
    )
    result = await session.execute(base_query)
    incidents = list(result.scalars().unique().all())

    next_cursor: str | None = None
    if len(incidents) > limit:
        last = incidents[limit - 1]
        next_cursor = encode_cursor(last.started_at, last.id)
        incidents = incidents[:limit]

    total_estimate = int((await session.execute(count_query)).scalar_one())
    return CursorPage(items=incidents, next_cursor=next_cursor, total_estimate=total_estimate)


async def get_incident(session: AsyncSession, incident_id: uuid.UUID) -> Incident | None:
    result = await session.execute(
        select(Incident)
        .where(Incident.id == incident_id)
        .options(selectinload(Incident.service_links))
    )
    return result.scalar_one_or_none()


async def list_services(
    session: AsyncSession,
    *,
    include_inactive: bool = False,
) -> list[Service]:
    query = select(Service).order_by(Service.name)
    if not include_inactive:
        query = query.where(Service.is_active.is_(True))
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_service(session: AsyncSession, service_id: uuid.UUID) -> Service | None:
    return await session.get(Service, service_id)


async def count_incidents_for_service(session: AsyncSession, service_id: uuid.UUID) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(IncidentService)
        .where(IncidentService.service_id == service_id)
    )
    return int(result.scalar_one())


async def list_evidence(
    session: AsyncSession,
    incident_id: uuid.UUID,
    *,
    cursor: str | None = None,
    limit: int = 50,
) -> CursorPage[Evidence]:
    limit = min(max(limit, 1), 100)
    query = select(Evidence).where(Evidence.incident_id == incident_id)

    if cursor is not None:
        cursor_observed_at, cursor_id = decode_cursor(cursor)
        query = query.where(
            tuple_(Evidence.observed_at, Evidence.id) < (cursor_observed_at, cursor_id)
        )

    query = query.order_by(Evidence.observed_at.desc(), Evidence.id.desc()).limit(limit + 1)
    result = await session.execute(query)
    items = list(result.scalars().all())

    next_cursor: str | None = None
    if len(items) > limit:
        last = items[limit - 1]
        next_cursor = encode_cursor(last.observed_at, last.id)
        items = items[:limit]

    count = await session.scalar(
        select(func.count()).select_from(Evidence).where(Evidence.incident_id == incident_id)
    )
    return CursorPage(items=items, next_cursor=next_cursor, total_estimate=int(count or 0))


async def list_hypotheses(
    session: AsyncSession,
    incident_id: uuid.UUID,
    *,
    cursor: str | None = None,
    limit: int = 50,
) -> CursorPage[Hypothesis]:
    limit = min(max(limit, 1), 100)
    query = select(Hypothesis).where(Hypothesis.incident_id == incident_id)

    if cursor is not None:
        cursor_confidence, cursor_id = decode_float_cursor(cursor)
        query = query.where(
            tuple_(Hypothesis.confidence, Hypothesis.id) < (cursor_confidence, cursor_id)
        )

    query = query.order_by(Hypothesis.confidence.desc(), Hypothesis.id.desc()).limit(limit + 1)
    result = await session.execute(query)
    items = list(result.scalars().all())

    next_cursor: str | None = None
    if len(items) > limit:
        last = items[limit - 1]
        next_cursor = encode_float_cursor(last.confidence, last.id)
        items = items[:limit]

    count = await session.scalar(
        select(func.count()).select_from(Hypothesis).where(Hypothesis.incident_id == incident_id)
    )
    return CursorPage(items=items, next_cursor=next_cursor, total_estimate=int(count or 0))


async def list_status_history(
    session: AsyncSession,
    incident_id: uuid.UUID,
) -> list[IncidentStatusHistory]:
    result = await session.execute(
        select(IncidentStatusHistory)
        .where(IncidentStatusHistory.incident_id == incident_id)
        .order_by(IncidentStatusHistory.occurred_at, IncidentStatusHistory.id)
    )
    return list(result.scalars().all())


async def list_notes(session: AsyncSession, incident_id: uuid.UUID) -> list[IncidentNote]:
    result = await session.execute(
        select(IncidentNote)
        .where(IncidentNote.incident_id == incident_id)
        .order_by(IncidentNote.created_at, IncidentNote.id)
    )
    return list(result.scalars().all())
