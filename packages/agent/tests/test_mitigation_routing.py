from __future__ import annotations

from typing import Any, cast

from opspilot.agent.graph.routing import route_after_approval
from opspilot.agent.state.graph_state import IncidentInvestigationState, initial_state


def _state(**overrides: Any) -> IncidentInvestigationState:
    base = initial_state(
        incident_id="inc-1",
        agent_run_id="run-1",
        graph_thread_id="thread-1",
        incident_title="Test",
        incident_description="desc",
        incident_severity="sev2",
        service_names=["demo-service"],
        repository=None,
        prompt_version="v1",
        model="mock-v1",
        started_at="2026-01-01T00:00:00Z",
    )
    return cast(IncidentInvestigationState, {**base, **overrides})


def test_route_after_approval_approved_executes() -> None:
    state = _state(approval_decision={"decision": "approved"})
    assert route_after_approval(state) == "execute_approved_action"


def test_route_after_approval_rejected_retries_once() -> None:
    state = _state(approval_decision={"decision": "rejected"}, proposal_attempts=1)
    assert route_after_approval(state) == "propose_mitigation"


def test_route_after_approval_rejected_closes_after_limit() -> None:
    state = _state(approval_decision={"decision": "rejected"}, proposal_attempts=2)
    assert route_after_approval(state) == "close_investigation"


def test_route_after_approval_skipped_generates_postmortem() -> None:
    state = _state(approval_decision={"decision": "skipped"})
    assert route_after_approval(state) == "generate_postmortem"
