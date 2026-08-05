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

    jwt_secret: SecretStr = Field(validation_alias="JWT_SECRET")
    jwt_access_ttl_seconds: int = Field(default=900, validation_alias="JWT_ACCESS_TTL_SECONDS")
    jwt_refresh_ttl_seconds: int = Field(
        default=604_800,
        validation_alias="JWT_REFRESH_TTL_SECONDS",
    )
    auth_cookie_secure: bool = Field(default=False, validation_alias="AUTH_COOKIE_SECURE")
    auth_rate_limit_attempts: int = Field(default=10, validation_alias="AUTH_RATE_LIMIT_ATTEMPTS")
    auth_rate_limit_window_seconds: int = Field(
        default=300,
        validation_alias="AUTH_RATE_LIMIT_WINDOW_SECONDS",
    )

    seed_viewer_email: str = Field(validation_alias="SEED_VIEWER_EMAIL")
    seed_viewer_password: SecretStr = Field(validation_alias="SEED_VIEWER_PASSWORD")
    seed_viewer_display_name: str = Field(
        default="Viewer Dev",
        validation_alias="SEED_VIEWER_DISPLAY_NAME",
    )
    seed_operator_email: str = Field(validation_alias="SEED_OPERATOR_EMAIL")
    seed_operator_password: SecretStr = Field(validation_alias="SEED_OPERATOR_PASSWORD")
    seed_operator_display_name: str = Field(
        default="Operator Dev",
        validation_alias="SEED_OPERATOR_DISPLAY_NAME",
    )
    seed_approver_email: str = Field(validation_alias="SEED_APPROVER_EMAIL")
    seed_approver_password: SecretStr = Field(validation_alias="SEED_APPROVER_PASSWORD")
    seed_approver_display_name: str = Field(
        default="Approver Dev",
        validation_alias="SEED_APPROVER_DISPLAY_NAME",
    )
    seed_admin_email: str = Field(validation_alias="SEED_ADMIN_EMAIL")
    seed_admin_password: SecretStr = Field(validation_alias="SEED_ADMIN_PASSWORD")
    seed_admin_display_name: str = Field(
        default="Admin Dev",
        validation_alias="SEED_ADMIN_DISPLAY_NAME",
    )


@lru_cache
def get_settings() -> Settings:
    try:
        return Settings()  # type: ignore[call-arg]
    except ValidationError as exc:
        missing = [str(error["loc"][0]) for error in exc.errors() if error["type"] == "missing"]
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}") from exc
