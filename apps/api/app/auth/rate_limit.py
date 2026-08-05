from __future__ import annotations

from app.audit.event_types import AuditEventType
from app.audit.service import record_audit_event
from app.core.config import Settings
from app.core.errors import AppError
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession


def _rate_limit_key(kind: str, value: str) -> str:
    return f"auth:rate:{kind}:{value}"


async def check_auth_rate_limit(
    *,
    redis: Redis,
    settings: Settings,
    ip_address: str,
    email: str,
) -> None:
    window = settings.auth_rate_limit_window_seconds
    limit = settings.auth_rate_limit_attempts
    keys = (_rate_limit_key("ip", ip_address), _rate_limit_key("email", email.strip().lower()))
    for key in keys:
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, window)
        if count > limit:
            raise AppError("Too many login attempts", status_code=429)


async def record_rate_limited(
    session: AsyncSession,
    *,
    email: str,
    ip_address: str,
    request_id: str | None,
) -> None:
    await record_audit_event(
        session,
        actor_type="system",
        actor_id=None,
        event_type=AuditEventType.AUTH_RATE_LIMITED,
        entity_type="auth",
        entity_id=None,
        payload={"email": email, "ip_address": ip_address},
        request_id=request_id,
    )
    await session.commit()
