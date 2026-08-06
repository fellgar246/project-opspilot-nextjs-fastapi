from __future__ import annotations

from typing import Any

from opspilot.agent.graph.routing import next_collection_target, unexplored_tools
from opspilot.agent.state.graph_state import IncidentInvestigationState
from opspilot.agent.state.schema import COLLECTION_NODE_BY_TOOL


def make_request_more_evidence_node():
    async def request_more_evidence(state: IncidentInvestigationState) -> dict[str, Any]:
        suggested = state.get("suggested_collection")
        if suggested and suggested.get("tool") in unexplored_tools(state):
            target = COLLECTION_NODE_BY_TOOL.get(suggested["tool"])
        else:
            target = next_collection_target(state)
        return {
            "current_node": "request_more_evidence",
            "completed_nodes": ["request_more_evidence"],
            "next_collection_node": target,
            "iteration_count": state["iteration_count"] + 1,
        }

    return request_more_evidence
