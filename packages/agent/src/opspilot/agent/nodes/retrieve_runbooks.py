from __future__ import annotations

import time
from typing import Any

from opspilot.agent.nodes.collect import _invoke_tool, _tool_updates
from opspilot.agent.state.graph_state import IncidentInvestigationState


def make_retrieve_runbooks_node(gateway):
    async def retrieve_runbooks(state: IncidentInvestigationState) -> dict[str, Any]:
        started = time.perf_counter()
        service = (
            state.get("affected_services") or state.get("service_names") or ["demo-service"]
        )[0]
        query = f"{state['incident_title']} {state['incident_description']}"
        result = await _invoke_tool(
            gateway,
            state=state,
            tool_name="search_runbooks",
            payload={"query": query, "service": service, "top_k": 5},
        )
        updates = _tool_updates(
            state=state,
            node="retrieve_runbooks",
            tool_name="search_runbooks",
            service=service,
            result=result,
            started=started,
        )
        if result.status == "ok" and not result.evidence_ids:
            updates["negative_findings"] = [
                {
                    "tool_name": "search_runbooks",
                    "service": service,
                    "message": "No relevant runbooks above relevance threshold",
                }
            ]
        return updates

    return retrieve_runbooks
