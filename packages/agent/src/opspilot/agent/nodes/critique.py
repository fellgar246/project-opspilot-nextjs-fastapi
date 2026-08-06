from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any, Literal

from opspilot.agent.nodes.base import (
    apply_token_usage,
    build_context_message,
    record_node_timing,
    valid_evidence_ids,
)
from opspilot.agent.parsing import parse_structured_output
from opspilot.agent.prompts import load_prompt
from opspilot.agent.providers.base import LLMMessage, LLMProvider
from opspilot.agent.scoring.confidence import (
    ConfidenceComponents,
    classify_grounding,
    compute_confidence,
)
from opspilot.agent.scoring.missing_evidence import detect_hypothesis_type, detect_missing_evidence
from opspilot.agent.state.graph_state import IncidentInvestigationState
from opspilot.agent.state.schema import CritiqueOutput, HypothesisDraft


def make_critique_hypotheses_node(
    provider: LLMProvider,
) -> Callable[[IncidentInvestigationState], Awaitable[dict[str, Any]]]:
    async def critique_hypotheses(state: IncidentInvestigationState) -> dict[str, Any]:
        started = time.perf_counter()
        known_ids = valid_evidence_ids(state)
        evidence_types = {
            ref["evidence_id"]: ref["source_type"] for ref in state.get("evidence_refs", [])
        }
        explored = set(state.get("explored_tools") or [])

        hypotheses = list(state.get("hypotheses") or [])
        if not hypotheses:
            return {
                "current_node": "critique_hypotheses",
                "completed_nodes": ["critique_hypotheses"],
            }

        messages = [
            LLMMessage(role="system", content=load_prompt("critique")),
            build_context_message(state),
            LLMMessage(
                role="user",
                content=str({"hypotheses": hypotheses, "valid_evidence_ids": sorted(known_ids)}),
            ),
        ]
        parsed, response, parse_errors = await parse_structured_output(
            provider,
            messages=messages,
            response_model=CritiqueOutput,
            node="critique_hypotheses",
        )

        updates: dict[str, Any] = {
            "current_node": "critique_hypotheses",
            "completed_nodes": ["critique_hypotheses"],
            "iteration_count": state["iteration_count"] + 1,
            "token_usage": apply_token_usage(
                state,
                {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                },
            ),
            "node_metrics": [
                record_node_timing(
                    node="critique_hypotheses",
                    started=started,
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                )
            ],
        }
        if parse_errors:
            updates["parse_errors"] = parse_errors
            updates["errors"] = ["critique_hypotheses: failed to parse structured output"]
            return updates

        assert parsed is not None
        critique_by_statement = {item.statement: item for item in parsed.critiques}
        refined: list[HypothesisDraft] = []
        missing_evidence: list[str] = []
        next_tool: str | None = None
        next_payload: dict[str, str] | None = None

        for hypothesis in hypotheses:
            critique = critique_by_statement.get(hypothesis["statement"])
            counter = _filter_ids(critique.counter_evidence if critique else [], known_ids)
            supporting = list(hypothesis["supporting_evidence"])
            grounding = classify_grounding(supporting, evidence_types)
            hypothesis_type = detect_hypothesis_type(hypothesis["statement"])
            missing_signals = detect_missing_evidence(hypothesis_type, explored)
            for signal in missing_signals:
                missing_evidence.append(signal.name)
                if next_tool is None:
                    next_tool = signal.tool
                    next_payload = {key: "" for key in signal.payload_keys}

            verdict = critique.verdict if critique else "weak"
            score, breakdown = compute_confidence(
                ConfidenceComponents(
                    supporting_count=len(supporting),
                    supporting_diversity=len(
                        {evidence_types.get(item, "unknown") for item in supporting}
                    ),
                    contradicting_count=len(counter),
                    grounding=grounding,
                    temporal_coherence=0.7,
                    critic_verdict=verdict,
                )
            )

            status: Literal["proposed", "accepted", "rejected"] = "proposed"
            rejection_reason: str | None = None
            if verdict == "refuted" and counter:
                status = "rejected"
                rejection_reason = "Refuted by critic with counter-evidence"

            refined.append(
                HypothesisDraft(
                    statement=hypothesis["statement"],
                    confidence=score,
                    supporting_evidence=supporting,
                    contradicting_evidence=counter,
                    reasoning=hypothesis.get("reasoning", ""),
                    grounding=grounding,
                    critic_verdict=verdict,
                    assumptions=critique.assumptions if critique else [],
                    missing_evidence=[signal.name for signal in missing_signals],
                    would_confirm=critique.would_confirm if critique else [],
                    would_refute=critique.would_refute if critique else [],
                    confidence_breakdown=breakdown,
                    hypothesis_type=hypothesis_type,
                    status=status,
                    rejection_reason=rejection_reason,
                )
            )

            if critique and critique.suggested_tool and critique.suggested_tool not in explored:
                next_tool = critique.suggested_tool
                next_payload = critique.suggested_payload or None

        updates["hypotheses"] = refined
        if missing_evidence:
            updates["missing_evidence"] = missing_evidence
        if next_tool:
            updates["suggested_collection"] = {"tool": next_tool, "payload": next_payload or {}}
        return updates

    return critique_hypotheses


def _filter_ids(values: list[str], known_ids: set[str]) -> list[str]:
    return [item for item in values if item in known_ids]
