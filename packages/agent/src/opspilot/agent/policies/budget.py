from __future__ import annotations

from opspilot.agent.config import AgentSettings, get_agent_settings
from opspilot.agent.state.graph_state import IncidentInvestigationState


def exceeded_budget(
    state: IncidentInvestigationState, settings: AgentSettings | None = None
) -> bool:
    settings = settings or get_agent_settings()
    usage = state["token_usage"]
    total = usage["prompt_tokens"] + usage["completion_tokens"]
    return total >= settings.max_tokens_per_incident


def exceeded_tool_calls(
    state: IncidentInvestigationState, settings: AgentSettings | None = None
) -> bool:
    settings = settings or get_agent_settings()
    return state["tool_call_count"] >= settings.max_tool_calls_per_run


def exceeded_iterations(
    state: IncidentInvestigationState, settings: AgentSettings | None = None
) -> bool:
    settings = settings or get_agent_settings()
    return state["iteration_count"] >= settings.max_iterations
