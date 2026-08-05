from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from app.auth.security import (
    create_access_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.core.config import Settings


def test_hash_and_verify_password() -> None:
    hashed = hash_password("super-secret")
    assert hashed != "super-secret"
    assert verify_password(hashed, "super-secret")
    assert not verify_password(hashed, "wrong-password")


def test_access_token_expiration(test_settings: None) -> None:
    settings = Settings(
        _env_file=None,
        DATABASE_URL="postgresql://ops_pilot:ops_pilot@localhost:5432/ops_pilot",
        REDIS_URL="redis://localhost:6379/0",
        JWT_SECRET="test-secret",
        SEED_VIEWER_EMAIL="viewer@ops-pilot.local",
        SEED_VIEWER_PASSWORD="pass",
        SEED_OPERATOR_EMAIL="operator@ops-pilot.local",
        SEED_OPERATOR_PASSWORD="pass",
        SEED_APPROVER_EMAIL="approver@ops-pilot.local",
        SEED_APPROVER_PASSWORD="pass",
        SEED_ADMIN_EMAIL="admin@ops-pilot.local",
        SEED_ADMIN_PASSWORD="pass",
        JWT_ACCESS_TTL_SECONDS=1,
    )
    import uuid

    user_id = uuid.uuid4()
    token = create_access_token(user_id=user_id, role="viewer", settings=settings)
    payload = jwt.decode(token, "test-secret", algorithms=["HS256"])
    assert payload["sub"] == str(user_id)
    exp = datetime.fromtimestamp(payload["exp"], tz=UTC)
    assert exp <= datetime.now(UTC) + timedelta(seconds=2)


def test_refresh_token_hash_is_deterministic() -> None:
    assert hash_refresh_token("abc") == hash_refresh_token("abc")
    assert hash_refresh_token("abc") != hash_refresh_token("def")
