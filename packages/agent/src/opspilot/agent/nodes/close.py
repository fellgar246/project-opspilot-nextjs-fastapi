from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from opspilot.agent.policies.limits import should_stop
from opspilot.agent.state.graph_state import IncidentInvestigationState


def make_close_investigation_node() -> Callable[
    [IncidentInvestigationState], Awaitable[dict[str, Any]]
]:
    async def close_investigation(state: IncidentInvestigationState) -> dict[str, Any]:
        reason = should_stop(state) or "completed"
        if reason == "paused":
            status = "paused"
        elif reason == "completed":
            status = "completed"
        else:
            status = reason
        return {
            "current_node": "close_investigation",
            "completed_nodes": ["close_investigation"],
            "investigation_status": status,
        }

    return close_investigation
