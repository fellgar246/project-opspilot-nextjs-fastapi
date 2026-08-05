from __future__ import annotations

from redis.asyncio import Redis

from app.core.config import Settings

_redis_client: Redis | None = None


def init_redis(settings: Settings) -> None:
    global _redis_client
    _redis_client = Redis.from_url(str(settings.redis_url), decode_responses=True)


async def close_redis() -> None:
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None


def get_redis() -> Redis:
    if _redis_client is None:
        raise RuntimeError("Redis not initialized")
    return _redis_client
