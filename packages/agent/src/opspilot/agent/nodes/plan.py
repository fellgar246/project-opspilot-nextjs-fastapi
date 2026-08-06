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
from opspilot.agent.state.schema import InvestigationPlanOutput


def make_plan_node(provider: LLMProvider):
    async def build_investigation_plan(state: IncidentInvestigationState) -> dict[str, Any]:
        started = time.perf_counter()
        messages = [
            LLMMessage(role="system", content=load_prompt("plan")),
            build_context_message(state),
        ]
        parsed, response, parse_errors = await parse_structured_output(
            provider,
            messages=messages,
            response_model=InvestigationPlanOutput,
            node="build_investigation_plan",
        )
        updates: dict[str, Any] = {
            "current_node": "build_investigation_plan",
            "completed_nodes": ["build_investigation_plan"],
            "token_usage": apply_token_usage(
                state,
                {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                },
            ),
            "node_metrics": [
                record_node_timing(
                    node="build_investigation_plan",
                    started=started,
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                )
            ],
        }
        if parse_errors:
            updates["parse_errors"] = parse_errors
            updates["errors"] = ["build_investigation_plan: failed to parse structured output"]
            return updates

        assert parsed is not None
        updates["investigation_plan"] = [step.model_dump() for step in parsed.steps]
        return updates

    return build_investigation_plan
