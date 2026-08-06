from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from demo_service.config import get_settings
from demo_service.main import create_app
from demo_service.scenarios.engine import ScenarioEngine


@pytest.fixture
def app(tmp_path, monkeypatch: pytest.MonkeyPatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    monkeypatch.setenv("INTERNAL_AUTH_TOKEN", "test-token")
    get_settings.cache_clear()
    application = create_app()
    # Reload engine against temp data dir.
    settings = get_settings()
    application.state.settings = settings
    application.state.engine = ScenarioEngine(settings)
    yield application
    get_settings.cache_clear()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
