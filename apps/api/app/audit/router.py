from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from app.audit.models import AuditEvent
from app.auth.dependencies import require_capability
from app.auth.models import User
from app.auth.policy import Capability
from app.db.session import get_session
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/audit", tags=["audit"])


class AuditEventItem(BaseModel):
    id: str
    actor_type: str
    actor_id: str | None
    event_type: str
    entity_type: str
    entity_id: str | None
    payload: dict[str, object]
    request_id: str | None
    occurred_at: datetime


class AuditEventListResponse(BaseModel):
    items: list[AuditEventItem]
    total: int
    page: int
    page_size: int


@router.get("", response_model=AuditEventListResponse)
async def list_audit_events(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(require_capability(Capability.READ_AUDIT))],
    entity_type: str | None = None,
    entity_id: UUID | None = None,
    actor_id: UUID | None = None,
    occurred_from: datetime | None = Query(default=None, alias="from"),
    occurred_to: datetime | None = Query(default=None, alias="to"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> AuditEventListResponse:
    query = select(AuditEvent)
    count_query = select(func.count()).select_from(AuditEvent)

    if entity_type is not None:
        query = query.where(AuditEvent.entity_type == entity_type)
        count_query = count_query.where(AuditEvent.entity_type == entity_type)
    if entity_id is not None:
        query = query.where(AuditEvent.entity_id == entity_id)
        count_query = count_query.where(AuditEvent.entity_id == entity_id)
    if actor_id is not None:
        query = query.where(AuditEvent.actor_id == actor_id)
        count_query = count_query.where(AuditEvent.actor_id == actor_id)
    if occurred_from is not None:
        query = query.where(AuditEvent.occurred_at >= occurred_from)
        count_query = count_query.where(AuditEvent.occurred_at >= occurred_from)
    if occurred_to is not None:
        query = query.where(AuditEvent.occurred_at <= occurred_to)
        count_query = count_query.where(AuditEvent.occurred_at <= occurred_to)

    total = int((await session.execute(count_query)).scalar_one())
    offset = (page - 1) * page_size
    result = await session.execute(
        query.order_by(AuditEvent.occurred_at.desc()).offset(offset).limit(page_size)
    )
    events = result.scalars().all()
    return AuditEventListResponse(
        items=[
            AuditEventItem(
                id=str(event.id),
                actor_type=event.actor_type,
                actor_id=str(event.actor_id) if event.actor_id else None,
                event_type=event.event_type,
                entity_type=event.entity_type,
                entity_id=str(event.entity_id) if event.entity_id else None,
                payload=event.payload,
                request_id=event.request_id,
                occurred_at=event.occurred_at,
            )
            for event in events
        ],
        total=total,
        page=page,
        page_size=page_size,
    )
