from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.auth.dependencies import get_current_user
from app.auth.models import User, UserRole
from app.auth.security import hash_password
from app.auth.service import TokenPair
from app.db.session import get_session, init_db
from httpx import ASGITransport, AsyncClient


def _user(role: UserRole = UserRole.APPROVER) -> User:
    return User(
        id=uuid.uuid4(),
        email="approver@example.com",
        display_name="Approver",
        role=role,
        password_hash=hash_password("password"),
        is_active=True,
    )


@pytest.fixture
def approver_client(test_settings: None, monkeypatch: pytest.MonkeyPatch):
    from app.core.config import get_settings
    from app.core.redis import init_redis
    from app.main import create_app
    from fakeredis import FakeAsyncRedis

    settings = get_settings()
    init_db(settings)
    init_redis(settings)
    monkeypatch.setattr("app.core.redis._redis_client", FakeAsyncRedis(decode_responses=True))

    app = create_app()
    user = _user(UserRole.APPROVER)

    async def override_user() -> User:
        return user

    async def override_session():
        session = AsyncMock()
        count_result = MagicMock()
        count_result.scalar_one = MagicMock(return_value=0)
        list_result = MagicMock()
        list_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        session.execute = AsyncMock(side_effect=[count_result, list_result])
        yield session

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_session] = override_session
    return app, user


@pytest.mark.asyncio
async def test_login_success_sets_cookies(client: AsyncClient) -> None:
    user = _user(UserRole.OPERATOR)
    token_pair = TokenPair(access_token="access", refresh_token="refresh", user=user)
    with (
        patch("app.auth.router.check_auth_rate_limit", new=AsyncMock()),
        patch("app.auth.router.authenticate", new=AsyncMock(return_value=user)),
        patch("app.auth.router.issue_tokens", new=AsyncMock(return_value=token_pair)),
        patch("app.auth.router.record_audit_event", new=AsyncMock()),
    ):
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "operator@example.com", "password": "password"},
        )
    assert response.status_code == 200
    assert response.json()["user"]["role"] == "operator"
    assert "access_token" in response.cookies


@pytest.mark.asyncio
async def test_login_invalid_credentials(client: AsyncClient) -> None:
    with (
        patch("app.auth.router.check_auth_rate_limit", new=AsyncMock()),
        patch("app.auth.router.authenticate", new=AsyncMock(return_value=None)),
        patch("app.auth.router.record_audit_event", new=AsyncMock()),
    ):
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "operator@example.com", "password": "wrong"},
        )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


@pytest.mark.asyncio
async def test_me_returns_current_user(client: AsyncClient) -> None:
    from app.main import create_app

    app = create_app()
    user = _user(UserRole.VIEWER)
    app.dependency_overrides[get_current_user] = lambda: user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        response = await http_client.get("/api/v1/auth/me")
    assert response.status_code == 200
    assert response.json()["email"] == user.email


@pytest.mark.asyncio
async def test_audit_list_forbidden_for_operator_role(client: AsyncClient) -> None:
    from app.main import create_app

    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: _user(UserRole.OPERATOR)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        response = await http_client.get("/api/v1/audit")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_audit_list_allowed_for_approver(approver_client) -> None:
    app, _ = approver_client
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        response = await http_client.get("/api/v1/audit")
    assert response.status_code == 200
    payload = response.json()
    assert payload["items"] == []
    assert payload["total"] == 0


@pytest.mark.asyncio
async def test_refresh_requires_cookie(client: AsyncClient) -> None:
    response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 401
