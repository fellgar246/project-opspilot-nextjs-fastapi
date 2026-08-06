from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.auth.dependencies import get_current_user
from app.auth.models import User, UserRole
from app.auth.security import hash_password
from app.db.session import get_session
from app.incidents.models import Incident, IncidentSeverity, IncidentSource, IncidentStatus
from app.investigation.models import AgentRun, AgentRunStatus
from httpx import ASGITransport, AsyncClient


def _operator() -> User:
    return User(
        id=uuid.uuid4(),
        email="operator@example.com",
        display_name="Operator",
        role=UserRole.OPERATOR,
        password_hash=hash_password("password"),
        is_active=True,
    )


@pytest.fixture
def investigation_client(test_settings: None, monkeypatch: pytest.MonkeyPatch):
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
    user = _operator()

    async def override_user() -> User:
        return user

    async def override_session():
        session = AsyncMock()
        yield session

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_session] = override_session
    return app, user


@pytest.mark.asyncio
async def test_start_investigation_returns_202(investigation_client) -> None:
    app, _ = investigation_client
    incident = Incident(
        id=uuid.uuid4(),
        title="Test incident",
        description="Service degraded",
        severity=IncidentSeverity.SEV2,
        status=IncidentStatus.OPEN,
        source=IncidentSource.MANUAL,
        started_at=datetime.now(UTC),
    )
    agent_run = AgentRun(
        id=uuid.uuid4(),
        incident_id=incident.id,
        graph_thread_id="inv-thread",
        status=AgentRunStatus.PENDING,
        model="mock-v1",
        prompt_version="v1",
    )

    with (
        pytest.MonkeyPatch.context() as mp,
    ):
        mp.setattr(
            "app.investigation.router.require_incident",
            AsyncMock(return_value=incident),
        )
        mp.setattr(
            "app.investigation.router.investigation_service.start_investigation",
            AsyncMock(return_value=agent_run),
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(f"/api/v1/incidents/{incident.id}/start-investigation")

    assert response.status_code == 202
    body = response.json()
    assert body["agent_run_id"] == str(agent_run.id)
    assert body["status"] == AgentRunStatus.PENDING


@pytest.mark.asyncio
async def test_list_agent_runs(investigation_client) -> None:
    app, _ = investigation_client
    incident_id = uuid.uuid4()
    run = AgentRun(
        id=uuid.uuid4(),
        incident_id=incident_id,
        graph_thread_id="inv-thread",
        status=AgentRunStatus.COMPLETED,
        model="mock-v1",
        prompt_version="v1",
        token_usage={"prompt_tokens": 10, "completion_tokens": 5},
        node_progress={"completed_nodes": ["triage_incident"]},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "app.investigation.router.require_incident",
            AsyncMock(return_value=MagicMock(id=incident_id)),
        )
        mp.setattr(
            "app.investigation.router.investigation_service.list_agent_runs",
            AsyncMock(return_value=[run]),
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/v1/incidents/{incident_id}/agent-runs")

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["prompt_version"] == "v1"


@pytest.mark.asyncio
async def test_pause_and_resume_endpoints(investigation_client) -> None:
    app, _ = investigation_client
    incident_id = uuid.uuid4()
    run = AgentRun(
        id=uuid.uuid4(),
        incident_id=incident_id,
        graph_thread_id="inv-thread",
        status=AgentRunStatus.PAUSED,
        model="mock-v1",
        prompt_version="v1",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "app.investigation.router.require_incident",
            AsyncMock(return_value=MagicMock(id=incident_id)),
        )
        mp.setattr(
            "app.investigation.router.investigation_service.pause_investigation",
            AsyncMock(return_value=run),
        )
        mp.setattr(
            "app.investigation.router.investigation_service.resume_investigation",
            AsyncMock(return_value=run),
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            pause = await client.post(f"/api/v1/incidents/{incident_id}/pause")
            resume = await client.post(f"/api/v1/incidents/{incident_id}/resume")

    assert pause.status_code == 200
    assert resume.status_code == 200
