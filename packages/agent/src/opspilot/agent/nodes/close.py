from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
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
        elif state.get("investigation_status") in {
            "monitoring",
            "resolved",
            "verifying_recovery",
            "awaiting_execution",
        }:
            status = state.get("investigation_status", "completed")
        elif reason == "completed":
            status = "completed"
        else:
            status = reason

        hypotheses = state.get("hypotheses") or []
        top = max(hypotheses, key=lambda item: item.get("confidence", 0), default=None)
        started_at = state.get("started_at")
        duration_seconds: int | None = None
        if started_at:
            try:
                start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                duration_seconds = int((datetime.now(UTC) - start).total_seconds())
            except ValueError:
                duration_seconds = None

        return {
            "current_node": "close_investigation",
            "completed_nodes": ["close_investigation"],
            "investigation_status": "completed" if status not in {"paused"} else status,
            "close_summary": {
                "root_cause_hypothesis_id": top.get("id") if top else None,
                "root_cause_statement": top.get("statement") if top else None,
                "execution_id": state.get("execution_id"),
                "execution_status": state.get("execution_status"),
                "recovery_verdict": (state.get("recovery_verdict") or {}).get("status"),
                "token_usage": state.get("token_usage"),
                "duration_seconds": duration_seconds,
                "postmortem_id": state.get("postmortem_id"),
            },
        }

    return close_investigation
