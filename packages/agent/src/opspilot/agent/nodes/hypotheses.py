from __future__ import annotations

import time
from typing import Any

from opspilot.agent.nodes.base import (
    apply_token_usage,
    build_context_message,
    filter_hypothesis_evidence,
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
from opspilot.agent.state.graph_state import IncidentInvestigationState
from opspilot.agent.state.schema import Claim, HypothesesOutput, HypothesisDraft


def make_hypotheses_node(provider: LLMProvider):
    async def generate_hypotheses(state: IncidentInvestigationState) -> dict[str, Any]:
        started = time.perf_counter()
        known_ids = valid_evidence_ids(state)
        evidence_types = {
            ref["evidence_id"]: ref["source_type"] for ref in state.get("evidence_refs", [])
        }
        messages = [
            LLMMessage(role="system", content=load_prompt("hypotheses")),
            build_context_message(state),
        ]

        parsed, response, parse_errors = await parse_structured_output(
            provider,
            messages=messages,
            response_model=HypothesesOutput,
            node="generate_hypotheses",
        )
        updates: dict[str, Any] = {
            "current_node": "generate_hypotheses",
            "completed_nodes": ["generate_hypotheses"],
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
                    node="generate_hypotheses",
                    started=started,
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                )
            ],
        }
        if parse_errors:
            updates["parse_errors"] = parse_errors
            updates["errors"] = ["generate_hypotheses: failed to parse structured output"]
            return updates

        assert parsed is not None
        accepted, rejected = _validate_hypotheses(parsed, known_ids, evidence_types)
        if rejected and not accepted:
            # One regeneration attempt
            regen_messages = messages + [
                LLMMessage(
                    role="user",
                    content=(
                        "Previous hypotheses lacked valid supporting_evidence references. "
                        f"Valid evidence_ids: {sorted(known_ids)}. Regenerate."
                    ),
                )
            ]
            parsed_retry, response_retry, retry_errors = await parse_structured_output(
                provider,
                messages=regen_messages,
                response_model=HypothesesOutput,
                node="generate_hypotheses",
            )
            updates["token_usage"] = apply_token_usage(
                {**state, "token_usage": updates["token_usage"]},
                {
                    "prompt_tokens": response_retry.usage.prompt_tokens,
                    "completion_tokens": response_retry.usage.completion_tokens,
                },
            )
            if retry_errors:
                updates["parse_errors"] = (updates.get("parse_errors") or []) + retry_errors
            if parsed_retry is not None:
                accepted, rejected = _validate_hypotheses(parsed_retry, known_ids)

        if rejected:
            updates["errors"] = [f"Rejected hypotheses without valid evidence: {len(rejected)}"]
        if accepted:
            updates["hypotheses"] = accepted
            updates["claims"] = _hypotheses_to_claims(accepted)
        return updates

    return generate_hypotheses


def _validate_hypotheses(
    output: HypothesesOutput,
    known_ids: set[str],
    evidence_types: dict[str, str],
) -> tuple[list[HypothesisDraft], list[str]]:
    accepted: list[HypothesisDraft] = []
    rejected: list[str] = []
    for item in output.hypotheses:
        refs = filter_hypothesis_evidence(item.supporting_evidence, known_ids)
        if not refs:
            rejected.append(item.statement)
            continue
        grounding = classify_grounding(refs, evidence_types)
        score, breakdown = compute_confidence(
            ConfidenceComponents(
                supporting_count=len(refs),
                supporting_diversity=len(
                    {evidence_types.get(item_id, "unknown") for item_id in refs}
                ),
                contradicting_count=0,
                grounding=grounding,
                temporal_coherence=0.5,
                critic_verdict=None,
            )
        )
        accepted.append(
            HypothesisDraft(
                statement=item.statement,
                confidence=min(item.confidence, score),
                supporting_evidence=refs,
                contradicting_evidence=[],
                reasoning=item.reasoning,
                grounding=grounding,
                confidence_breakdown=breakdown,
                status="proposed",
            )
        )
    return accepted, rejected


def _hypotheses_to_claims(hypotheses: list[HypothesisDraft]) -> list[Claim]:
    claims: list[Claim] = []
    for hypothesis in hypotheses:
        claims.append(
            Claim(
                text=hypothesis["statement"],
                classification="inference",
                evidence_ids=hypothesis["supporting_evidence"],
            )
        )
        claims.append(
            Claim(
                text=f"Investigate root cause related to: {hypothesis['statement']}",
                classification="recommendation",
                evidence_ids=[],
            )
        )
    return claims
