from __future__ import annotations

from opspilot.tools.time_range import TimeRangeInput
from pydantic import BaseModel, Field


class ServiceInput(BaseModel):
    service: str


class ServiceHealthOutput(BaseModel):
    service: str
    status: str
    version: str
    dependencies: list[dict[str, str]]
    active_scenarios: list[str] = Field(default_factory=list)


class QueryMetricsInput(BaseModel):
    service: str
    metric: str
    time_range: TimeRangeInput
    aggregation: str = "avg"
    group_by: list[str] | None = None


class MetricPoint(BaseModel):
    timestamp: str
    value: float


class QueryMetricsOutput(BaseModel):
    service: str
    metric: str
    unit: str | None = None
    series: list[MetricPoint]
    statistics: dict[str, float | str]
    baseline_comparison: dict[str, float]
    time_range_label: str | None = None


class SearchLogsInput(BaseModel):
    service: str
    query: str = ""
    time_range: TimeRangeInput
    level: str | None = None
    limit: int = 100


class LogEntry(BaseModel):
    timestamp: str
    level: str
    service: str
    message: str
    endpoint: str | None = None
    status: int | None = None
    trace_id: str | None = None


class SearchLogsOutput(BaseModel):
    service: str
    entries: list[LogEntry]
    total_count: int
    patterns: list[dict[str, int | str]]
    truncated: bool = False
    time_range_label: str | None = None


class DeploymentsInput(BaseModel):
    service: str
    time_range: TimeRangeInput


class DeploymentSummary(BaseModel):
    deployment_id: str
    service: str
    version: str
    commit_sha: str
    deployed_at: str | float
    deployed_by: str
    status: str
    changelog: str | None = None


class DeploymentsOutput(BaseModel):
    deployments: list[DeploymentSummary]
    time_range_label: str | None = None


class DeploymentDetailsInput(BaseModel):
    deployment_id: str


class DeploymentDetailsOutput(BaseModel):
    deployment_id: str
    service: str
    version: str
    commit_sha: str
    deployed_at: str | float
    deployed_by: str
    status: str
    changelog: str | None = None
    commits: list[str] = Field(default_factory=list)
    diff_summary: str = ""


class CommitsInput(BaseModel):
    repository: str
    time_range: TimeRangeInput
    path: str | None = None


class CommitSummary(BaseModel):
    sha: str
    author: str
    message: str
    committed_at: str
    files_changed: list[str] = Field(default_factory=list)
    diff_summary: str = ""


class CommitsOutput(BaseModel):
    repository: str
    commits: list[CommitSummary]
    time_range_label: str | None = None


class PullRequestInput(BaseModel):
    repository: str
    number: int


class PullRequestOutput(BaseModel):
    repository: str
    number: int
    title: str
    description: str
    author: str
    commits: list[str] = Field(default_factory=list)
    files_changed: list[str] = Field(default_factory=list)
    merged_at: str | None = None
    reviewers: list[str] = Field(default_factory=list)
    diff_summary: str = ""


class FeatureFlagsInput(BaseModel):
    service: str
    key: str | None = None


class FeatureFlagItem(BaseModel):
    key: str
    service: str
    enabled: bool
    rollout_percentage: float | None = None
    updated_at: str | float | None = None
    updated_by: str | None = None


class FeatureFlagsOutput(BaseModel):
    flags: list[FeatureFlagItem]


class ListServicesOutput(BaseModel):
    services: list[dict[str, str]]


class EmptyInput(BaseModel):
    pass
