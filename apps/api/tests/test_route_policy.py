from __future__ import annotations

from app.auth.route_policy import collect_unprotected_routes
from app.core.config import get_settings
from app.core.redis import init_redis
from app.main import create_app
from fakeredis import FakeAsyncRedis


def test_all_routes_declare_policy(test_settings: None, monkeypatch: pytest.MonkeyPatch) -> None:
    init_redis(get_settings())
    fake = FakeAsyncRedis(decode_responses=True)
    monkeypatch.setattr("app.core.redis._redis_client", fake)
    app = create_app()
    missing = collect_unprotected_routes(app)
    assert missing == [], f"Routes without policy: {missing}"
