from __future__ import annotations

import pytest
from opspilot.agent.nodes.hypotheses import _validate_hypotheses
from opspilot.agent.state.schema import ClaimItem, HypothesesOutput, HypothesisItem


def test_rejects_hypothesis_without_valid_evidence() -> None:
    output = HypothesesOutput(
        hypotheses=[
            HypothesisItem(
                statement="bad",
                confidence=0.8,
                supporting_evidence=["missing-id"],
                reasoning="r",
            )
        ]
    )
    accepted, rejected = _validate_hypotheses(output, {"real-id"})
    assert not accepted
    assert rejected == ["bad"]


def test_rejects_fact_claim_without_evidence_reference() -> None:
    with pytest.raises(ValueError):
        ClaimItem(text="fact", classification="fact", evidence_ids=[])
