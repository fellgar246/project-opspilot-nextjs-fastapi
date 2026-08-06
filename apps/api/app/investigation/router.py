from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_capability
from app.auth.models import User
from app.auth.policy import Capability
from app.db.session import get_session
from app.incidents.service import require_incident
from app.investigation import service as investigation_service
from app.investigation.models import AgentRun
from app.investigation.schemas import AgentRunListResponse, AgentRunRead, StartInvestigationResponse

router = APIRouter(tags=["investigation"])


def _agent_run_to_read(run: AgentRun) -> AgentRunRead:
    return AgentRunRead(
        id=str(run.id),
        incident_id=str(run.incident_id),
        graph_thread_id=run.graph_thread_id,
        status=run.status,
        model=run.model,
        prompt_version=run.prompt_version,
        started_at=run.started_at,
        completed_at=run.completed_at,
        token_usage=run.token_usage or {},
        estimated_compute_usage=run.estimated_compute_usage,
        error=run.error,
        node_progress=run.node_progress or {},
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


@router.post(
    "/incidents/{incident_id}/start-investigation",
    response_model=StartInvestigationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_investigation(
    request: Request,
    incident_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_capability(Capability.MANAGE_INVESTIGATION))],
) -> StartInvestigationResponse:
    incident = await require_incident(session, incident_id)
    agent_run = await investigation_service.start_investigation(
        session,
        incident=incident,
        actor=actor,
        request_id=getattr(request.state, "request_id", None),
    )
    await session.commit()
    return StartInvestigationResponse(agent_run_id=str(agent_run.id), status=agent_run.status)


@router.post("/incidents/{incident_id}/pause", response_model=AgentRunRead)
async def pause_investigation(
    request: Request,
    incident_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_capability(Capability.MANAGE_INVESTIGATION))],
) -> AgentRunRead:
    incident = await require_incident(session, incident_id)
    agent_run = await investigation_service.pause_investigation(
        session,
        incident=incident,
        actor=actor,
        request_id=getattr(request.state, "request_id", None),
    )
    await session.commit()
    return _agent_run_to_read(agent_run)


@router.post("/incidents/{incident_id}/resume", response_model=AgentRunRead)
async def resume_investigation(
    request: Request,
    incident_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_capability(Capability.MANAGE_INVESTIGATION))],
) -> AgentRunRead:
    incident = await require_incident(session, incident_id)
    agent_run = await investigation_service.resume_investigation(
        session,
        incident=incident,
        actor=actor,
        request_id=getattr(request.state, "request_id", None),
    )
    await session.commit()
    return _agent_run_to_read(agent_run)


@router.get("/incidents/{incident_id}/agent-runs", response_model=AgentRunListResponse)
async def list_agent_runs(
    incident_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(require_capability(Capability.READ_INCIDENTS))],
) -> AgentRunListResponse:
    await require_incident(session, incident_id)
    runs = await investigation_service.list_agent_runs(session, incident_id)
    return AgentRunListResponse(items=[_agent_run_to_read(run) for run in runs])
