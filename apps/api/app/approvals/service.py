from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from arq import create_pool
from arq.connections import RedisSettings
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.approvals.models import (
    ALLOWED_ACTION_TYPES,
    ActionType,
    Approval,
    ApprovalDecision,
    ProposedAction,
    ProposedActionStatus,
    RiskLevel,
)
from app.approvals.risk import assess_risk
from app.audit.event_types import AuditEventType
from app.audit.service import record_audit_event
from app.auth.models import User
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.events.bus import publish_event
from app.events.models import InvestigationEventType
from app.incidents.models import Hypothesis, Incident
from app.investigation.models import AgentRun, AgentRunStatus


class ProposalValidationError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=422)


def _validate_proposal_fields(
    *,
    action_type: str,
    rollback_plan: str,
    hypothesis_ids: list[uuid.UUID],
    supporting_evidence: list[uuid.UUID],
) -> ActionType:
    try:
        parsed = ActionType(action_type)
    except ValueError as exc:
        raise ProposalValidationError(f"Unsupported action_type: {action_type}") from exc
    if parsed not in ALLOWED_ACTION_TYPES:
        raise ProposalValidationError(f"Unsupported action_type: {action_type}")
    if not rollback_plan.strip():
        raise ProposalValidationError("rollback_plan is required")
    if not hypothesis_ids:
        raise ProposalValidationError("At least one hypothesis reference is required")
    if not supporting_evidence:
        raise ProposalValidationError("At least one supporting evidence reference is required")
    return parsed


async def create_proposed_action(
    session: AsyncSession,
    *,
    incident_id: uuid.UUID,
    agent_run_id: uuid.UUID,
    action_type: str,
    description: str,
    target: str,
    parameters: dict[str, Any],
    expected_result: str,
    rollback_plan: str,
    hypothesis_ids: list[uuid.UUID],
    supporting_evidence: list[uuid.UUID],
    hypothesis_confidence: float,
    environment: str = "production",
    requested_by: uuid.UUID | None = None,
) -> ProposedAction:
    parsed_type = _validate_proposal_fields(
        action_type=action_type,
        rollback_plan=rollback_plan,
        hypothesis_ids=hypothesis_ids,
        supporting_evidence=supporting_evidence,
    )
    risk_level, risk_rationale = assess_risk(
        action_type=parsed_type,
        target=target,
        environment=environment,
        hypothesis_confidence=hypothesis_confidence,
        rollback_plan=rollback_plan,
    )
    if risk_level == RiskLevel.CRITICAL:
        raise ProposalValidationError(risk_rationale)

    action = ProposedAction(
        id=uuid.uuid4(),
        incident_id=incident_id,
        agent_run_id=agent_run_id,
        action_type=parsed_type.value,
        description=description,
        target=target,
        parameters=parameters,
        risk_level=risk_level.value,
        risk_rationale=risk_rationale,
        expected_result=expected_result,
        rollback_plan=rollback_plan,
        supporting_evidence=supporting_evidence,
        hypothesis_ids=hypothesis_ids,
        status=ProposedActionStatus.PENDING,
        requested_by=requested_by,
    )
    session.add(action)
    await session.flush()

    await publish_event(
        session,
        incident_id=incident_id,
        agent_run_id=agent_run_id,
        event_type=InvestigationEventType.ACTION_PROPOSED,
        payload={
            "proposed_action_id": str(action.id),
            "action_type": action.action_type,
            "target": action.target,
            "risk_level": action.risk_level,
        },
    )
    await record_audit_event(
        session,
        actor_type="agent",
        actor_id=agent_run_id,
        event_type=AuditEventType.ACTION_PROPOSED,
        entity_type="proposed_action",
        entity_id=action.id,
        payload={
            "incident_id": str(incident_id),
            "action_type": action.action_type,
            "risk_level": action.risk_level,
        },
    )
    return action


async def create_pending_approval(
    session: AsyncSession,
    *,
    proposed_action: ProposedAction,
    agent_run: AgentRun,
    requested_by: uuid.UUID | None,
) -> Approval:
    settings = get_settings()
    if proposed_action.risk_level not in {RiskLevel.MEDIUM.value, RiskLevel.HIGH.value}:
        raise AppError("Approval not required for this risk level", status_code=409)

    approval = Approval(
        id=uuid.uuid4(),
        proposed_action_id=proposed_action.id,
        requested_by=requested_by,
        decision=ApprovalDecision.PENDING,
        expires_at=datetime.now(UTC) + timedelta(minutes=settings.approval_expiration_minutes),
        resume_token=secrets.token_urlsafe(32),
        agent_run_id=agent_run.id,
        graph_thread_id=agent_run.graph_thread_id,
    )
    session.add(approval)
    agent_run.status = AgentRunStatus.AWAITING_APPROVAL
    await session.flush()

    await publish_event(
        session,
        incident_id=proposed_action.incident_id,
        agent_run_id=agent_run.id,
        event_type=InvestigationEventType.APPROVAL_REQUESTED,
        payload={
            "approval_id": str(approval.id),
            "proposed_action_id": str(proposed_action.id),
            "risk_level": proposed_action.risk_level,
            "expires_at": approval.expires_at.isoformat(),
        },
    )
    await record_audit_event(
        session,
        actor_type="agent",
        actor_id=agent_run.id,
        event_type=AuditEventType.APPROVAL_REQUESTED,
        entity_type="approval",
        entity_id=approval.id,
        payload={
            "proposed_action_id": str(proposed_action.id),
            "incident_id": str(proposed_action.incident_id),
        },
    )
    return approval


async def consume_resume_token(session: AsyncSession, approval: Approval) -> bool:
    """Atomically consume resume token; returns False if already consumed."""
    if approval.resume_token_consumed:
        return False
    approval.resume_token_consumed = True
    await session.flush()
    return True


async def approve_action(
    session: AsyncSession,
    *,
    approval: Approval,
    actor: User,
    request_id: str | None,
) -> Approval:
    if approval.decision != ApprovalDecision.PENDING:
        raise AppError("Approval already decided", status_code=409)
    if approval.requested_by and approval.requested_by == actor.id:
        raise AppError("self_approval_forbidden", status_code=403)
    if datetime.now(UTC) > approval.expires_at:
        raise AppError("Approval has expired", status_code=409)

    action = await session.get(ProposedAction, approval.proposed_action_id)
    if action is None:
        raise AppError("Proposed action not found", status_code=404)

    if not await consume_resume_token(session, approval):
        raise AppError("Graph already resumed for this approval", status_code=409)

    approval.decision = ApprovalDecision.APPROVED
    approval.reviewed_by = actor.id
    approval.reviewed_at = datetime.now(UTC)
    action.status = ProposedActionStatus.APPROVED

    agent_run = await session.get(AgentRun, approval.agent_run_id)
    if agent_run:
        agent_run.status = AgentRunStatus.RUNNING

    await publish_event(
        session,
        incident_id=action.incident_id,
        agent_run_id=approval.agent_run_id,
        event_type=InvestigationEventType.APPROVAL_DECIDED,
        payload={"approval_id": str(approval.id), "decision": "approved"},
    )
    await publish_event(
        session,
        incident_id=action.incident_id,
        agent_run_id=approval.agent_run_id,
        event_type=InvestigationEventType.RUN_RESUMED,
        payload={"approval_id": str(approval.id), "branch": "approved"},
    )
    await record_audit_event(
        session,
        actor_type="user",
        actor_id=actor.id,
        event_type=AuditEventType.APPROVAL_GRANTED,
        entity_type="approval",
        entity_id=approval.id,
        payload={"proposed_action_id": str(action.id), "reason": None},
        request_id=request_id,
    )

    await _enqueue_resume(approval.id, {"decision": "approved"}, get_settings())
    return approval


async def reject_action(
    session: AsyncSession,
    *,
    approval: Approval,
    actor: User,
    reason: str,
    request_id: str | None,
) -> Approval:
    if approval.decision != ApprovalDecision.PENDING:
        raise AppError("Approval already decided", status_code=409)
    if approval.requested_by and approval.requested_by == actor.id:
        raise AppError("self_approval_forbidden", status_code=403)

    action = await session.get(ProposedAction, approval.proposed_action_id)
    if action is None:
        raise AppError("Proposed action not found", status_code=404)

    if not await consume_resume_token(session, approval):
        raise AppError("Graph already resumed for this approval", status_code=409)

    approval.decision = ApprovalDecision.REJECTED
    approval.reviewed_by = actor.id
    approval.reviewed_at = datetime.now(UTC)
    approval.reason = reason
    action.status = ProposedActionStatus.REJECTED

    agent_run = await session.get(AgentRun, approval.agent_run_id)
    if agent_run:
        agent_run.status = AgentRunStatus.RUNNING

    await publish_event(
        session,
        incident_id=action.incident_id,
        agent_run_id=approval.agent_run_id,
        event_type=InvestigationEventType.APPROVAL_DECIDED,
        payload={"approval_id": str(approval.id), "decision": "rejected", "reason": reason},
    )
    await publish_event(
        session,
        incident_id=action.incident_id,
        agent_run_id=approval.agent_run_id,
        event_type=InvestigationEventType.RUN_RESUMED,
        payload={"approval_id": str(approval.id), "branch": "rejected"},
    )
    await record_audit_event(
        session,
        actor_type="user",
        actor_id=actor.id,
        event_type=AuditEventType.APPROVAL_REJECTED,
        entity_type="approval",
        entity_id=approval.id,
        payload={"proposed_action_id": str(action.id), "reason": reason},
        request_id=request_id,
    )

    await _enqueue_resume(approval.id, {"decision": "rejected", "reason": reason}, get_settings())
    return approval


async def expire_approval(session: AsyncSession, approval: Approval) -> bool:
    if approval.decision != ApprovalDecision.PENDING:
        return False
    if datetime.now(UTC) <= approval.expires_at:
        return False
    if approval.resume_token_consumed:
        return False

    action = await session.get(ProposedAction, approval.proposed_action_id)
    if action is None:
        return False

    approval.resume_token_consumed = True
    approval.decision = ApprovalDecision.EXPIRED
    approval.reason = "Approval expired without decision"
    action.status = ProposedActionStatus.CANCELLED

    agent_run = await session.get(AgentRun, approval.agent_run_id)
    if agent_run:
        agent_run.status = AgentRunStatus.RUNNING

    await publish_event(
        session,
        incident_id=action.incident_id,
        agent_run_id=approval.agent_run_id,
        event_type=InvestigationEventType.APPROVAL_DECIDED,
        payload={"approval_id": str(approval.id), "decision": "expired"},
    )
    await publish_event(
        session,
        incident_id=action.incident_id,
        agent_run_id=approval.agent_run_id,
        event_type=InvestigationEventType.RUN_RESUMED,
        payload={"approval_id": str(approval.id), "branch": "expired"},
    )

    await _enqueue_resume(
        approval.id,
        {"decision": "expired", "reason": "Approval expired without decision"},
        get_settings(),
    )
    return True


async def list_pending_approvals(
    session: AsyncSession,
) -> list[tuple[Approval, ProposedAction, Incident]]:
    result = await session.execute(
        select(Approval, ProposedAction, Incident)
        .join(ProposedAction, Approval.proposed_action_id == ProposedAction.id)
        .join(Incident, ProposedAction.incident_id == Incident.id)
        .where(Approval.decision == ApprovalDecision.PENDING)
        .order_by(Incident.severity.asc(), Approval.requested_at.asc())
    )
    return list(result.all())


async def list_proposed_actions_for_incident(
    session: AsyncSession,
    incident_id: uuid.UUID,
) -> list[ProposedAction]:
    result = await session.execute(
        select(ProposedAction)
        .where(ProposedAction.incident_id == incident_id)
        .order_by(ProposedAction.created_at.desc())
    )
    return list(result.scalars().all())


async def get_approval(session: AsyncSession, approval_id: uuid.UUID) -> Approval | None:
    return await session.get(Approval, approval_id)


async def get_hypothesis_confidence(
    session: AsyncSession,
    hypothesis_ids: list[uuid.UUID],
) -> float:
    if not hypothesis_ids:
        return 0.0
    result = await session.execute(select(Hypothesis).where(Hypothesis.id.in_(hypothesis_ids)))
    hypotheses = list(result.scalars().all())
    if not hypotheses:
        return 0.0
    return max(item.confidence for item in hypotheses)


async def _enqueue_resume(
    approval_id: uuid.UUID, resume_value: dict[str, Any], settings: Settings
) -> None:
    redis_settings = RedisSettings.from_dsn(str(settings.redis_url))
    pool = await create_pool(redis_settings)
    try:
        await pool.enqueue_job("resume_investigation", str(approval_id), resume_value)
    finally:
        await pool.aclose()
