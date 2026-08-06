from __future__ import annotations

from datetime import UTC, datetime

from opspilot.agent.graph.routing import route_after_hypotheses
from opspilot.agent.providers.mock import MockProvider
from opspilot.agent.state.graph_state import initial_state


def test_adversarial_provider_terminates_via_iteration_limit() -> None:
    state = initial_state(
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
    provider = MockProvider(adversarial=True)
    assert provider.adversarial is True

    for _ in range(20):
        state["hypotheses"] = [
            {
                "statement": "never confident",
                "confidence": 0.4,
                "supporting_evidence": ["ev-1"],
                "reasoning": "adversarial",
            }
        ]
        decision = route_after_hypotheses(state)
        if decision == "close":
            break
        state["iteration_count"] = state["iteration_count"] + 1
        state["explored_tools"] = [
            "get_service_health",
            "query_metrics",
            "search_logs",
            "get_recent_deployments",
            "get_recent_commits",
        ]
    else:
        raise AssertionError("routing did not terminate")

    assert state["iteration_count"] <= 12
