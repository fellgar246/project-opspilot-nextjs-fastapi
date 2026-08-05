from __future__ import annotations

import uuid
from typing import Any

from app.audit.event_types import AuditEventType
from app.audit.models import AuditEvent
from app.audit.redaction import redact
from sqlalchemy.ext.asyncio import AsyncSession


async def record_audit_event(
    session: AsyncSession,
    *,
    actor_type: str,
    actor_id: uuid.UUID | None,
    event_type: AuditEventType | str,
    entity_type: str,
    entity_id: uuid.UUID | None,
    payload: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> AuditEvent:
    event = AuditEvent(
        actor_type=actor_type,
        actor_id=actor_id,
        event_type=str(event_type.value if isinstance(event_type, AuditEventType) else event_type),
        entity_type=entity_type,
        entity_id=entity_id,
        payload=redact(payload or {}),
        request_id=request_id,
    )
    session.add(event)
    await session.flush()
    return event
