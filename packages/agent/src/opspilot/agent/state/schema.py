from __future__ import annotations

from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field, field_validator


class TokenUsageState(TypedDict):
    prompt_tokens: int
    completion_tokens: int


class EvidenceRef(TypedDict):
    evidence_id: str
    source_type: str
    title: str
    summary: str
    tool_name: str


class NegativeFinding(TypedDict):
    tool_name: str
    service: str
    message: str


class TimelineEntry(TypedDict):
    occurred_at: str
    kind: str
    title: str
    summary: str
    evidence_id: str | None


class InvestigationStep(TypedDict):
    order: int
    tool: str
    question: str
    service: str


class HypothesisDraft(TypedDict):
    statement: str
    confidence: float
    supporting_evidence: list[str]
    reasoning: str


class Claim(TypedDict):
    text: str
    classification: Literal["fact", "inference", "recommendation"]
    evidence_ids: list[str]


class NodeMetric(TypedDict):
    node: str
    duration_ms: int
    prompt_tokens: int
    completion_tokens: int
    retries: int


class ParseError(TypedDict):
    node: str
    model: str
    message: str


class TriageOutput(BaseModel):
    perceived_severity: str
    affected_services: list[str]
    time_window: dict[str, str]
    reasoning: str


class PlanStep(BaseModel):
    order: int
    tool: str
    question: str
    service: str


class InvestigationPlanOutput(BaseModel):
    steps: list[PlanStep]


class HypothesisItem(BaseModel):
    statement: str
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_evidence: list[str]
    reasoning: str


class HypothesesOutput(BaseModel):
    hypotheses: list[HypothesisItem]


class ClaimItem(BaseModel):
    text: str
    classification: Literal["fact", "inference", "recommendation"]
    evidence_ids: list[str] = Field(default_factory=list)

    @field_validator("evidence_ids")
    @classmethod
    def facts_require_evidence(cls, value: list[str], info: Any) -> list[str]:
        classification = info.data.get("classification")
        if classification == "fact" and not value:
            raise ValueError("fact claims require at least one evidence_id")
        return value


class ClaimsOutput(BaseModel):
    claims: list[ClaimItem]


COLLECTION_NODE_BY_TOOL: dict[str, str] = {
    "get_service_health": "collect_service_health",
    "query_metrics": "collect_metrics",
    "search_logs": "collect_logs",
    "get_recent_deployments": "collect_deployments",
    "get_recent_commits": "collect_code_changes",
    "get_deployment_details": "collect_deployments",
    "get_pull_request": "collect_code_changes",
}

COLLECTION_NODES: list[str] = [
    "collect_service_health",
    "collect_metrics",
    "collect_logs",
    "collect_deployments",
    "collect_code_changes",
]

TOOL_BY_COLLECTION_NODE: dict[str, str] = {
    "collect_service_health": "get_service_health",
    "collect_metrics": "query_metrics",
    "collect_logs": "search_logs",
    "collect_deployments": "get_recent_deployments",
    "collect_code_changes": "get_recent_commits",
}
