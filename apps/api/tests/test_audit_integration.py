from __future__ import annotations

import pytest
from alembic import command
from alembic.config import Config
from app.audit.event_types import AuditEventType
from app.audit.service import record_audit_event
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest.mark.integration
@pytest.mark.asyncio
async def test_audit_events_append_only_trigger() -> None:
    pytest.importorskip("testcontainers")
    try:
        import docker

        docker.from_env().ping()
    except Exception:
        pytest.skip("Docker is not available")

    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("pgvector/pgvector:pg16") as postgres:
        raw_url = postgres.get_connection_url()
        async_url = raw_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://").replace(
            "postgresql://",
            "postgresql+asyncpg://",
            1,
        )
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")

        engine = create_async_engine(async_url)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            await record_audit_event(
                session,
                actor_type="system",
                actor_id=None,
                event_type=AuditEventType.AUTH_LOGIN_FAILED,
                entity_type="auth",
                entity_id=None,
                payload={"email": "test@example.com"},
                request_id="req-1",
            )
            await session.commit()

            from app.audit.models import AuditEvent

            count = await session.scalar(select(func.count()).select_from(AuditEvent))
            assert count == 1

            with pytest.raises(Exception, match="append-only"):
                await session.execute(
                    text("UPDATE audit_events SET event_type = 'x' WHERE event_type != 'x'")
                )
                await session.commit()

        await engine.dispose()
