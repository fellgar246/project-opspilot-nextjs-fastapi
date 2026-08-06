from __future__ import annotations

from datetime import UTC, datetime

from opspilot.agent.graph.routing import (
    route_after_critique,
    route_after_hypotheses,
    unexplored_tools,
)
from opspilot.agent.state.graph_state import initial_state


def _state(**overrides):
    base = initial_state(
        incident_id="inc-1",
        agent_run_id="run-1",
        graph_thread_id="thread-1",
        incident_title="t",
        incident_description="d",
        incident_severity="sev2",
        service_names=["demo-service"],
        repository=None,
        prompt_version="v1",
        model="mock-v1",
        started_at=datetime.now(UTC).isoformat(),
    )
    base.update(overrides)
    return base


def test_route_closes_on_high_confidence() -> None:
    state = _state(
        hypotheses=[
            {"statement": "x", "confidence": 0.9, "supporting_evidence": ["e"], "reasoning": "r"}
        ]
    )
    assert route_after_hypotheses(state) == "close"


def test_route_requests_more_evidence_when_low_confidence_and_tools_remain() -> None:
    state = _state(
        hypotheses=[
            {"statement": "x", "confidence": 0.2, "supporting_evidence": ["e"], "reasoning": "r"}
        ],
        explored_tools=["get_service_health"],
    )
    assert route_after_hypotheses(state) == "request_more_evidence"
    assert unexplored_tools(state)


def test_route_closes_when_no_unexplored_tools() -> None:
    state = _state(
        hypotheses=[
            {"statement": "x", "confidence": 0.2, "supporting_evidence": ["e"], "reasoning": "r"}
        ],
        explored_tools=[
            "get_service_health",
            "query_metrics",
            "search_logs",
            "get_recent_deployments",
            "get_recent_commits",
            "search_runbooks",
        ],
    )
    assert route_after_hypotheses(state) == "close"


def test_route_closes_on_iteration_limit() -> None:
    state = _state(iteration_count=12, hypotheses=[])
    assert route_after_hypotheses(state) == "close"


def test_route_after_critique_proposes_mitigation_on_high_confidence() -> None:
    state = _state(
        hypotheses=[
            {"statement": "x", "confidence": 0.9, "supporting_evidence": ["e"], "reasoning": "r"}
        ]
    )
    assert route_after_critique(state) == "propose_mitigation"


def test_route_after_critique_respects_rejected_hypotheses() -> None:
    state = _state(
        hypotheses=[
            {
                "statement": "rejected",
                "confidence": 0.9,
                "supporting_evidence": ["e"],
                "reasoning": "r",
                "status": "rejected",
            }
        ],
        explored_tools=["search_runbooks"],
    )
    assert route_after_critique(state) == "request_more_evidence"
