from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.auth.dependencies import require_capability, require_not_proposer
from app.auth.models import User, UserRole
from app.auth.rate_limit import check_auth_rate_limit
from app.auth.security import decode_access_token, hash_password
from app.auth.service import TokenPair, authenticate, user_to_me
from app.audit.service import record_audit_event
from app.core.config import Settings
from app.core.context import request_id_var
from app.core.errors import AppError
from app.worker.enqueue import enqueue_kwargs
from fakeredis import FakeAsyncRedis


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        DATABASE_URL="postgresql://ops_pilot:ops_pilot@localhost:5432/ops_pilot",
        REDIS_URL="redis://localhost:6379/0",
        JWT_SECRET="test-jwt-secret-key-for-unit-tests-only",
        SEED_VIEWER_EMAIL="viewer@ops-pilot.local",
        SEED_VIEWER_PASSWORD="pass",
        SEED_OPERATOR_EMAIL="operator@ops-pilot.local",
        SEED_OPERATOR_PASSWORD="pass",
        SEED_APPROVER_EMAIL="approver@ops-pilot.local",
        SEED_APPROVER_PASSWORD="pass",
        SEED_ADMIN_EMAIL="admin@ops-pilot.local",
        SEED_ADMIN_PASSWORD="pass",
    )


@pytest.mark.asyncio
async def test_authenticate_rejects_invalid_password() -> None:
    user = User(
        id=uuid.uuid4(),
        email="viewer@example.com",
        display_name="Viewer",
        role=UserRole.VIEWER,
        password_hash=hash_password("correct"),
        is_active=True,
    )
    session = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=user)))
    result = await authenticate(session, email="viewer@ops-pilot.local", password="wrong")
    assert result is None


def test_user_to_me_shape() -> None:
    user = User(
        id=uuid.uuid4(),
        email="viewer@example.com",
        display_name="Viewer",
        role=UserRole.VIEWER,
        password_hash="hash",
        is_active=True,
    )
    me = user_to_me(user)
    assert me.email == user.email
    assert me.role == "viewer"
    assert "password" not in me.model_dump()


def test_decode_access_token() -> None:
    settings = _settings()
    from app.auth.security import create_access_token

    user_id = uuid.uuid4()
    token = create_access_token(user_id=user_id, role="admin", settings=settings)
    payload = decode_access_token(token, settings)
    assert payload["sub"] == str(user_id)
    assert payload["role"] == "admin"


@pytest.mark.asyncio
async def test_rate_limit_blocks_after_threshold() -> None:
    settings = _settings()
    settings = settings.model_copy(update={"auth_rate_limit_attempts": 2})
    redis = FakeAsyncRedis(decode_responses=True)
    await check_auth_rate_limit(redis=redis, settings=settings, ip_address="127.0.0.1", email="a@b.com")
    await check_auth_rate_limit(redis=redis, settings=settings, ip_address="127.0.0.1", email="a@b.com")
    with pytest.raises(AppError) as exc_info:
        await check_auth_rate_limit(
            redis=redis,
            settings=settings,
            ip_address="127.0.0.1",
            email="a@b.com",
        )
    assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_record_audit_event_redacts_payload() -> None:
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    await record_audit_event(
        session,
        actor_type="system",
        actor_id=None,
        event_type="auth.login_failed",
        entity_type="auth",
        entity_id=None,
        payload={"password": "secret"},
    )
    event = session.add.call_args.args[0]
    assert event.payload["password"] == "[REDACTED]"


def test_enqueue_kwargs_includes_request_id() -> None:
    token = request_id_var.set("req-abc")
    try:
        assert enqueue_kwargs() == {"request_id": "req-abc"}
    finally:
        request_id_var.reset(token)


def test_require_not_proposer_dependency_metadata() -> None:
    proposer_id = uuid.uuid4()
    dependency = require_not_proposer(proposer_id)
    assert hasattr(dependency, "__route_policy__")


def test_require_capability_dependency_metadata() -> None:
    from app.auth.policy import Capability

    dependency = require_capability(Capability.READ_AUDIT)
    assert hasattr(dependency, "__route_policy__")
