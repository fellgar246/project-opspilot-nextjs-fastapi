from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ToolGatewaySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    sim_url: str = "http://127.0.0.1:8080"
    prometheus_url: str = "http://127.0.0.1:9090"
    loki_url: str = "http://127.0.0.1:3100"
    git_data_dir: Path = Field(default_factory=lambda: Path("simulator/data"))
    repo_root: Path = Field(default_factory=lambda: Path("."))

    tool_mode: Literal["live", "record", "replay"] = "live"
    fixtures_dir: Path = Field(
        default_factory=lambda: Path("packages/tools/tests/fixtures/recordings")
    )

    global_concurrency_limit: int = 20
    per_tool_concurrency_limit: int = 5
    circuit_breaker_threshold: int = 5
    circuit_breaker_cooldown_seconds: float = 30.0
    max_time_range_hours: float = 24.0
    max_log_limit: int = 500
    max_metric_points: int = 100
    output_summary_max_chars: int = 2000


@lru_cache
def get_tool_settings() -> ToolGatewaySettings:
    return ToolGatewaySettings()
