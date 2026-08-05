from __future__ import annotations

import pytest
from app.core.config import get_settings
from app.core.redis import init_redis
from app.db.session import init_db
from app.main import create_app
from fakeredis import FakeAsyncRedis
from httpx import ASGITransport, AsyncClient


def _set_auth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-key-for-unit-tests")
    monkeypatch.setenv("SEED_VIEWER_EMAIL", "viewer@ops-pilot.local")
    monkeypatch.setenv("SEED_VIEWER_PASSWORD", "viewer-dev-password")
    monkeypatch.setenv("SEED_OPERATOR_EMAIL", "operator@ops-pilot.local")
    monkeypatch.setenv("SEED_OPERATOR_PASSWORD", "operator-dev-password")
    monkeypatch.setenv("SEED_APPROVER_EMAIL", "approver@ops-pilot.local")
    monkeypatch.setenv("SEED_APPROVER_PASSWORD", "approver-dev-password")
    monkeypatch.setenv("SEED_ADMIN_EMAIL", "admin@ops-pilot.local")
    monkeypatch.setenv("SEED_ADMIN_PASSWORD", "admin-dev-password")


@pytest.fixture
def test_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://ops_pilot:ops_pilot@localhost:5432/ops_pilot",
    )
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("APP_ENV", "test")
    _set_auth_env(monkeypatch)
    get_settings.cache_clear()


@pytest.fixture
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> FakeAsyncRedis:
    client = FakeAsyncRedis(decode_responses=True)
    monkeypatch.setattr("app.core.redis._redis_client", client)
    return client


@pytest.fixture
async def client(test_settings: None, monkeypatch: pytest.MonkeyPatch) -> AsyncClient:
    settings = get_settings()
    init_db(settings)
    init_redis(settings)
    fake = FakeAsyncRedis(decode_responses=True)
    monkeypatch.setattr("app.core.redis._redis_client", fake)
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client
