from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_ok(client: AsyncClient) -> None:
    with (
        patch("app.api.routes.check_db_connection", new=AsyncMock(return_value=True)),
        patch("app.api.routes._check_redis", new=AsyncMock(return_value=True)),
    ):
        response = await client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["checks"] == {"db": "ok", "redis": "ok"}
    assert "version" in payload
    assert "git_sha" in payload


@pytest.mark.asyncio
async def test_health_degraded_when_db_unavailable(client: AsyncClient) -> None:
    with (
        patch("app.api.routes.check_db_connection", new=AsyncMock(return_value=False)),
        patch("app.api.routes._check_redis", new=AsyncMock(return_value=True)),
    ):
        response = await client.get("/health")

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["checks"]["db"] == "fail"
    assert payload["checks"]["redis"] == "ok"


@pytest.mark.asyncio
async def test_health_degraded_when_redis_unavailable(client: AsyncClient) -> None:
    with (
        patch("app.api.routes.check_db_connection", new=AsyncMock(return_value=True)),
        patch("app.api.routes._check_redis", new=AsyncMock(return_value=False)),
    ):
        response = await client.get("/health")

    assert response.status_code == 503
    payload = response.json()
    assert payload["checks"]["redis"] == "fail"
