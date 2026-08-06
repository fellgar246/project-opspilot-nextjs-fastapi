from __future__ import annotations

import json
import time
from typing import Any
from uuid import UUID

from opspilot.agent.metrics import record_node_metric
from opspilot.agent.providers.base import LLMMessage
from opspilot.agent.state.graph_state import IncidentInvestigationState
from opspilot.agent.state.schema import TokenUsageState


def apply_token_usage(state: IncidentInvestigationState, usage: TokenUsageState) -> TokenUsageState:
    current = state["token_usage"]
    return {
        "prompt_tokens": current["prompt_tokens"] + usage["prompt_tokens"],
        "completion_tokens": current["completion_tokens"] + usage["completion_tokens"],
    }


def build_context_message(state: IncidentInvestigationState) -> LLMMessage:
    payload = {
        "incident_id": state["incident_id"],
        "incident_title": state["incident_title"],
        "incident_description": state["incident_description"],
        "incident_severity": state["incident_severity"],
        "service_names": state["service_names"],
        "repository": state["repository"],
        "evidence_ids": [ref["evidence_id"] for ref in state.get("evidence_refs", [])],
        "negative_findings": state.get("negative_findings", []),
    }
    return LLMMessage(role="user", content=json.dumps(payload))


def record_node_timing(
    *,
    node: str,
    started: float,
    prompt_tokens: int,
    completion_tokens: int,
    retries: int = 0,
) -> dict[str, Any]:
    duration_ms = int((time.perf_counter() - started) * 1000)
    metric = {
        "node": node,
        "duration_ms": duration_ms,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "retries": retries,
    }
    record_node_metric(
        node=node,
        duration_ms=duration_ms,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        retries=retries,
    )
    return metric


def valid_evidence_ids(state: IncidentInvestigationState) -> set[str]:
    return {ref["evidence_id"] for ref in state.get("evidence_refs", [])}


def filter_hypothesis_evidence(supporting: list[str], known_ids: set[str]) -> list[str]:
    return [item for item in supporting if item in known_ids]


def as_uuid(value: str | UUID) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))
