from __future__ import annotations

from datetime import UTC, datetime

from opspilot.agent.config import AgentSettings, get_agent_settings
from opspilot.agent.policies.budget import (
    exceeded_budget,
    exceeded_iterations,
    exceeded_tool_calls,
)
from opspilot.agent.state.graph_state import IncidentInvestigationState


def investigation_timed_out(
    state: IncidentInvestigationState, settings: AgentSettings | None = None
) -> bool:
    settings = settings or get_agent_settings()
    started = datetime.fromisoformat(state["started_at"].replace("Z", "+00:00"))
    elapsed = (datetime.now(UTC) - started).total_seconds()
    return elapsed >= settings.investigation_timeout_seconds


def should_stop(state: IncidentInvestigationState, settings: AgentSettings | None = None) -> str | None:
    if state.get("paused"):
        return "paused"
    if exceeded_iterations(state, settings):
        return "iteration_limit_reached"
    if exceeded_budget(state, settings):
        return "budget_exceeded"
    if exceeded_tool_calls(state, settings):
        return "tool_call_limit_reached"
    if investigation_timed_out(state, settings):
        return "timeout"
    return None
