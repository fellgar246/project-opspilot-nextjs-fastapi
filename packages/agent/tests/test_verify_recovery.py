from __future__ import annotations

from typing import Any, cast

import pytest
from opspilot.agent.graph.routing import (
    route_after_approval,
    route_after_execution,
    route_after_verify_recovery,
)
from opspilot.agent.nodes.verify_recovery import _determine_verdict
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


def test_route_after_approval_skipped_generates_postmortem() -> None:
    state = _state(approval_decision={"decision": "skipped"})
    assert route_after_approval(state) == "generate_postmortem"


def test_route_after_approval_rejected_retries_once() -> None:
    state = _state(approval_decision={"decision": "rejected"}, proposal_attempts=1)
    assert route_after_approval(state) == "propose_mitigation"


def test_route_after_execution_success_verifies() -> None:
    state = _state(execution_status="succeeded")
    assert route_after_execution(state) == "verify_recovery"


def test_route_after_verify_not_recovered_retries() -> None:
    state = _state(recovery_verdict={"status": "not_recovered"}, proposal_attempts=0)
    assert route_after_verify_recovery(state) == "propose_mitigation"


@pytest.mark.parametrize(
    ("baseline", "degraded", "post", "expected"),
    [
        (0.01, 0.4, 0.02, "recovered"),
        (0.01, 0.4, 0.1, "partially_recovered"),
        (0.01, 0.4, 0.5, "not_recovered"),
        (None, 0.4, 0.02, "inconclusive"),
    ],
)
def test_recovery_verdicts(
    baseline: float | None,
    degraded: float | None,
    post: float | None,
    expected: str,
) -> None:
    verdict = _determine_verdict(
        baseline=baseline,
        degraded=degraded,
        post_action=post,
        error_threshold=0.05,
        partial_threshold=0.15,
    )
    assert verdict == expected
