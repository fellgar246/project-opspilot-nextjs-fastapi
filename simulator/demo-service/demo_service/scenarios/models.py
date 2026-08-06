from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class SignalSpec(BaseModel):
    metric: str | None = None
    log_pattern: str | None = None
    behavior: str | None = None
    factor: float | None = None
    rate_per_minute: float | None = None
    note: str | None = None


class DeploymentSpec(BaseModel):
    version: str
    commit_sha: str | None = None
    offset_seconds: int = -120
    deployed_by: str = "ci-bot"
    changelog: str = ""


class ScenarioDefinition(BaseModel):
    id: str
    title: str
    description: str = ""
    expected_root_cause: str
    expected_tools: list[str] = Field(default_factory=list)
    forbidden_actions: list[str] = Field(default_factory=list)
    signals: list[SignalSpec] = Field(default_factory=list)
    ramp_up_seconds: float = 60.0
    ramp_down_seconds: float | None = None
    tags: list[str] = Field(default_factory=list)
    deployment: DeploymentSpec | None = None
    feature_flag: dict[str, Any] | None = None
    effects: dict[str, Any] = Field(default_factory=dict)


Mode = Literal["live", "replay"]


class ActiveScenario(BaseModel):
    id: str
    seed: int
    activated_at: float
    mode: Mode = "live"
    intensity: float = 0.0
    deployment_id: str | None = None
