from __future__ import annotations

import pytest
from alembic import command
from alembic.config import Config
from app.auth.models import User, UserRole
from app.auth.security import hash_password
from app.core.config import get_settings
from app.core.redis import init_redis
from app.db.session import init_db
from app.main import create_app
from fakeredis import FakeAsyncRedis
from httpx import ASGITransport, AsyncClient
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


async def _create_test_user(database_url: str) -> tuple[str, str]:
    async_url = database_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://").replace(
        "postgresql://",
        "postgresql+asyncpg://",
        1,
    )
    engine = create_async_engine(async_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    email = "operator@ops-pilot.local"
    password = "operator-dev-password"
    async with session_factory() as session:
        session.add(
            User(
                email=email,
                display_name="Operator Dev",
                role=UserRole.OPERATOR,
                password_hash=hash_password(password),
                is_active=True,
            )
        )
        await session.commit()
    await engine.dispose()
    return email, password


@pytest.mark.integration
@pytest.mark.asyncio
async def test_login_refresh_and_me_flow(monkeypatch: pytest.MonkeyPatch) -> None:
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
        email, password = await _create_test_user(database_url)

        settings = get_settings()
        init_db(settings)
        init_redis(settings)
        fake = FakeAsyncRedis(decode_responses=True)
        monkeypatch.setattr("app.core.redis._redis_client", fake)

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            bad = await client.post("/api/v1/auth/login", json={"email": email, "password": "wrong"})
            assert bad.status_code == 401
            assert bad.json()["detail"] == "Invalid credentials"

            login = await client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": password},
            )
            assert login.status_code == 200
            assert login.json()["user"]["role"] == "operator"
            assert "access_token" in login.cookies
            assert "refresh_token" in login.cookies

            me = await client.get("/api/v1/auth/me")
            assert me.status_code == 200
            assert me.json()["email"] == email

            audit = await client.get("/api/v1/audit")
            assert audit.status_code == 403

            refresh = await client.post("/api/v1/auth/refresh")
            assert refresh.status_code == 200
            old_refresh = login.cookies.get("refresh_token")
            assert refresh.cookies.get("refresh_token") != old_refresh

            reuse = await client.post(
                "/api/v1/auth/refresh",
                cookies={"refresh_token": old_refresh},
            )
            assert reuse.status_code == 401

            me_after_reuse = await client.get("/api/v1/auth/me")
            assert me_after_reuse.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
async def test_login_rate_limit_returns_429(monkeypatch: pytest.MonkeyPatch) -> None:
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
        monkeypatch.setenv("AUTH_RATE_LIMIT_ATTEMPTS", "2")
        get_settings.cache_clear()

        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        email, _ = await _create_test_user(database_url)

        settings = get_settings()
        init_db(settings)
        init_redis(settings)
        fake = FakeAsyncRedis(decode_responses=True)
        monkeypatch.setattr("app.core.redis._redis_client", fake)

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            for _ in range(2):
                response = await client.post(
                    "/api/v1/auth/login",
                    json={"email": email, "password": "wrong"},
                )
                assert response.status_code == 401

            limited = await client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": "wrong"},
            )
            assert limited.status_code == 429
