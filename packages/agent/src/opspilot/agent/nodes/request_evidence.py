from __future__ import annotations

from typing import Any

from opspilot.agent.graph.routing import next_collection_target
from opspilot.agent.state.graph_state import IncidentInvestigationState


def make_request_more_evidence_node():
    async def request_more_evidence(state: IncidentInvestigationState) -> dict[str, Any]:
        target = next_collection_target(state)
        return {
            "current_node": "request_more_evidence",
            "completed_nodes": ["request_more_evidence"],
            "next_collection_node": target,
            "iteration_count": state["iteration_count"] + 1,
        }

    return request_more_evidence
