from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.auth.dependencies import get_current_user
from app.auth.models import User, UserRole
from app.auth.security import hash_password
from app.core.config import get_settings
from app.core.redis import init_redis
from app.db.session import get_session
from app.incidents.models import (
    Incident,
    IncidentService,
    IncidentSeverity,
    IncidentSource,
    IncidentStatus,
    Service,
    ServiceEnvironment,
)
from app.incidents.repository import CursorPage
from app.incidents.timeline import TimelineEntry
from app.main import create_app
from fakeredis import FakeAsyncRedis
from httpx import ASGITransport, AsyncClient


def _user(role: UserRole = UserRole.OPERATOR) -> User:
    return User(
        id=uuid.uuid4(),
        email="operator@example.com",
        display_name="Operator",
        role=role,
        password_hash=hash_password("password"),
        is_active=True,
    )


def _incident(user: User) -> Incident:
    service_id = uuid.uuid4()
    now = datetime.now(UTC)
    incident = Incident(
        id=uuid.uuid4(),
        title="Checkout errors",
        description="5xx errors",
        severity=IncidentSeverity.SEV2,
        status=IncidentStatus.OPEN,
        source=IncidentSource.MANUAL,
        started_at=now,
        created_by=user.id,
        created_at=now,
        updated_at=now,
    )
    incident.service_links = [IncidentService(incident_id=incident.id, service_id=service_id)]
    return incident


@pytest.fixture
def operator_client(test_settings: None, monkeypatch: pytest.MonkeyPatch):
    settings = get_settings()
    init_db(settings)
    init_redis(settings)
    monkeypatch.setattr("app.core.redis._redis_client", FakeAsyncRedis(decode_responses=True))

    app = create_app()
    user = _user(UserRole.OPERATOR)

    async def override_user() -> User:
        return user

    async def override_session():
        session = AsyncMock()
        yield session

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_session] = override_session
    return app, user


@pytest.fixture
def admin_client(test_settings: None, monkeypatch: pytest.MonkeyPatch):
    settings = get_settings()
    init_db(settings)
    init_redis(settings)
    monkeypatch.setattr("app.core.redis._redis_client", FakeAsyncRedis(decode_responses=True))

    app = create_app()
    user = _user(UserRole.ADMIN)

    async def override_user() -> User:
        return user

    async def override_session():
        session = AsyncMock()
        yield session

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_session] = override_session
    return app, user


def init_db(settings):
    from app.db.session import init_db as _init_db

    _init_db(settings)


@pytest.mark.asyncio
async def test_list_incidents_returns_page(operator_client, monkeypatch: pytest.MonkeyPatch) -> None:
    app, _ = operator_client
    incident = _incident(_user())

    async def fake_list(*args, **kwargs):
        return CursorPage(items=[incident], next_cursor=None, total_estimate=1)

    monkeypatch.setattr("app.incidents.router.repository.list_incidents", fake_list)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/incidents")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_estimate"] == 1
    assert payload["items"][0]["title"] == "Checkout errors"


@pytest.mark.asyncio
async def test_create_incident_returns_201(operator_client, monkeypatch: pytest.MonkeyPatch) -> None:
    app, user = operator_client
    incident = _incident(user)

    monkeypatch.setattr("app.incidents.router.service.create_incident", AsyncMock(return_value=incident))
    monkeypatch.setattr("app.incidents.router.service.require_incident", AsyncMock(return_value=incident))

    session = AsyncMock()
    session.commit = AsyncMock()

    async def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/incidents",
            json={
                "title": "Checkout errors",
                "description": "5xx errors",
                "severity": "sev2",
                "service_ids": [str(uuid.uuid4())],
                "started_at": datetime.now(UTC).isoformat(),
            },
        )
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_admin_can_create_service(admin_client, monkeypatch: pytest.MonkeyPatch) -> None:
    app, _ = admin_client
    service = Service(
        id=uuid.uuid4(),
        name="demo-service",
        environment=ServiceEnvironment.DEMO,
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    monkeypatch.setattr("app.incidents.router.service.create_service", AsyncMock(return_value=service))

    session = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    async def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/services",
            json={"name": "demo-service", "environment": "demo"},
        )
    assert response.status_code == 201
    assert response.json()["name"] == "demo-service"


@pytest.mark.asyncio
async def test_operator_cannot_create_service(operator_client) -> None:
    app, _ = operator_client
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/services",
            json={"name": "blocked", "environment": "demo"},
        )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_incident_endpoint(operator_client, monkeypatch: pytest.MonkeyPatch) -> None:
    app, user = operator_client
    incident = _incident(user)
    monkeypatch.setattr("app.incidents.router.service.require_incident", AsyncMock(return_value=incident))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/api/v1/incidents/{incident.id}")
    assert response.status_code == 200
    assert response.json()["id"] == str(incident.id)


@pytest.mark.asyncio
async def test_get_timeline(operator_client, monkeypatch: pytest.MonkeyPatch) -> None:
    app, _ = operator_client
    incident_id = uuid.uuid4()
    monkeypatch.setattr("app.incidents.router.service.require_incident", AsyncMock(return_value=MagicMock()))
    monkeypatch.setattr(
        "app.incidents.router.assemble_timeline",
        AsyncMock(
            return_value=[
                TimelineEntry(
                    id=uuid.uuid4(),
                    occurred_at=datetime.now(UTC),
                    kind="note",
                    actor_type="user",
                    actor_id=uuid.uuid4(),
                    title="Manual note",
                    description="hello",
                    reference={"note_id": "n-1"},
                )
            ]
        ),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/api/v1/incidents/{incident_id}/timeline")
    assert response.status_code == 200
    assert response.json()["items"][0]["kind"] == "note"
