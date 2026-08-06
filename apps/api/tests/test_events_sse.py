from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.auth.dependencies import get_current_user
from app.auth.models import User, UserRole
from app.auth.security import hash_password
from app.db.session import get_session
from app.events.models import InvestigationEvent
from httpx import ASGITransport, AsyncClient


def _viewer() -> User:
    return User(
        id=uuid.uuid4(),
        email="viewer@example.com",
        display_name="Viewer",
        role=UserRole.VIEWER,
        password_hash=hash_password("password"),
        is_active=True,
    )


@pytest.fixture
def sse_client(test_settings: None, monkeypatch: pytest.MonkeyPatch):
    from app.core.config import get_settings
    from app.core.redis import init_redis
    from app.db.session import init_db
    from app.main import create_app
    from fakeredis import FakeAsyncRedis

    settings = get_settings()
    init_db(settings)
    init_redis(settings)
    monkeypatch.setattr("app.core.redis._redis_client", FakeAsyncRedis(decode_responses=True))

    app = create_app()
    user = _viewer()

    async def override_user() -> User:
        return user

    async def override_session():
        session = AsyncMock()
        yield session

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_session] = override_session
    return app


@pytest.mark.asyncio
async def test_sse_requires_incident_access(sse_client) -> None:
    app = sse_client
    incident_id = uuid.uuid4()

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "app.events.router.require_incident",
            AsyncMock(side_effect=__import__("app.core.errors", fromlist=["AppError"]).AppError("Forbidden", status_code=403)),
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/v1/incidents/{incident_id}/events")

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_event_to_sse_format() -> None:
    from app.events.bus import event_to_sse

    event = InvestigationEvent(
        id=uuid.uuid4(),
        incident_id=uuid.uuid4(),
        agent_run_id=uuid.uuid4(),
        seq=42,
        type="node_started",
        occurred_at=datetime.now(UTC),
        payload={"node": "collect_metrics"},
    )
    event_type, event_id, data = event_to_sse(event)
    assert event_type == "node_started"
    assert event_id == "42"
    parsed = json.loads(data)
    assert parsed["seq"] == 42
