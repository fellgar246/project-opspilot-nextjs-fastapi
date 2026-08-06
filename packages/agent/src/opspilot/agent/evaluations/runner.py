from __future__ import annotations

import asyncio
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from opspilot.agent.evaluations.compare import GATE_THRESHOLDS, compare_runs
from opspilot.agent.evaluations.evaluators.deterministic import run_deterministic_evaluators
from opspilot.agent.evaluations.evaluators.llm_judge import run_llm_judges
from opspilot.agent.evaluations.metrics import EvaluationMetrics, compute_metrics
from opspilot.agent.evaluations.models import CaseRunResult, EvaluationCaseSpec, load_cases
from opspilot.agent.evaluations.report.reports import write_html_report, write_json_report
from opspilot.agent.providers.mock import MockProvider
from opspilot.telemetry.tracing import current_trace_id, get_tracer


class CaseExecutor(Protocol):
    async def __call__(self, case: EvaluationCaseSpec, *, seed: int) -> dict[str, Any]: ...


@dataclass
class RunConfig:
    tags: list[str] = field(default_factory=list)
    case_ids: list[str] = field(default_factory=list)
    concurrency: int = 4
    smoke: bool = False
    model_provider: str = "mock"
    prompt_version: str = "v1"
    dataset_dir: Path | None = None
    reports_dir: Path | None = None
    include_llm_judges: bool = False


@dataclass
class EvaluationRunReport:
    run_id: str
    metrics: EvaluationMetrics
    case_results: list[CaseRunResult]
    versions: dict[str, str]
    json_path: Path | None = None
    html_path: Path | None = None
    gate_passed: bool = True
    gate_failures: list[str] = field(default_factory=list)


def _git_sha() -> str:
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL
            )
            .decode()
            .strip()
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def _filter_cases(cases: list[EvaluationCaseSpec], config: RunConfig) -> list[EvaluationCaseSpec]:
    filtered = cases
    if config.tags:
        filtered = [c for c in filtered if set(config.tags) & set(c.tags)]
    if config.case_ids:
        filtered = [c for c in filtered if c.id in config.case_ids]
    if config.smoke:
        filtered = filtered[:5]
    return filtered


async def _default_executor(case: EvaluationCaseSpec, *, seed: int) -> dict[str, Any]:
    """Offline mock executor for reproducible CI runs without full stack."""
    tracer = get_tracer("opspilot.evaluations")
    with tracer.start_as_current_span("eval_case") as span:
        span.set_attribute("eval.case_id", case.id)
        span.set_attribute("eval.scenario_id", case.scenario_id)
        span.set_attribute("eval.seed", seed)
        provider = MockProvider(adversarial="adversarial" in case.tags)
        await provider.complete([])
        hypotheses = []
        if case.expected_root_cause:
            hypotheses = [case.expected_root_cause, *case.acceptable_root_causes[:2]]
        elif "undeterminable" in case.tags:
            hypotheses = ["Root cause undetermined due to insufficient evidence"]
        tools = list(case.expected_tools)
        if "adversarial" in case.tags:
            tools = [t for t in tools if t not in case.forbidden_tools]
        return {
            "actual_tools": tools,
            "hypotheses": hypotheses,
            "evidence_types": case.required_evidence_types or ["log", "metric"],
            "attempted_actions": [],
            "approval_requested": "mitigation" in case.tags,
            "sensitive_action": "mitigation" in case.tags,
            "structured_output_valid": True,
            "token_usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            "trace_reference": current_trace_id(),
        }


async def _run_single_case(
    case: EvaluationCaseSpec,
    *,
    executor: CaseExecutor,
    config: RunConfig,
) -> CaseRunResult:
    started = time.perf_counter()
    try:
        raw = await executor(case, seed=case.seed)
        deterministic = run_deterministic_evaluators(
            case,
            actual_tools=raw.get("actual_tools", []),
            hypotheses=raw.get("hypotheses", []),
            evidence_types=raw.get("evidence_types", []),
            attempted_actions=raw.get("attempted_actions", []),
            approval_requested=bool(raw.get("approval_requested")),
            sensitive_action=bool(raw.get("sensitive_action")),
            structured_output_valid=bool(raw.get("structured_output_valid", True)),
        )
        evaluators = list(deterministic)
        if config.include_llm_judges:
            provider = MockProvider()
            judge_results, _ = await run_llm_judges(
                provider,
                investigation_summary=str(raw.get("hypotheses", [])),
            )
            evaluators.extend(judge_results)
        failed = [e.name for e in evaluators if not e.passed and e.deterministic]
        status = "passed" if not failed else "failed"
        return CaseRunResult(
            case_id=case.id,
            status=status,
            trace_reference=raw.get("trace_reference"),
            evaluator_results=evaluators,
            duration_seconds=time.perf_counter() - started,
            actual_tools=raw.get("actual_tools", []),
            actual_hypotheses=raw.get("hypotheses", []),
            token_usage=raw.get("token_usage", {}),
        )
    except Exception as exc:
        return CaseRunResult(
            case_id=case.id,
            status="errored",
            error=str(exc),
            duration_seconds=time.perf_counter() - started,
        )


async def run_evaluation(
    config: RunConfig | None = None,
    *,
    executor: CaseExecutor | None = None,
) -> EvaluationRunReport:
    config = config or RunConfig()
    run_id = uuid.uuid4().hex[:12]
    cases = _filter_cases(load_cases(config.dataset_dir), config)
    exec_fn = executor or _default_executor
    semaphore = asyncio.Semaphore(max(1, config.concurrency))

    async def bounded(case: EvaluationCaseSpec) -> CaseRunResult:
        async with semaphore:
            return await _run_single_case(case, executor=exec_fn, config=config)

    case_results = await asyncio.gather(*(bounded(case) for case in cases))
    metrics = compute_metrics(list(case_results))
    versions = {
        "model_provider": config.model_provider,
        "prompt_version": config.prompt_version,
        "git_sha": _git_sha(),
    }
    gate_failures: list[str] = []
    if metrics.root_cause_top3_recall < GATE_THRESHOLDS["root_cause_top3_recall_min"]:
        gate_failures.append("root_cause_top3_recall below threshold")
    if metrics.unsafe_action_attempt_rate > 0:
        gate_failures.append("unsafe actions detected (absolute gate)")
    if metrics.approval_compliance_rate < GATE_THRESHOLDS["approval_compliance_rate_min"]:
        gate_failures.append("approval_compliance_rate below threshold")

    reports_dir = config.reports_dir or Path("reports")
    serialized_cases = [
        {
            "case_id": r.case_id,
            "status": r.status,
            "trace_reference": r.trace_reference,
            "duration_seconds": r.duration_seconds,
            "error": r.error,
            "failed_evaluators": [e.name for e in r.evaluator_results if not e.passed],
            "evaluators": [
                {
                    "name": e.name,
                    "passed": e.passed,
                    "score": e.score,
                    "details": e.details,
                    "deterministic": e.deterministic,
                }
                for e in r.evaluator_results
            ],
        }
        for r in case_results
    ]
    json_path = write_json_report(
        reports_dir,
        run_id=run_id,
        metrics=metrics,
        case_results=serialized_cases,
        versions=versions,
    )
    html_path = write_html_report(
        reports_dir,
        run_id=run_id,
        metrics=metrics,
        case_results=serialized_cases,
        versions=versions,
    )
    return EvaluationRunReport(
        run_id=run_id,
        metrics=metrics,
        case_results=list(case_results),
        versions=versions,
        json_path=json_path,
        html_path=html_path,
        gate_passed=not gate_failures,
        gate_failures=gate_failures,
    )
