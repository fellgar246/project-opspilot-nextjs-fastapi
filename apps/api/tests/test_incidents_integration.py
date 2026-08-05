from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from alembic import command
from alembic.config import Config
from app.auth.models import User, UserRole
from app.auth.security import hash_password
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.redis import init_redis
from app.db.session import init_db
from app.incidents.models import (
    EvidenceSourceType,
    IncidentSeverity,
    IncidentSource,
    Service,
    ServiceEnvironment,
)
from app.incidents.service import create_hypothesis, create_incident, upsert_evidence
from app.incidents.timeline import assemble_timeline
from app.main import create_app
from fakeredis import FakeAsyncRedis
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


def _set_integration_env(monkeypatch: pytest.MonkeyPatch, database_url: str) -> None:
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("JWT_SECRET", "integration-test-secret")
    monkeypatch.setenv("SEED_VIEWER_EMAIL", "viewer@ops-pilot.local")
    monkeypatch.setenv("SEED_VIEWER_PASSWORD", "pass")
    monkeypatch.setenv("SEED_OPERATOR_EMAIL", "operator@ops-pilot.local")
    monkeypatch.setenv("SEED_OPERATOR_PASSWORD", "pass")
    monkeypatch.setenv("SEED_APPROVER_EMAIL", "approver@ops-pilot.local")
    monkeypatch.setenv("SEED_APPROVER_PASSWORD", "pass")
    monkeypatch.setenv("SEED_ADMIN_EMAIL", "admin@ops-pilot.local")
    monkeypatch.setenv("SEED_ADMIN_PASSWORD", "pass")
    get_settings.cache_clear()


@pytest.fixture
async def integration_client(monkeypatch: pytest.MonkeyPatch):
    pytest.importorskip("testcontainers")
    try:
        import docker

        docker.from_env().ping()
    except Exception:
        pytest.skip("Docker is not available")

    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("pgvector/pgvector:pg16") as postgres:
        database_url = postgres.get_connection_url()
        _set_integration_env(monkeypatch, database_url)
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")

        init_db(get_settings())
        init_redis(get_settings())
        fake = FakeAsyncRedis(decode_responses=True)
        monkeypatch.setattr("app.core.redis._redis_client", fake)
        monkeypatch.setattr("app.auth.router.check_auth_rate_limit", AsyncMock())

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            async_url = database_url.replace(
                "postgresql+psycopg2://", "postgresql+asyncpg://"
            ).replace(
                "postgresql://",
                "postgresql+asyncpg://",
                1,
            )
            engine = create_async_engine(async_url)
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            yield client, session_factory
            await engine.dispose()


async def _seed_operator(session_factory) -> User:
    async with session_factory() as session:
        user = User(
            email="operator@ops-pilot.local",
            display_name="Operator",
            role=UserRole.OPERATOR,
            password_hash=hash_password("pass"),
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def _seed_admin(session_factory) -> User:
    async with session_factory() as session:
        user = User(
            email="admin@ops-pilot.local",
            display_name="Admin",
            role=UserRole.ADMIN,
            password_hash=hash_password("pass"),
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def _login(client: AsyncClient, email: str, password: str) -> None:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200


@pytest.mark.integration
@pytest.mark.asyncio
async def test_incident_lifecycle_and_timeline(integration_client) -> None:
    client, session_factory = integration_client
    await _seed_operator(session_factory)
    await _login(client, "operator@ops-pilot.local", "pass")

    async with session_factory() as session:
        service = Service(
            name="demo-service",
            environment=ServiceEnvironment.DEMO,
            is_active=True,
        )
        session.add(service)
        await session.commit()
        service_id = service.id

    started_at = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    create_resp = await client.post(
        "/api/v1/incidents",
        json={
            "title": "Checkout errors",
            "description": "5xx on checkout endpoint",
            "severity": "sev2",
            "service_ids": [str(service_id)],
            "started_at": started_at,
            "source": "manual",
        },
    )
    assert create_resp.status_code == 201
    incident = create_resp.json()
    incident_id = incident["id"]
    assert incident["status"] == "open"

    note_resp = await client.post(
        f"/api/v1/incidents/{incident_id}/notes",
        json={"content": "PagerDuty alert received"},
    )
    assert note_resp.status_code == 201

    for status in ["investigating", "mitigating", "monitoring", "resolved", "closed"]:
        patch_resp = await client.patch(
            f"/api/v1/incidents/{incident_id}",
            json={"status": status, "reason": f"Moving to {status}"},
        )
        assert patch_resp.status_code == 200

    timeline_resp = await client.get(f"/api/v1/incidents/{incident_id}/timeline")
    assert timeline_resp.status_code == 200
    kinds = [entry["kind"] for entry in timeline_resp.json()["items"]]
    assert "note" in kinds
    assert kinds.count("status_change") >= 6

    async with session_factory() as session:
        from app.audit.models import AuditEvent

        count = await session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.entity_id == uuid.UUID(incident_id))
        )
        assert count is not None and count >= 2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_service_delete_with_incidents_returns_409(integration_client) -> None:
    client, session_factory = integration_client
    await _seed_admin(session_factory)
    await _seed_operator(session_factory)
    await _login(client, "admin@ops-pilot.local", "pass")

    create_service = await client.post(
        "/api/v1/services",
        json={
            "name": "temp-service",
            "environment": "demo",
            "description": "Temporary",
        },
    )
    assert create_service.status_code == 201
    service_id = create_service.json()["id"]

    await _login(client, "operator@ops-pilot.local", "pass")
    incident = await client.post(
        "/api/v1/incidents",
        json={
            "title": "Linked incident",
            "description": "Test",
            "severity": "sev3",
            "service_ids": [service_id],
            "started_at": datetime.now(UTC).isoformat(),
        },
    )
    assert incident.status_code == 201

    await _login(client, "admin@ops-pilot.local", "pass")
    delete_resp = await client.delete(f"/api/v1/services/{service_id}")
    assert delete_resp.status_code == 409
    assert "Deactivate" in delete_resp.json()["detail"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_operator_cannot_create_service(integration_client) -> None:
    client, session_factory = integration_client
    await _seed_operator(session_factory)
    await _login(client, "operator@ops-pilot.local", "pass")

    response = await client.post(
        "/api/v1/services",
        json={"name": "blocked", "environment": "demo"},
    )
    assert response.status_code == 403


@pytest.mark.integration
@pytest.mark.asyncio
async def test_evidence_dedup_and_hypothesis_requires_support(integration_client) -> None:
    client, session_factory = integration_client
    operator = await _seed_operator(session_factory)

    async with session_factory() as session:
        incident = await create_incident(
            session,
            title="Test",
            description="Test",
            severity=IncidentSeverity.SEV3,
            service_ids=[],
            started_at=datetime.now(UTC) - timedelta(hours=1),
            source=IncidentSource.MANUAL,
            actor=operator,
            request_id=None,
        )
        await session.commit()
        incident_id = incident.id

        evidence_a = await upsert_evidence(
            session,
            incident_id=incident_id,
            source_type=EvidenceSourceType.METRIC,
            source_reference="prometheus/http_errors",
            title="Error rate",
            content="42 errors/min",
            structured_data={"metric_name": "http_errors", "value": 42.0},
            observed_at=datetime.now(UTC),
        )
        evidence_b = await upsert_evidence(
            session,
            incident_id=incident_id,
            source_type=EvidenceSourceType.METRIC,
            source_reference="prometheus/http_errors",
            title="Error rate duplicate",
            content="42 errors/min",
            structured_data={"metric_name": "http_errors", "value": 42.0},
            observed_at=datetime.now(UTC),
        )
        await session.commit()
        assert evidence_a.id == evidence_b.id

        with pytest.raises(AppError, match="supporting evidence"):
            await create_hypothesis(
                session,
                incident_id=incident_id,
                statement="Pool exhausted",
                confidence=0.7,
                supporting_evidence=[],
            )

        hypothesis = await create_hypothesis(
            session,
            incident_id=incident_id,
            statement="Pool exhausted",
            confidence=0.7,
            supporting_evidence=[evidence_a.id],
        )
        await session.commit()

        timeline = await assemble_timeline(session, incident_id)
        kinds = [entry.kind for entry in timeline]
        assert "evidence_collected" in kinds
        assert "hypothesis_created" in kinds
        assert hypothesis.id is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_timeline_stable_order_with_equal_timestamps(integration_client) -> None:
    _, session_factory = integration_client
    operator = await _seed_operator(session_factory)
    fixed_time = datetime(2026, 1, 1, tzinfo=UTC)

    async with session_factory() as session:
        incident = await create_incident(
            session,
            title="Order test",
            description="Order test",
            severity=IncidentSeverity.SEV4,
            service_ids=[],
            started_at=fixed_time,
            source=IncidentSource.MANUAL,
            actor=operator,
            request_id=None,
        )
        await session.commit()
        incident_id = incident.id

        for i in range(3):
            await upsert_evidence(
                session,
                incident_id=incident_id,
                source_type=EvidenceSourceType.LOG,
                source_reference=f"log/{i}",
                title=f"Log {i}",
                content=f"entry {i}",
                structured_data={"level": "error", "service": "demo"},
                observed_at=fixed_time,
            )
        await session.commit()

        timeline_first = await assemble_timeline(session, incident_id)
        timeline_second = await assemble_timeline(session, incident_id)
        ids_first = [entry.id for entry in timeline_first]
        ids_second = [entry.id for entry in timeline_second]
        assert ids_first == ids_second


@pytest.mark.integration
@pytest.mark.asyncio
async def test_migration_003_up_down(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("testcontainers")
    try:
        import docker

        docker.from_env().ping()
    except Exception:
        pytest.skip("Docker is not available")

    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("pgvector/pgvector:pg16") as postgres:
        database_url = postgres.get_connection_url()
        _set_integration_env(monkeypatch, database_url)
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        command.downgrade(alembic_cfg, "002")
        command.upgrade(alembic_cfg, "head")
