from __future__ import annotations

import time
from typing import Any

from opspilot.agent.nodes.base import (
    apply_token_usage,
    build_context_message,
    record_node_timing,
)
from opspilot.agent.parsing import parse_structured_output
from opspilot.agent.prompts import load_prompt
from opspilot.agent.providers.base import LLMMessage, LLMProvider
from opspilot.agent.state.graph_state import IncidentInvestigationState
from opspilot.agent.state.schema import TriageOutput


def make_triage_node(provider: LLMProvider):
    async def triage_incident(state: IncidentInvestigationState) -> dict[str, Any]:
        started = time.perf_counter()
        messages = [
            LLMMessage(role="system", content=load_prompt("triage")),
            build_context_message(state),
        ]
        parsed, response, parse_errors = await parse_structured_output(
            provider,
            messages=messages,
            response_model=TriageOutput,
            node="triage_incident",
        )
        updates: dict[str, Any] = {
            "current_node": "triage_incident",
            "completed_nodes": ["triage_incident"],
            "token_usage": apply_token_usage(
                state,
                {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                },
            ),
            "node_metrics": [
                record_node_timing(
                    node="triage_incident",
                    started=started,
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                )
            ],
        }
        if parse_errors:
            updates["parse_errors"] = parse_errors
            updates["errors"] = ["triage_incident: failed to parse structured output"]
            return updates

        assert parsed is not None
        updates.update(
            {
                "perceived_severity": parsed.perceived_severity,
                "affected_services": parsed.affected_services,
                "time_window": parsed.time_window,
            }
        )
        return updates

    return triage_incident
