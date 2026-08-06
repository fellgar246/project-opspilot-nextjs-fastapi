from __future__ import annotations

import pytest
from opspilot.agent.evaluations import RunConfig, compare_runs, load_cases, run_evaluation
from opspilot.agent.evaluations.metrics import EvaluationMetrics, compute_metrics
from opspilot.agent.evaluations.models import (
    CaseRunResult,
    EvaluatorResult,
    matches_acceptable_root_cause,
)


def test_load_cases_meets_minimum_count() -> None:
    cases = load_cases()
    assert len(cases) >= 30


def test_undeterminable_cases_exist() -> None:
    cases = load_cases()
    null_cases = [c for c in cases if c.expected_root_cause is None]
    assert len(null_cases) >= 3


def test_adversarial_cases_exist() -> None:
    cases = load_cases()
    adversarial = [c for c in cases if "adversarial" in c.tags]
    assert len(adversarial) >= 3


def test_root_cause_matching_normalization() -> None:
    assert matches_acceptable_root_cause(
        "Missing PAYMENTS_API_KEY environment variable after deployment",
        expected="PAYMENTS_API_KEY environment variable is missing after deploy",
        acceptable=["PAYMENTS_API_KEY not injected in checkout service"],
    )


@pytest.mark.asyncio
async def test_run_evaluation_smoke() -> None:
    report = await run_evaluation(RunConfig(smoke=True, concurrency=2))
    assert report.metrics.case_count == 5
    assert report.json_path is not None
    assert report.html_path is not None


@pytest.mark.asyncio
async def test_unsafe_action_absolute_gate() -> None:
    results = [
        CaseRunResult(
            case_id="X",
            status="failed",
            evaluator_results=[
                EvaluatorResult(name="unsafe_actions", passed=False, score=0.0),
            ],
        )
    ]
    metrics = compute_metrics(results)
    assert metrics.unsafe_action_attempt_rate > 0


def test_compare_regression_gate() -> None:
    baseline = EvaluationMetrics(root_cause_top3_recall=0.9, unsafe_action_attempt_rate=0.0)
    candidate = EvaluationMetrics(root_cause_top3_recall=0.7, unsafe_action_attempt_rate=0.0)
    report = compare_runs(baseline, candidate)
    assert not report.gate_passed


def test_unsafe_action_gate_absolute() -> None:
    baseline = EvaluationMetrics(unsafe_action_attempt_rate=0.0)
    candidate = EvaluationMetrics(unsafe_action_attempt_rate=0.01)
    report = compare_runs(baseline, candidate)
    assert not report.gate_passed
    assert any("unsafe" in f.lower() for f in report.gate_failures)
