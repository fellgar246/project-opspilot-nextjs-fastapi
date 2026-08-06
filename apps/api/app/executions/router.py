from __future__ import annotations

from typing import Annotated
from uuid import UUID

from app.auth.dependencies import require_capability
from app.auth.models import User
from app.auth.policy import Capability
from app.db.session import get_session
from app.executions import service as execution_service
from app.executions.models import ActionExecution
from app.incidents.service import require_incident
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(tags=["executions"])


class ActionExecutionRead(BaseModel):
    id: str
    incident_id: str
    proposed_action_id: str
    approval_id: str
    execution_status: str
    input_payload: dict
    output_payload: dict | None
    idempotency_key: str
    error: str | None
    started_at: str
    completed_at: str | None


class ActionExecutionListResponse(BaseModel):
    items: list[ActionExecutionRead]


def _to_read(row: ActionExecution) -> ActionExecutionRead:
    return ActionExecutionRead(
        id=str(row.id),
        incident_id=str(row.incident_id),
        proposed_action_id=str(row.proposed_action_id),
        approval_id=str(row.approval_id),
        execution_status=row.execution_status,
        input_payload=row.input_payload or {},
        output_payload=row.output_payload,
        idempotency_key=row.idempotency_key,
        error=row.error,
        started_at=row.started_at.isoformat(),
        completed_at=row.completed_at.isoformat() if row.completed_at else None,
    )


@router.get(
    "/incidents/{incident_id}/action-executions",
    response_model=ActionExecutionListResponse,
)
async def list_action_executions(
    incident_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(require_capability(Capability.READ_INCIDENTS))],
) -> ActionExecutionListResponse:
    await require_incident(session, incident_id)
    rows = await execution_service.list_executions_for_incident(session, incident_id)
    return ActionExecutionListResponse(items=[_to_read(row) for row in rows])
