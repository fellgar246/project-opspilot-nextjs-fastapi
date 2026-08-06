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


class HypothesisDraft(TypedDict, total=False):
    statement: str
    confidence: float
    supporting_evidence: list[str]
    contradicting_evidence: list[str]
    reasoning: str
    grounding: Literal["observed", "mixed", "knowledge_only"]
    critic_verdict: Literal["supported", "weak", "refuted"]
    assumptions: list[str]
    missing_evidence: list[str]
    would_confirm: list[str]
    would_refute: list[str]
    confidence_breakdown: dict[str, Any]
    hypothesis_type: str
    status: Literal["proposed", "accepted", "rejected"]
    rejection_reason: str | None


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


class CritiqueItem(BaseModel):
    statement: str
    counter_evidence: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    would_confirm: list[str] = Field(default_factory=list)
    would_refute: list[str] = Field(default_factory=list)
    verdict: Literal["supported", "weak", "refuted"]
    suggested_tool: str | None = None
    suggested_payload: dict[str, str] = Field(default_factory=dict)


class CritiqueOutput(BaseModel):
    critiques: list[CritiqueItem]


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
    "search_runbooks": "retrieve_runbooks",
    "search_similar_incidents": "retrieve_runbooks",
}

COLLECTION_NODES: list[str] = [
    "collect_service_health",
    "collect_metrics",
    "collect_logs",
    "collect_deployments",
    "collect_code_changes",
    "retrieve_runbooks",
]

TOOL_EVIDENCE_SOURCE_TYPE: dict[str, str] = {
    "get_service_health": "metric",
    "query_metrics": "metric",
    "search_logs": "log",
    "get_recent_deployments": "deployment",
    "get_recent_commits": "commit",
    "get_deployment_details": "deployment",
    "get_pull_request": "pull_request",
    "search_runbooks": "runbook",
    "search_similar_incidents": "similar_incident",
}

TOOL_BY_COLLECTION_NODE: dict[str, str] = {
    "collect_service_health": "get_service_health",
    "collect_metrics": "query_metrics",
    "collect_logs": "search_logs",
    "collect_deployments": "get_recent_deployments",
    "collect_code_changes": "get_recent_commits",
    "retrieve_runbooks": "search_runbooks",
}
