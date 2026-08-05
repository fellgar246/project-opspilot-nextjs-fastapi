from __future__ import annotations

import pytest
from alembic import command
from alembic.config import Config
from app.audit.event_types import AuditEventType
from app.audit.service import record_audit_event
from app.auth.models import User, UserRole
from app.auth.security import hash_password
from app.core.config import get_settings
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


def _set_integration_env(monkeypatch: pytest.MonkeyPatch, database_url: str) -> None:
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("JWT_SECRET", "integration-test-secret")
    monkeypatch.setenv("SEED_VIEWER_EMAIL", "viewer@ops-pilot.local")
    monkeypatch.setenv("SEED_VIEWER_PASSWORD", "viewer-dev-password")
    monkeypatch.setenv("SEED_OPERATOR_EMAIL", "operator@ops-pilot.local")
    monkeypatch.setenv("SEED_OPERATOR_PASSWORD", "operator-dev-password")
    monkeypatch.setenv("SEED_APPROVER_EMAIL", "approver@ops-pilot.local")
    monkeypatch.setenv("SEED_APPROVER_PASSWORD", "approver-dev-password")
    monkeypatch.setenv("SEED_ADMIN_EMAIL", "admin@ops-pilot.local")
    monkeypatch.setenv("SEED_ADMIN_PASSWORD", "admin-dev-password")
    get_settings.cache_clear()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_audit_write_failure_rolls_back_domain_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

        async_url = database_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://").replace(
            "postgresql://",
            "postgresql+asyncpg://",
            1,
        )
        engine = create_async_engine(async_url)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        async def failing_record(*args, **kwargs):
            raise RuntimeError("audit failed")

        monkeypatch.setattr("app.audit.service.record_audit_event", failing_record)

        async with session_factory() as session:
            session.add(
                User(
                    email="rollback@ops-pilot.local",
                    display_name="Rollback Test",
                    role=UserRole.VIEWER,
                    password_hash=hash_password("password"),
                    is_active=True,
                )
            )
            with pytest.raises(RuntimeError, match="audit failed"):
                await record_audit_event(
                    session,
                    actor_type="system",
                    actor_id=None,
                    event_type=AuditEventType.INCIDENT_CREATED,
                    entity_type="incident",
                    entity_id=None,
                    payload={},
                )
                await session.commit()

            count = await session.scalar(select(func.count()).select_from(User))
            assert count == 0

        await engine.dispose()
