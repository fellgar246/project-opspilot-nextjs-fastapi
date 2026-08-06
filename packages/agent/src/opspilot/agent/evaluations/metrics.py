from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any

from opspilot.agent.evaluations.models import CaseRunResult


@dataclass
class EvaluationMetrics:
    root_cause_accuracy: float = 0.0
    root_cause_top3_recall: float = 0.0
    tool_selection_precision: float = 0.0
    tool_selection_recall: float = 0.0
    evidence_grounding_score: float = 0.0
    unsupported_claim_rate: float = 0.0
    unsafe_action_attempt_rate: float = 0.0
    approval_compliance_rate: float = 0.0
    investigation_completion_rate: float = 0.0
    mean_investigation_time_seconds: float = 0.0
    token_usage_total: int = 0
    estimated_compute_usage: float = 0.0
    recovery_verification_accuracy: float = 0.0
    case_count: int = 0
    errored_count: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvaluationMetrics:
        int_fields = {"token_usage_total", "case_count", "errored_count"}
        valid = {field.name for field in fields(cls)}
        kwargs: dict[str, float | int] = {}
        for key, value in data.items():
            if key not in valid:
                continue
            kwargs[key] = int(value) if key in int_fields else float(value)
        return cls(**kwargs)  # type: ignore[arg-type]

    def to_dict(self) -> dict[str, Any]:
        return {
            "root_cause_accuracy": self.root_cause_accuracy,
            "root_cause_top3_recall": self.root_cause_top3_recall,
            "tool_selection_precision": self.tool_selection_precision,
            "tool_selection_recall": self.tool_selection_recall,
            "evidence_grounding_score": self.evidence_grounding_score,
            "unsupported_claim_rate": self.unsupported_claim_rate,
            "unsafe_action_attempt_rate": self.unsafe_action_attempt_rate,
            "approval_compliance_rate": self.approval_compliance_rate,
            "investigation_completion_rate": self.investigation_completion_rate,
            "mean_investigation_time_seconds": self.mean_investigation_time_seconds,
            "token_usage_total": self.token_usage_total,
            "estimated_compute_usage": self.estimated_compute_usage,
            "recovery_verification_accuracy": self.recovery_verification_accuracy,
            "case_count": self.case_count,
            "errored_count": self.errored_count,
        }


def _score(results: list[CaseRunResult], name: str) -> float:
    scores: list[float] = []
    for result in results:
        if result.status == "errored":
            continue
        for evaluator in result.evaluator_results:
            if evaluator.name == name and evaluator.score is not None:
                scores.append(evaluator.score)
    return sum(scores) / len(scores) if scores else 0.0


def _pass_rate(results: list[CaseRunResult], name: str) -> float:
    applicable = [
        r
        for r in results
        if r.status != "errored" and any(e.name == name for e in r.evaluator_results)
    ]
    if not applicable:
        return 1.0
    passed = sum(
        1 for r in applicable if any(e.name == name and e.passed for e in r.evaluator_results)
    )
    return passed / len(applicable)


def compute_metrics(results: list[CaseRunResult]) -> EvaluationMetrics:
    completed = [r for r in results if r.status != "errored"]
    metrics = EvaluationMetrics(
        case_count=len(results),
        errored_count=sum(1 for r in results if r.status == "errored"),
    )
    if not completed:
        return metrics

    metrics.root_cause_accuracy = _score(completed, "root_cause_exact")
    metrics.root_cause_top3_recall = _pass_rate(completed, "root_cause_top3")
    metrics.tool_selection_precision = _score(completed, "expected_tools")
    metrics.tool_selection_recall = _score(completed, "expected_tools")
    metrics.evidence_grounding_score = _score(completed, "required_evidence_types")
    metrics.unsupported_claim_rate = 1.0 - _pass_rate(completed, "structured_output")
    metrics.unsafe_action_attempt_rate = 1.0 - _pass_rate(completed, "unsafe_actions")
    metrics.approval_compliance_rate = _pass_rate(completed, "approval_compliance")
    metrics.investigation_completion_rate = sum(1 for r in completed if r.status == "passed") / len(
        completed
    )
    metrics.mean_investigation_time_seconds = sum(r.duration_seconds for r in completed) / len(
        completed
    )
    metrics.token_usage_total = sum(
        r.token_usage.get("total_tokens", 0)
        + r.token_usage.get("prompt_tokens", 0)
        + r.token_usage.get("completion_tokens", 0)
        for r in completed
    )
    metrics.estimated_compute_usage = sum(
        r.token_usage.get("estimated_compute", 0.0) for r in completed
    )
    metrics.recovery_verification_accuracy = _pass_rate(completed, "structured_output")
    return metrics
