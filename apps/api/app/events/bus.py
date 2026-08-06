from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.redaction import redact_copy
from app.core.config import get_settings
from app.core.redis import get_redis
from app.events.models import InvestigationEvent, InvestigationEventType

logger = logging.getLogger(__name__)

REDIS_CHANNEL_PREFIX = "investigation:events:"


def _channel(incident_id: uuid.UUID) -> str:
    return f"{REDIS_CHANNEL_PREFIX}{incident_id}"


async def _next_seq(session: AsyncSession, incident_id: uuid.UUID, *, max_retries: int = 5) -> int:
    for _ in range(max_retries):
        result = await session.execute(
            select(func.coalesce(func.max(InvestigationEvent.seq), 0)).where(
                InvestigationEvent.incident_id == incident_id
            )
        )
        return int(result.scalar_one()) + 1
    raise RuntimeError("Unable to allocate investigation event sequence")


async def publish_event(
    session: AsyncSession,
    *,
    incident_id: uuid.UUID,
    agent_run_id: uuid.UUID | None,
    event_type: InvestigationEventType | str,
    payload: dict[str, Any],
    occurred_at: datetime | None = None,
) -> InvestigationEvent:
    """Persist and publish an investigation event (payload redacted per SPEC-02)."""
    settings = get_settings()
    redacted_payload = redact_copy(payload)
    event_type_str = str(event_type)
    now = occurred_at or datetime.now(UTC)

    for attempt in range(3):
        seq = await _next_seq(session, incident_id)
        event = InvestigationEvent(
            id=uuid.uuid4(),
            incident_id=incident_id,
            agent_run_id=agent_run_id,
            seq=seq,
            type=event_type_str,
            occurred_at=now,
            payload=redacted_payload,
        )
        session.add(event)
        try:
            await session.flush()
            break
        except IntegrityError:
            await session.rollback()
            if attempt == 2:
                raise
            continue

    message = {
        "id": str(event.id),
        "incident_id": str(incident_id),
        "agent_run_id": str(agent_run_id) if agent_run_id else None,
        "seq": event.seq,
        "type": event_type_str,
        "occurred_at": event.occurred_at.isoformat(),
        "payload": redacted_payload,
    }
    try:
        await get_redis().publish(_channel(incident_id), json.dumps(message))
    except Exception:
        logger.exception(
            "investigation_event_publish_failed",
            extra={"incident_id": str(incident_id), "seq": event.seq},
        )

    if settings.event_retention_hours > 0:
        pass  # retention enforced at query time via occurred_at filter

    return event


async def list_events_after_seq(
    session: AsyncSession,
    *,
    incident_id: uuid.UUID,
    after_seq: int = 0,
    limit: int = 500,
) -> list[InvestigationEvent]:
    settings = get_settings()
    cutoff = None
    if settings.event_retention_hours > 0:
        from datetime import timedelta

        cutoff = datetime.now(UTC) - timedelta(hours=settings.event_retention_hours)

    query = (
        select(InvestigationEvent)
        .where(
            InvestigationEvent.incident_id == incident_id,
            InvestigationEvent.seq > after_seq,
        )
        .order_by(InvestigationEvent.seq.asc())
        .limit(limit)
    )
    if cutoff is not None:
        query = query.where(InvestigationEvent.occurred_at >= cutoff)

    result = await session.execute(query)
    return list(result.scalars().all())


async def get_latest_seq(session: AsyncSession, incident_id: uuid.UUID) -> int:
    result = await session.execute(
        select(func.coalesce(func.max(InvestigationEvent.seq), 0)).where(
            InvestigationEvent.incident_id == incident_id
        )
    )
    return int(result.scalar_one())


def event_to_sse(event: InvestigationEvent) -> tuple[str, str, str]:
    """Return (event_type, event_id, data_json) for SSE framing."""
    data = {
        "incident_id": str(event.incident_id),
        "agent_run_id": str(event.agent_run_id) if event.agent_run_id else None,
        "seq": event.seq,
        "type": event.type,
        "occurred_at": event.occurred_at.isoformat(),
        "payload": event.payload,
    }
    return event.type, str(event.seq), json.dumps(data, separators=(",", ":"))
