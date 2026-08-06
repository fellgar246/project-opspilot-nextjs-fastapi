from __future__ import annotations

from typing import Literal

from opspilot.agent.config import get_agent_settings
from opspilot.agent.policies.limits import should_stop
from opspilot.agent.state.graph_state import IncidentInvestigationState
from opspilot.agent.state.schema import COLLECTION_NODES, TOOL_BY_COLLECTION_NODE


def route_after_critique(
    state: IncidentInvestigationState,
) -> Literal["request_more_evidence", "close"]:
    stop_reason = should_stop(state)
    if stop_reason is not None:
        return "close"

    settings = get_agent_settings()
    hypotheses = [
        item for item in (state.get("hypotheses") or []) if item.get("status") != "rejected"
    ]
    top = max((item["confidence"] for item in hypotheses), default=0.0)
    if top >= settings.confidence_threshold:
        return "close"
    if state.get("suggested_collection") and unexplored_tools(state):
        return "request_more_evidence"
    if not unexplored_tools(state):
        return "close"
    return "request_more_evidence"


def route_after_hypotheses(
    state: IncidentInvestigationState,
) -> Literal["request_more_evidence", "close"]:
    stop_reason = should_stop(state)
    if stop_reason is not None:
        return "close"

    settings = get_agent_settings()
    hypotheses = state.get("hypotheses") or []
    top = max((item["confidence"] for item in hypotheses), default=0.0)
    if top >= settings.confidence_threshold:
        return "close"
    if not unexplored_tools(state):
        return "close"
    return "request_more_evidence"


def unexplored_tools(state: IncidentInvestigationState) -> list[str]:
    explored = set(state.get("explored_tools") or [])
    remaining = [tool for tool in TOOL_BY_COLLECTION_NODE.values() if tool not in explored]
    return remaining


def next_collection_target(state: IncidentInvestigationState) -> str | None:
    explored_nodes = set(state.get("completed_nodes") or [])
    for node in COLLECTION_NODES:
        if node not in explored_nodes:
            return node
    return None
