from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

SourceType = Literal[
    "metric",
    "log",
    "deployment",
    "commit",
    "pull_request",
    "feature_flag",
    "runbook",
    "similar_incident",
    "note",
]


class MetricStructuredData(BaseModel):
    metric_name: str
    value: float
    unit: str | None = None
    labels: dict[str, str] = Field(default_factory=dict)


class LogStructuredData(BaseModel):
    level: str
    service: str
    endpoint: str | None = None
    status: int | None = None
    latency_ms: float | None = None
    trace_id: str | None = None
    error_type: str | None = None


class DeploymentStructuredData(BaseModel):
    deployment_id: str
    service: str
    version: str
    commit_sha: str
    deployed_by: str
    status: str


class CommitStructuredData(BaseModel):
    sha: str
    author: str
    message: str
    files_changed: list[str] = Field(default_factory=list)


class PullRequestStructuredData(BaseModel):
    number: int
    title: str
    author: str
    merged_at: str | None = None
    commits: list[str] = Field(default_factory=list)


class FeatureFlagStructuredData(BaseModel):
    key: str
    service: str
    enabled: bool
    rollout_percentage: float | None = None


class RunbookStructuredData(BaseModel):
    runbook_id: str
    title: str
    section: str | None = None
    relevance: float | None = None


class SimilarIncidentStructuredData(BaseModel):
    incident_id: str
    title: str
    root_cause: str
    resolution: str
    similarity_score: float | None = None


class NoteStructuredData(BaseModel):
    author: str | None = None
    tags: list[str] = Field(default_factory=list)


STRUCTURED_DATA_MODELS: dict[str, type[BaseModel]] = {
    "metric": MetricStructuredData,
    "log": LogStructuredData,
    "deployment": DeploymentStructuredData,
    "commit": CommitStructuredData,
    "pull_request": PullRequestStructuredData,
    "feature_flag": FeatureFlagStructuredData,
    "runbook": RunbookStructuredData,
    "similar_incident": SimilarIncidentStructuredData,
    "note": NoteStructuredData,
}


def validate_structured_data(source_type: str, data: dict[str, Any]) -> dict[str, Any]:
    model = STRUCTURED_DATA_MODELS.get(source_type)
    if model is None:
        raise ValueError(f"Unknown source_type: {source_type}")
    validated = model.model_validate(data)
    return validated.model_dump()
