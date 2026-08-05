from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from app.auth.policy import Capability, role_has_capability
from httpx import AsyncClient


def test_role_capability_matrix() -> None:
    assert role_has_capability("viewer", Capability.READ_INCIDENTS)
    assert not role_has_capability("viewer", Capability.CREATE_INCIDENTS)
    assert role_has_capability("operator", Capability.PROPOSE_MITIGATION)
    assert not role_has_capability("operator", Capability.READ_AUDIT)
    assert role_has_capability("approver", Capability.READ_AUDIT)
    assert role_has_capability("admin", Capability.RUN_EVALUATIONS)


@pytest.mark.asyncio
async def test_request_id_header_propagated(client: AsyncClient) -> None:
    with (
        patch("app.api.routes.check_db_connection", new=AsyncMock(return_value=True)),
        patch("app.api.routes._check_redis", new=AsyncMock(return_value=True)),
    ):
        response = await client.get("/health", headers={"X-Request-ID": "req-test-123"})
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == "req-test-123"


@pytest.mark.asyncio
async def test_request_id_generated_when_missing(client: AsyncClient) -> None:
    with (
        patch("app.api.routes.check_db_connection", new=AsyncMock(return_value=True)),
        patch("app.api.routes._check_redis", new=AsyncMock(return_value=True)),
    ):
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")


@pytest.mark.asyncio
async def test_audit_endpoint_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/api/v1/audit")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
