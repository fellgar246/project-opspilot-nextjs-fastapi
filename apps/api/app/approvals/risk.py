from __future__ import annotations

from app.approvals.models import ActionType, RiskLevel


def assess_risk(
    *,
    action_type: ActionType | str,
    target: str,
    environment: str = "production",
    hypothesis_confidence: float,
    rollback_plan: str,
) -> tuple[RiskLevel, str]:
    """
    Explicit risk scoring for proposed mitigations.

    low      -> no system effect (not used for write proposals).
    medium   -> reversible, single-service scope, validated rollback plan.
    high     -> rollback, global flag, restart, or confidence < 0.6.
    critical -> destructive or data-affecting -> rejected in MVP.
    """
    action = ActionType(str(action_type))
    reasons: list[str] = []

    if action == ActionType.SCALE_SERVICE:
        return RiskLevel.CRITICAL, "Scaling service capacity is destructive in MVP and rejected."

    if not rollback_plan.strip():
        return RiskLevel.CRITICAL, "Missing rollback plan; proposal rejected."

    if action in {ActionType.ROLLBACK_DEPLOYMENT, ActionType.RESTART_SERVICE}:
        reasons.append(f"{action.value} affects running production workload")
        level = RiskLevel.HIGH
    elif action == ActionType.TOGGLE_FEATURE_FLAG:
        if environment == "production" and "global" in target.lower():
            reasons.append("global feature flag change in production")
            level = RiskLevel.HIGH
        else:
            reasons.append("reversible single-service flag toggle with rollback plan")
            level = RiskLevel.MEDIUM
    else:
        reasons.append("reversible scoped change with validated rollback plan")
        level = RiskLevel.MEDIUM

    if hypothesis_confidence < 0.6:
        reasons.append(f"hypothesis confidence {hypothesis_confidence:.2f} below 0.6")
        level = RiskLevel.HIGH

    rationale = "; ".join(reasons) if reasons else "standard mitigation risk profile"
    return level, rationale
