from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.approvals import service as approval_service
from app.approvals.models import ProposedAction
from app.approvals.schemas import (
    ApprovalDecisionRequest,
    ApprovalListResponse,
    ApprovalRead,
    ProposedActionListResponse,
    ProposedActionRead,
    RejectApprovalRequest,
)
from app.auth.dependencies import require_capability
from app.auth.models import User
from app.auth.policy import Capability
from app.core.errors import AppError
from app.db.session import get_session
from app.incidents.service import require_incident

router = APIRouter(tags=["approvals"])


def _action_to_read(action: ProposedAction) -> ProposedActionRead:
    return ProposedActionRead(
        id=str(action.id),
        incident_id=str(action.incident_id),
        agent_run_id=str(action.agent_run_id),
        action_type=action.action_type,
        description=action.description,
        target=action.target,
        parameters=action.parameters or {},
        risk_level=action.risk_level,
        risk_rationale=action.risk_rationale,
        expected_result=action.expected_result,
        rollback_plan=action.rollback_plan,
        supporting_evidence=[str(item) for item in action.supporting_evidence],
        hypothesis_ids=[str(item) for item in action.hypothesis_ids],
        status=action.status,
        requested_by=str(action.requested_by) if action.requested_by else None,
        created_at=action.created_at,
    )


@router.get("/approvals/pending", response_model=ApprovalListResponse)
async def list_pending_approvals(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(require_capability(Capability.READ_INCIDENTS))],
) -> ApprovalListResponse:
    rows = await approval_service.list_pending_approvals(session)
    items = [
        ApprovalRead(
            id=str(approval.id),
            proposed_action_id=str(action.id),
            incident_id=str(incident.id),
            incident_title=incident.title,
            incident_severity=incident.severity.value,
            action=_action_to_read(action),
            decision=approval.decision,
            reason=approval.reason,
            expires_at=approval.expires_at,
            requested_at=approval.requested_at,
            reviewed_at=approval.reviewed_at,
            reviewed_by=str(approval.reviewed_by) if approval.reviewed_by else None,
        )
        for approval, action, incident in rows
    ]
    return ApprovalListResponse(items=items)


@router.get("/incidents/{incident_id}/proposed-actions", response_model=ProposedActionListResponse)
async def list_incident_proposed_actions(
    incident_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(require_capability(Capability.READ_INCIDENTS))],
) -> ProposedActionListResponse:
    await require_incident(session, incident_id)
    actions = await approval_service.list_proposed_actions_for_incident(session, incident_id)
    return ProposedActionListResponse(items=[_action_to_read(item) for item in actions])


@router.post("/approvals/{approval_id}/approve", response_model=ApprovalRead)
async def approve_proposed_action(
    request: Request,
    approval_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_capability(Capability.APPROVE_ACTION))],
    body: ApprovalDecisionRequest | None = None,
) -> ApprovalRead:
    approval = await approval_service.get_approval(session, approval_id)
    if approval is None:
        raise AppError("Approval not found", status_code=404)

    if approval.requested_by and approval.requested_by == actor.id:
        raise AppError("self_approval_forbidden", status_code=403)

    action = await session.get(ProposedAction, approval.proposed_action_id)
    if action is None:
        raise AppError("Proposed action not found", status_code=404)

    approval = await approval_service.approve_action(
        session,
        approval=approval,
        actor=actor,
        request_id=getattr(request.state, "request_id", None),
    )
    await session.commit()

    incident = await require_incident(session, action.incident_id)
    return ApprovalRead(
        id=str(approval.id),
        proposed_action_id=str(action.id),
        incident_id=str(incident.id),
        incident_title=incident.title,
        incident_severity=incident.severity.value,
        action=_action_to_read(action),
        decision=approval.decision,
        reason=approval.reason,
        expires_at=approval.expires_at,
        requested_at=approval.requested_at,
        reviewed_at=approval.reviewed_at,
        reviewed_by=str(approval.reviewed_by) if approval.reviewed_by else None,
    )


@router.post("/approvals/{approval_id}/reject", response_model=ApprovalRead)
async def reject_proposed_action(
    request: Request,
    approval_id: UUID,
    body: RejectApprovalRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_capability(Capability.APPROVE_ACTION))],
) -> ApprovalRead:
    approval = await approval_service.get_approval(session, approval_id)
    if approval is None:
        raise AppError("Approval not found", status_code=404)

    if approval.requested_by and approval.requested_by == actor.id:
        raise AppError("self_approval_forbidden", status_code=403)

    action = await session.get(ProposedAction, approval.proposed_action_id)
    if action is None:
        raise AppError("Proposed action not found", status_code=404)

    approval = await approval_service.reject_action(
        session,
        approval=approval,
        actor=actor,
        reason=body.reason,
        request_id=getattr(request.state, "request_id", None),
    )
    await session.commit()

    incident = await require_incident(session, action.incident_id)
    return ApprovalRead(
        id=str(approval.id),
        proposed_action_id=str(action.id),
        incident_id=str(incident.id),
        incident_title=incident.title,
        incident_severity=incident.severity.value,
        action=_action_to_read(action),
        decision=approval.decision,
        reason=approval.reason,
        expires_at=approval.expires_at,
        requested_at=approval.requested_at,
        reviewed_at=approval.reviewed_at,
        reviewed_by=str(approval.reviewed_by) if approval.reviewed_by else None,
    )
