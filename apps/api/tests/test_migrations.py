from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config


def test_initial_migration_declares_extensions() -> None:
    migration_path = Path("alembic/versions/001_initial_extensions.py")
    source = migration_path.read_text(encoding="utf-8")
    assert "CREATE EXTENSION IF NOT EXISTS vector" in source
    assert 'CREATE EXTENSION IF NOT EXISTS "uuid-ossp"' in source


@pytest.mark.integration
def test_initial_migration_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("testcontainers")
    try:
        from testcontainers.postgres import PostgresContainer
    except ImportError:
        pytest.skip("testcontainers not installed")

    try:
        import docker

        docker.from_env().ping()
    except Exception:
        pytest.skip("Docker is not available")

    with PostgresContainer("pgvector/pgvector:pg16") as postgres:
        database_url = postgres.get_connection_url()
        monkeypatch.setenv("DATABASE_URL", database_url)
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("JWT_SECRET", "migration-test-secret")
        monkeypatch.setenv("SEED_VIEWER_EMAIL", "viewer@ops-pilot.local")
        monkeypatch.setenv("SEED_VIEWER_PASSWORD", "pass")
        monkeypatch.setenv("SEED_OPERATOR_EMAIL", "operator@ops-pilot.local")
        monkeypatch.setenv("SEED_OPERATOR_PASSWORD", "pass")
        monkeypatch.setenv("SEED_APPROVER_EMAIL", "approver@ops-pilot.local")
        monkeypatch.setenv("SEED_APPROVER_PASSWORD", "pass")
        monkeypatch.setenv("SEED_ADMIN_EMAIL", "admin@ops-pilot.local")
        monkeypatch.setenv("SEED_ADMIN_PASSWORD", "pass")

        from app.core.config import get_settings

        get_settings.cache_clear()
        alembic_cfg = Config("alembic.ini")

        command.upgrade(alembic_cfg, "head")
        command.upgrade(alembic_cfg, "head")

        async def verify_extensions() -> None:
            from sqlalchemy import text
            from sqlalchemy.ext.asyncio import create_async_engine

            settings = get_settings()
            url = str(settings.database_url).replace("postgresql://", "postgresql+asyncpg://", 1)
            engine = create_async_engine(url)
            async with engine.connect() as connection:
                vector = await connection.scalar(
                    text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
                )
                uuid = await connection.scalar(
                    text("SELECT 1 FROM pg_extension WHERE extname = 'uuid-ossp'")
                )
                assert vector == 1
                assert uuid == 1
            await engine.dispose()

        import asyncio

        asyncio.run(verify_extensions())
