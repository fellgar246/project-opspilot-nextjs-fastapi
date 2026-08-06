from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_capability
from app.auth.models import User
from app.auth.policy import Capability
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.db.session import get_session
from app.evaluations import service
from app.evaluations.schemas import (
    EvaluationCaseRead,
    EvaluationCompareRequest,
    EvaluationRunListResponse,
    EvaluationRunRead,
    EvaluationRunRequest,
)

router = APIRouter(prefix="/evaluations", tags=["evaluations"])


@router.get("/cases", response_model=list[EvaluationCaseRead])
async def list_cases(
    _: Annotated[User, Depends(require_capability(Capability.RUN_EVALUATIONS))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[EvaluationCaseRead]:
    await service.sync_cases_from_repo(session)
    return await service.list_cases(session)


@router.post("/run", response_model=EvaluationRunRead)
async def run_evaluations(
    body: EvaluationRunRequest,
    _: Annotated[User, Depends(require_capability(Capability.RUN_EVALUATIONS))],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> EvaluationRunRead:
    run = await service.start_evaluation_run(
        session,
        settings=settings,
        tags=body.tags,
        smoke=body.smoke,
        concurrency=body.concurrency,
    )
    case_results = await service.get_case_results(session, run.id)
    return service.run_to_read(run, case_results)


@router.get("/runs", response_model=EvaluationRunListResponse)
async def list_runs(
    _: Annotated[User, Depends(require_capability(Capability.RUN_EVALUATIONS))],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> EvaluationRunListResponse:
    runs = await service.list_runs(session, limit=limit)
    items: list[EvaluationRunRead] = []
    for run in runs:
        case_results = await service.get_case_results(session, run.id)
        items.append(service.run_to_read(run, case_results))
    return EvaluationRunListResponse(items=items, total=len(items))


@router.get("/runs/{run_id}", response_model=EvaluationRunRead)
async def get_run(
    run_id: UUID,
    _: Annotated[User, Depends(require_capability(Capability.RUN_EVALUATIONS))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> EvaluationRunRead:
    run = await service.get_run(session, run_id)
    if run is None:
        raise AppError("Evaluation run not found", status_code=404)
    case_results = await service.get_case_results(session, run_id)
    return service.run_to_read(run, case_results)


@router.post("/compare")
async def compare_runs(
    body: EvaluationCompareRequest,
    _: Annotated[User, Depends(require_capability(Capability.RUN_EVALUATIONS))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    try:
        return await service.compare_evaluation_runs(
            session,
            baseline_id=body.baseline_run_id,
            candidate_id=body.candidate_run_id,
        )
    except ValueError as exc:
        raise AppError(str(exc), status_code=404) from exc
