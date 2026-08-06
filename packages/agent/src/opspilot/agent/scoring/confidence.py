from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from opspilot.agent.config import get_agent_settings


@dataclass(frozen=True)
class ConfidenceComponents:
    supporting_count: int
    supporting_diversity: int
    contradicting_count: int
    grounding: Literal["observed", "mixed", "knowledge_only"]
    temporal_coherence: float
    critic_verdict: Literal["supported", "weak", "refuted"] | None


def compute_confidence(components: ConfidenceComponents) -> tuple[float, dict[str, Any]]:
    """Deterministic confidence with auditable breakdown."""
    settings = get_agent_settings()
    knowledge_cap = settings.knowledge_only_confidence_cap
    refuted_cap = 0.3

    base = 0.15
    support_bonus = min(0.35, components.supporting_count * 0.08)
    diversity_bonus = min(0.15, max(0, components.supporting_diversity - 1) * 0.05)
    contradict_penalty = min(0.35, components.contradicting_count * 0.12)
    temporal_bonus = components.temporal_coherence * 0.1

    verdict_adjustment = 0.0
    if components.critic_verdict == "supported":
        verdict_adjustment = 0.1
    elif components.critic_verdict == "weak":
        verdict_adjustment = -0.08
    elif components.critic_verdict == "refuted":
        verdict_adjustment = -0.25

    raw = (
        base
        + support_bonus
        + diversity_bonus
        + temporal_bonus
        + verdict_adjustment
        - contradict_penalty
    )
    score = max(0.0, min(1.0, raw))

    cap = 1.0
    if components.grounding == "knowledge_only":
        cap = knowledge_cap
    if components.critic_verdict == "refuted":
        cap = min(cap, refuted_cap)
    score = min(score, cap)

    breakdown = {
        "base": base,
        "support_bonus": support_bonus,
        "diversity_bonus": diversity_bonus,
        "contradict_penalty": contradict_penalty,
        "temporal_bonus": temporal_bonus,
        "verdict_adjustment": verdict_adjustment,
        "grounding": components.grounding,
        "critic_verdict": components.critic_verdict,
        "cap_applied": cap,
        "raw_before_cap": raw,
        "final": score,
    }
    return score, breakdown


def classify_grounding(
    supporting_evidence: list[str],
    evidence_source_types: dict[str, str],
) -> Literal["observed", "mixed", "knowledge_only"]:
    if not supporting_evidence:
        return "knowledge_only"
    observed_types = {"metric", "log", "deployment", "commit", "pull_request", "feature_flag"}
    knowledge_types = {"runbook", "similar_incident"}
    types = {evidence_source_types.get(item, "unknown") for item in supporting_evidence}
    has_observed = bool(types & observed_types)
    has_knowledge = bool(types & knowledge_types)
    if has_observed and has_knowledge:
        return "mixed"
    if has_observed:
        return "observed"
    return "knowledge_only"
