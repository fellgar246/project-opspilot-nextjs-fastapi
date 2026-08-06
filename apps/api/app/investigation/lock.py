from __future__ import annotations

import uuid

from redis.asyncio import Redis

LOCK_PREFIX = "investigation:lock:"
LOCK_TTL_SECONDS = 3600


def lock_key(incident_id: uuid.UUID) -> str:
    return f"{LOCK_PREFIX}{incident_id}"


async def acquire_investigation_lock(
    redis: Redis,
    *,
    incident_id: uuid.UUID,
    agent_run_id: uuid.UUID,
) -> bool:
    return bool(
        await redis.set(
            lock_key(incident_id),
            str(agent_run_id),
            nx=True,
            ex=LOCK_TTL_SECONDS,
        )
    )


async def release_investigation_lock(redis: Redis, *, incident_id: uuid.UUID) -> None:
    await redis.delete(lock_key(incident_id))


async def get_lock_owner(redis: Redis, *, incident_id: uuid.UUID) -> str | None:
    return await redis.get(lock_key(incident_id))
