from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from opspilot.agent.evaluations import RunConfig, compare_runs, run_evaluation
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.evaluations.models import EvaluationCase, EvaluationCaseResult, EvaluationRun
from app.evaluations.schemas import EvaluationCaseRead, EvaluationRunRead


async def sync_cases_from_repo(session: AsyncSession, dataset_dir: Path | None = None) -> int:
    from opspilot.agent.evaluations.models import load_cases

    root = dataset_dir or Path(__file__).resolve().parents[4] / "datasets" / "evaluations"
    specs = load_cases(root)
    count = 0
    for spec in specs:
        row = await session.get(EvaluationCase, spec.id)
        payload = {
            "scenario_id": spec.scenario_id,
            "input_payload": spec.input_payload,
            "expected_root_cause": spec.expected_root_cause,
            "acceptable_root_causes": spec.acceptable_root_causes,
            "expected_tools": spec.expected_tools,
            "forbidden_tools": spec.forbidden_tools,
            "unsafe_actions": spec.unsafe_actions,
            "required_evidence_types": spec.required_evidence_types,
            "tags": spec.tags,
            "seed": spec.seed,
        }
        if row is None:
            session.add(EvaluationCase(id=spec.id, **payload))
        else:
            for key, value in payload.items():
                setattr(row, key, value)
        count += 1
    await session.commit()
    return count


async def list_cases(session: AsyncSession) -> list[EvaluationCaseRead]:
    result = await session.execute(select(EvaluationCase).order_by(EvaluationCase.id))
    return [
        EvaluationCaseRead(
            id=row.id,
            scenario_id=row.scenario_id,
            input_payload=row.input_payload,
            expected_root_cause=row.expected_root_cause,
            acceptable_root_causes=row.acceptable_root_causes,
            expected_tools=row.expected_tools,
            forbidden_tools=row.forbidden_tools,
            unsafe_actions=row.unsafe_actions,
            required_evidence_types=row.required_evidence_types,
            tags=row.tags,
            seed=row.seed,
        )
        for row in result.scalars().all()
    ]


async def start_evaluation_run(
    session: AsyncSession,
    *,
    settings: Settings,
    tags: list[str] | None = None,
    smoke: bool = False,
    concurrency: int = 4,
) -> EvaluationRun:
    await sync_cases_from_repo(session)
    run = EvaluationRun(
        id=uuid.uuid4(),
        status="running",
        model_provider=settings.model_provider,
        prompt_version="v1",
        git_sha=settings.git_sha,
        tags_filter=tags or [],
    )
    session.add(run)
    await session.commit()

    reports_dir = Path("reports")
    config = RunConfig(
        tags=tags or [],
        smoke=smoke,
        concurrency=concurrency,
        model_provider=settings.model_provider,
        reports_dir=reports_dir,
    )
    report = await run_evaluation(config)

    for case_result in report.case_results:
        session.add(
            EvaluationCaseResult(
                run_id=run.id,
                case_id=case_result.case_id,
                status=case_result.status,
                trace_reference=case_result.trace_reference,
                evaluator_results=[
                    {
                        "name": e.name,
                        "passed": e.passed,
                        "score": e.score,
                        "details": e.details,
                        "deterministic": e.deterministic,
                    }
                    for e in case_result.evaluator_results
                ],
                duration_seconds=case_result.duration_seconds,
                error=case_result.error,
            )
        )

    run.status = "completed"
    run.metrics = report.metrics.to_dict()
    run.gate_passed = report.gate_passed
    run.gate_failures = report.gate_failures
    run.report_json_path = str(report.json_path) if report.json_path else None
    run.report_html_path = str(report.html_path) if report.html_path else None
    run.completed_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(run)
    return run


async def get_run(session: AsyncSession, run_id: uuid.UUID) -> EvaluationRun | None:
    return await session.get(EvaluationRun, run_id)


async def list_runs(session: AsyncSession, *, limit: int = 20) -> list[EvaluationRun]:
    result = await session.execute(
        select(EvaluationRun).order_by(EvaluationRun.started_at.desc()).limit(limit)
    )
    return list(result.scalars().all())


async def get_case_results(session: AsyncSession, run_id: uuid.UUID) -> list[EvaluationCaseResult]:
    result = await session.execute(
        select(EvaluationCaseResult).where(EvaluationCaseResult.run_id == run_id)
    )
    return list(result.scalars().all())


def run_to_read(
    run: EvaluationRun, case_results: list[EvaluationCaseResult] | None = None
) -> EvaluationRunRead:
    return EvaluationRunRead(
        id=str(run.id),
        status=run.status,
        model_provider=run.model_provider,
        prompt_version=run.prompt_version,
        git_sha=run.git_sha,
        tags_filter=run.tags_filter,
        metrics=run.metrics,
        gate_passed=run.gate_passed,
        gate_failures=run.gate_failures,
        report_json_path=run.report_json_path,
        report_html_path=run.report_html_path,
        started_at=run.started_at,
        completed_at=run.completed_at,
        case_results=[
            {
                "case_id": cr.case_id,
                "status": cr.status,
                "trace_reference": cr.trace_reference,
                "duration_seconds": cr.duration_seconds,
                "error": cr.error,
                "evaluator_results": cr.evaluator_results,
            }
            for cr in (case_results or [])
        ],  # type: ignore[arg-type]
    )


async def compare_evaluation_runs(
    session: AsyncSession,
    *,
    baseline_id: uuid.UUID,
    candidate_id: uuid.UUID,
) -> dict:
    baseline = await get_run(session, baseline_id)
    candidate = await get_run(session, candidate_id)
    if baseline is None or candidate is None:
        raise ValueError("run not found")
    from opspilot.agent.evaluations.metrics import EvaluationMetrics

    from dataclasses import fields

    valid = {f.name for f in fields(EvaluationMetrics)}
    base_metrics = EvaluationMetrics(
        **{k: float(v) for k, v in baseline.metrics.items() if k in valid}
    )
    cand_metrics = EvaluationMetrics(
        **{k: float(v) for k, v in candidate.metrics.items() if k in valid}
    )
    base_cases = {row.case_id: row.status for row in await get_case_results(session, baseline_id)}
    cand_cases = {row.case_id: row.status for row in await get_case_results(session, candidate_id)}
    report = compare_runs(
        base_metrics, cand_metrics, baseline_cases=base_cases, candidate_cases=cand_cases
    )
    return report.to_dict()
