from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Response, status
from redis.asyncio import Redis

from app.api.health import HealthResponse
from app.core.config import Settings, get_settings
from app.db.session import check_db_connection

router = APIRouter(tags=["health"])


async def _check_redis(redis_url: str) -> bool:
    client = Redis.from_url(redis_url, decode_responses=True)
    try:
        return bool(await client.ping())
    except Exception:
        return False
    finally:
        await client.aclose()


@router.get("/health", response_model=HealthResponse)
async def health(
    response: Response,
    settings: Settings = Depends(get_settings),
) -> HealthResponse:
    db_ok = await check_db_connection()
    redis_ok = await _check_redis(str(settings.redis_url))

    checks: dict[str, Literal["ok", "fail"]] = {
        "db": "ok" if db_ok else "fail",
        "redis": "ok" if redis_ok else "fail",
    }
    all_ok = all(value == "ok" for value in checks.values())
    response.status_code = status.HTTP_200_OK if all_ok else status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status="ok" if all_ok else "degraded",
        version=settings.app_version,
        git_sha=settings.git_sha,
        checks=checks,
    )
