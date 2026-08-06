from __future__ import annotations

import pytest
from opspilot.agent.scoring.confidence import ConfidenceComponents, compute_confidence


@pytest.mark.parametrize(
    ("components", "max_score"),
    [
        (
            ConfidenceComponents(
                supporting_count=0,
                supporting_diversity=0,
                contradicting_count=0,
                grounding="knowledge_only",
                temporal_coherence=1.0,
                critic_verdict="supported",
            ),
            0.6,
        ),
        (
            ConfidenceComponents(
                supporting_count=5,
                supporting_diversity=3,
                contradicting_count=0,
                grounding="observed",
                temporal_coherence=1.0,
                critic_verdict="supported",
            ),
            1.0,
        ),
        (
            ConfidenceComponents(
                supporting_count=3,
                supporting_diversity=2,
                contradicting_count=2,
                grounding="mixed",
                temporal_coherence=0.2,
                critic_verdict="refuted",
            ),
            0.3,
        ),
    ],
)
def test_confidence_caps_and_monotonicity(
    components: ConfidenceComponents, max_score: float
) -> None:
    score, breakdown = compute_confidence(components)
    assert score <= max_score
    assert breakdown["final"] == score
