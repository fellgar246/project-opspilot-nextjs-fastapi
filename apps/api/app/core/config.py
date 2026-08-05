from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(ROOT_DIR / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["local", "test", "ci"] = "local"
    app_version: str = "0.1.0"
    git_sha: str = "dev"

    database_url: PostgresDsn = Field(validation_alias="DATABASE_URL")
    redis_url: RedisDsn = Field(validation_alias="REDIS_URL")

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    model_provider: Literal["mock", "openai"] = "mock"
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-4o-mini"

    max_agent_iterations: int = 12
    max_tokens_per_incident: int = 120_000

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])


@lru_cache
def get_settings() -> Settings:
    try:
        return Settings()  # type: ignore[call-arg]
    except ValidationError as exc:
        missing = [str(error["loc"][0]) for error in exc.errors() if error["type"] == "missing"]
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}") from exc
