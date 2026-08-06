from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_capability
from app.auth.models import User
from app.auth.policy import Capability
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.redis import get_redis
from app.db.session import get_session, get_session_factory
from app.events.bus import REDIS_CHANNEL_PREFIX, event_to_sse, list_events_after_seq
from app.events.models import TERMINAL_EVENT_TYPES, InvestigationEvent
from app.events.schemas import InvestigationEventListResponse, InvestigationEventRead
from app.incidents.service import require_incident

logger = logging.getLogger(__name__)

router = APIRouter(tags=["events"])

_active_connections: dict[str, set[str]] = defaultdict(set)
_connection_lock = asyncio.Lock()


async def _register_connection(user_id: str, connection_id: str) -> None:
    settings = get_settings()
    async with _connection_lock:
        active = _active_connections[user_id]
        if len(active) >= settings.sse_max_connections_per_user:
            oldest = next(iter(active))
            active.discard(oldest)
        active.add(connection_id)


async def _unregister_connection(user_id: str, connection_id: str) -> None:
    async with _connection_lock:
        _active_connections[user_id].discard(connection_id)
        if not _active_connections[user_id]:
            del _active_connections[user_id]


def _parse_last_event_id(last_event_id: str | None) -> int:
    if not last_event_id:
        return 0
    try:
        return int(last_event_id)
    except ValueError as exc:
        raise AppError("Invalid Last-Event-ID header", status_code=400) from exc


async def _is_seq_outside_retention(session: AsyncSession, incident_id: UUID, after_seq: int) -> bool:
    settings = get_settings()
    if settings.event_retention_hours <= 0 or after_seq <= 0:
        return False
    result = await session.execute(
        select(InvestigationEvent.occurred_at).where(
            InvestigationEvent.incident_id == incident_id,
            InvestigationEvent.seq == after_seq,
        )
    )
    anchor = result.scalar_one_or_none()
    if anchor is None:
        max_seq = await session.execute(
            select(func.coalesce(func.max(InvestigationEvent.seq), 0)).where(
                InvestigationEvent.incident_id == incident_id
            )
        )
        return int(max_seq.scalar_one()) > after_seq
    from datetime import UTC, datetime, timedelta

    cutoff = datetime.now(UTC) - timedelta(hours=settings.event_retention_hours)
    return anchor < cutoff


async def _event_stream(
    *,
    incident_id: UUID,
    user_id: str,
    connection_id: str,
    after_seq: int,
):
    settings = get_settings()
    redis = get_redis()
    pubsub = redis.pubsub()
    channel = f"{REDIS_CHANNEL_PREFIX}{incident_id}"
    delivered: set[int] = set()
    terminal_sent = False
    session_factory = get_session_factory()

    try:
        async with session_factory() as session:
            if await _is_seq_outside_retention(session, incident_id, after_seq):
                yield 'event: retention_expired\ndata: {"reload":true}\n\n'
                return

            backlog = await list_events_after_seq(session, incident_id=incident_id, after_seq=after_seq)
            for event in backlog:
                if event.seq in delivered:
                    continue
                delivered.add(event.seq)
                event_type, event_id, data = event_to_sse(event)
                yield f"event: {event_type}\nid: {event_id}\ndata: {data}\n\n"
                if event.type in {t.value for t in TERMINAL_EVENT_TYPES}:
                    terminal_sent = True

        if terminal_sent:
            return

        await pubsub.subscribe(channel)
        keepalive_ticks = 0
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message.get("type") == "message":
                payload = json.loads(message["data"])
                seq = int(payload["seq"])
                if seq <= after_seq or seq in delivered:
                    continue
                delivered.add(seq)
                event_type = payload["type"]
                data = json.dumps(
                    {
                        "incident_id": payload["incident_id"],
                        "agent_run_id": payload.get("agent_run_id"),
                        "seq": seq,
                        "type": event_type,
                        "occurred_at": payload["occurred_at"],
                        "payload": payload.get("payload", {}),
                    },
                    separators=(",", ":"),
                )
                yield f"event: {event_type}\nid: {seq}\ndata: {data}\n\n"
                if event_type in {t.value for t in TERMINAL_EVENT_TYPES}:
                    break

            keepalive_ticks += 1
            if keepalive_ticks >= settings.sse_keepalive_seconds:
                yield ": keep-alive\n\n"
                keepalive_ticks = 0
            await asyncio.sleep(0.05)
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()
        await _unregister_connection(user_id, connection_id)


@router.get("/incidents/{incident_id}/events")
async def stream_incident_events(
    request: Request,
    incident_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(require_capability(Capability.READ_INCIDENTS))],
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    await require_incident(session, incident_id)
    after_seq = _parse_last_event_id(last_event_id)
    connection_id = f"{request.client.host if request.client else 'unknown'}:{id(request)}"
    await _register_connection(str(user.id), connection_id)

    async def generator():
        try:
            async for chunk in _event_stream(
                incident_id=incident_id,
                user_id=str(user.id),
                connection_id=connection_id,
                after_seq=after_seq,
            ):
                yield chunk
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("sse_stream_error", extra={"incident_id": str(incident_id)})
        finally:
            await _unregister_connection(str(user.id), connection_id)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/incidents/{incident_id}/events/history", response_model=InvestigationEventListResponse)
async def list_incident_event_history(
    incident_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(require_capability(Capability.READ_INCIDENTS))],
    after_seq: int = 0,
) -> InvestigationEventListResponse:
    await require_incident(session, incident_id)
    events = await list_events_after_seq(session, incident_id=incident_id, after_seq=after_seq)
    latest = events[-1].seq if events else after_seq
    return InvestigationEventListResponse(
        items=[
            InvestigationEventRead(
                id=str(event.id),
                incident_id=str(event.incident_id),
                agent_run_id=str(event.agent_run_id) if event.agent_run_id else None,
                seq=event.seq,
                type=event.type,
                occurred_at=event.occurred_at,
                payload=event.payload,
            )
            for event in events
        ],
        latest_seq=latest,
    )
