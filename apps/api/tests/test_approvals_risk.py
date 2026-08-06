from __future__ import annotations

import pytest
from app.approvals.models import ActionType, RiskLevel
from app.approvals.risk import assess_risk


@pytest.mark.parametrize(
    ("action_type", "target", "confidence", "expected_level"),
    [
        (ActionType.TOGGLE_FEATURE_FLAG, "checkout/feature_x", 0.8, RiskLevel.MEDIUM),
        (ActionType.ROLLBACK_DEPLOYMENT, "checkout/deploy-1", 0.8, RiskLevel.HIGH),
        (ActionType.ROLLBACK_DEPLOYMENT, "checkout/deploy-1", 0.5, RiskLevel.HIGH),
        (ActionType.TOGGLE_FEATURE_FLAG, "global/kill_switch", 0.9, RiskLevel.HIGH),
        (ActionType.SCALE_SERVICE, "checkout", 0.9, RiskLevel.CRITICAL),
    ],
)
def test_assess_risk_parametrized(action_type, target, confidence, expected_level) -> None:
    level, rationale = assess_risk(
        action_type=action_type,
        target=target,
        hypothesis_confidence=confidence,
        rollback_plan="Revert to previous stable deployment",
    )
    assert level == expected_level
    assert rationale
