from __future__ import annotations

from typing import Annotated, Any, TypedDict

from opspilot.agent.state.reducers import (
    merge_claims,
    merge_completed_nodes,
    merge_errors,
    merge_evidence_refs,
    merge_explored_tools,
    merge_hypotheses,
    merge_missing_evidence,
    merge_negative_findings,
    merge_node_metrics,
    merge_parse_errors,
    merge_timeline,
)
from opspilot.agent.state.schema import (
    Claim,
    EvidenceRef,
    HypothesisDraft,
    InvestigationStep,
    NegativeFinding,
    NodeMetric,
    ParseError,
    TimelineEntry,
    TokenUsageState,
)


class IncidentInvestigationState(TypedDict):
    incident_id: str
    agent_run_id: str
    graph_thread_id: str
    incident_title: str
    incident_description: str
    incident_severity: str
    service_names: list[str]
    repository: str | None

    perceived_severity: str | None
    affected_services: list[str]
    time_window: dict[str, str]

    investigation_plan: list[InvestigationStep]
    evidence_refs: Annotated[list[EvidenceRef], merge_evidence_refs]
    negative_findings: Annotated[list[NegativeFinding], merge_negative_findings]
    timeline: Annotated[list[TimelineEntry], merge_timeline]

    hypotheses: Annotated[list[HypothesisDraft], merge_hypotheses]
    claims: Annotated[list[Claim], merge_claims]

    iteration_count: int
    tool_call_count: int
    token_usage: TokenUsageState
    investigation_status: str
    current_node: str | None
    completed_nodes: Annotated[list[str], merge_completed_nodes]
    explored_tools: Annotated[list[str], merge_explored_tools]
    next_collection_node: str | None
    missing_evidence: Annotated[list[str], merge_missing_evidence]
    suggested_collection: dict[str, Any] | None

    errors: Annotated[list[str], merge_errors]
    parse_errors: Annotated[list[ParseError], merge_parse_errors]
    node_metrics: Annotated[list[NodeMetric], merge_node_metrics]

    paused: bool
    prompt_version: str
    started_at: str
    model: str

    pending_action_id: str | None
    proposal: dict[str, Any] | None
    proposal_confidence: float | None
    assessed_risk_level: str | None
    approval_decision: dict[str, Any] | None
    proposal_attempts: int
    rejected_action_ids: list[str]


def initial_state(
    *,
    incident_id: str,
    agent_run_id: str,
    graph_thread_id: str,
    incident_title: str,
    incident_description: str,
    incident_severity: str,
    service_names: list[str],
    repository: str | None,
    prompt_version: str,
    model: str,
    started_at: str,
) -> IncidentInvestigationState:
    return IncidentInvestigationState(
        incident_id=incident_id,
        agent_run_id=agent_run_id,
        graph_thread_id=graph_thread_id,
        incident_title=incident_title,
        incident_description=incident_description,
        incident_severity=incident_severity,
        service_names=service_names,
        repository=repository,
        perceived_severity=None,
        affected_services=[],
        time_window={},
        investigation_plan=[],
        evidence_refs=[],
        negative_findings=[],
        timeline=[],
        hypotheses=[],
        claims=[],
        iteration_count=0,
        tool_call_count=0,
        token_usage={"prompt_tokens": 0, "completion_tokens": 0},
        investigation_status="running",
        current_node=None,
        completed_nodes=[],
        explored_tools=[],
        next_collection_node=None,
        missing_evidence=[],
        suggested_collection=None,
        errors=[],
        parse_errors=[],
        node_metrics=[],
        paused=False,
        prompt_version=prompt_version,
        started_at=started_at,
        model=model,
        pending_action_id=None,
        proposal=None,
        proposal_confidence=None,
        assessed_risk_level=None,
        approval_decision=None,
        proposal_attempts=0,
        rejected_action_ids=[],
    )
