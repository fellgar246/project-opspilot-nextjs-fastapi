"""Agent evaluation framework for reproducible quality measurement."""

from opspilot.agent.evaluations.compare import GATE_THRESHOLDS, compare_runs
from opspilot.agent.evaluations.metrics import EvaluationMetrics, compute_metrics
from opspilot.agent.evaluations.models import EvaluationCaseSpec, load_cases
from opspilot.agent.evaluations.runner import EvaluationRunReport, RunConfig, run_evaluation

__all__ = [
    "EvaluationCaseSpec",
    "EvaluationMetrics",
    "EvaluationRunReport",
    "GATE_THRESHOLDS",
    "RunConfig",
    "compare_runs",
    "compute_metrics",
    "load_cases",
    "run_evaluation",
]
