from __future__ import annotations

import pytest
from app.core.config import get_settings
from app.db.session import init_db
from app.main import create_app
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def test_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://ops_pilot:ops_pilot@localhost:5432/ops_pilot",
    )
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("APP_ENV", "test")
    get_settings.cache_clear()


@pytest.fixture
async def client(test_settings: None) -> AsyncClient:
    settings = get_settings()
    init_db(settings)
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client
