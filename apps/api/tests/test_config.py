from __future__ import annotations

import pytest
from app.core.config import Settings, get_settings
from pydantic import ValidationError


def test_settings_requires_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    get_settings.cache_clear()

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)

    assert "DATABASE_URL" in str(exc_info.value)


def test_settings_requires_redis_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")
    monkeypatch.delenv("REDIS_URL", raising=False)
    get_settings.cache_clear()

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)

    assert "REDIS_URL" in str(exc_info.value)
