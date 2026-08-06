from __future__ import annotations

from datetime import UTC, datetime

import pytest
from opspilot.agent.nodes.critique import make_critique_hypotheses_node
from opspilot.agent.providers.mock import MockProvider
from opspilot.agent.state.graph_state import initial_state


@pytest.mark.asyncio
async def test_critique_does_not_create_new_evidence_ids() -> None:
    provider = MockProvider()
    node = make_critique_hypotheses_node(provider)
    state = initial_state(
        incident_id="inc-1",
        agent_run_id="run-1",
        graph_thread_id="thread-1",
        incident_title="Outage",
        incident_description="Errors",
        incident_severity="sev2",
        service_names=["demo-service"],
        repository=None,
        prompt_version="v1",
        model="mock-v1",
        started_at=datetime.now(UTC).isoformat(),
    )
    state["hypotheses"] = [
        {
            "statement": "Recent deployment degraded demo-service.",
            "confidence": 0.7,
            "supporting_evidence": ["ev-1"],
            "reasoning": "timing",
        }
    ]
    state["evidence_refs"] = [
        {
            "evidence_id": "ev-1",
            "source_type": "deployment",
            "title": "Deployment",
            "summary": "dep",
            "tool_name": "get_recent_deployments",
        }
    ]
    updates = await node(state)
    known = {"ev-1"}
    for hypothesis in updates["hypotheses"]:
        for evidence_id in hypothesis.get("contradicting_evidence", []):
            assert evidence_id in known
        for evidence_id in hypothesis["supporting_evidence"]:
            assert evidence_id in known
