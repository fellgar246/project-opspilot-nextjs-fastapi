from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

SIMULATOR_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = SIMULATOR_ROOT.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    service_name: str = "demo-service"
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 8080

    scenarios_dir: Path = Field(default_factory=lambda: SIMULATOR_ROOT / "scenarios")
    data_dir: Path = Field(default_factory=lambda: SIMULATOR_ROOT / "data")
    replay_dir: Path | None = None

    internal_auth_token: str = "sim-internal-dev-token"
    otel_exporter_endpoint: str | None = None
    default_db_pool_max_size: int = 50
    ramp_down_seconds: float = 30.0
    reproducibility_tolerance: float = 0.15

    @model_validator(mode="after")
    def _default_replay_dir(self) -> Self:
        if self.replay_dir is None:
            self.replay_dir = self.data_dir / "replay"
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
