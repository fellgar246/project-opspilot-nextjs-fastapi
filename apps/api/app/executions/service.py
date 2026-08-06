from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.approvals.models import (
    Approval,
    ApprovalDecision,
    ProposedAction,
    ProposedActionStatus,
)
from app.audit.event_types import AuditEventType
from app.audit.service import record_audit_event
from app.events.bus import publish_event
from app.events.models import InvestigationEventType
from app.executions.hash import canonical_parameters_hash, execution_idempotency_key
from app.executions.models import ActionExecution, ExecutionStatus

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExecutionValidation:
    approval: Approval
    action: ProposedAction
    parameters_hash: str
    idempotency_key: str


class ExecutionValidationError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


async def validate_execution_request(
    session: AsyncSession,
    *,
    approval_id: uuid.UUID,
    parameters: dict[str, Any],
) -> ExecutionValidation:
    approval = await session.get(Approval, approval_id)
    if approval is None:
        raise ExecutionValidationError("not_found", "Approval not found")
    if approval.decision != ApprovalDecision.APPROVED:
        raise ExecutionValidationError("forbidden", "Approval is not approved")
    if datetime.now(UTC) > approval.expires_at:
        raise ExecutionValidationError("forbidden", "Approval has expired")
    if approval.execution_consumed:
        raise ExecutionValidationError("forbidden", "Approval already consumed for execution")

    action = await session.get(ProposedAction, approval.proposed_action_id)
    if action is None:
        raise ExecutionValidationError("not_found", "Proposed action not found")

    params_hash = canonical_parameters_hash(parameters)
    if approval.parameters_hash and params_hash != approval.parameters_hash:
        await record_audit_event(
            session,
            actor_type="agent",
            actor_id=approval.agent_run_id,
            event_type=AuditEventType.ACTION_PARAMETER_MISMATCH,
            entity_type="approval",
            entity_id=approval.id,
            payload={
                "proposed_action_id": str(action.id),
                "expected_hash": approval.parameters_hash,
                "actual_hash": params_hash,
            },
        )
        raise ExecutionValidationError("forbidden", "Parameters do not match approved action")

    idempotency_key = execution_idempotency_key(str(approval_id), params_hash)
    return ExecutionValidation(
        approval=approval,
        action=action,
        parameters_hash=params_hash,
        idempotency_key=idempotency_key,
    )


async def get_execution_by_idempotency_key(
    session: AsyncSession,
    idempotency_key: str,
) -> ActionExecution | None:
    result = await session.execute(
        select(ActionExecution).where(ActionExecution.idempotency_key == idempotency_key)
    )
    return result.scalar_one_or_none()


async def create_execution(
    session: AsyncSession,
    *,
    validation: ExecutionValidation,
    input_payload: dict[str, Any],
) -> ActionExecution:
    existing = await get_execution_by_idempotency_key(session, validation.idempotency_key)
    if existing is not None:
        return existing

    execution = ActionExecution(
        id=uuid.uuid4(),
        incident_id=validation.action.incident_id,
        proposed_action_id=validation.action.id,
        approval_id=validation.approval.id,
        execution_status=ExecutionStatus.PENDING,
        input_payload=input_payload,
        idempotency_key=validation.idempotency_key,
    )
    session.add(execution)
    await session.flush()
    await _emit_execution_event(
        session,
        execution=execution,
        event_type=InvestigationEventType.ACTION_EXECUTED,
        payload={"execution_id": str(execution.id), "status": ExecutionStatus.PENDING},
        audit_type=AuditEventType.ACTION_EXECUTED,
    )
    return execution


async def mark_execution_running(session: AsyncSession, execution: ActionExecution) -> None:
    execution.execution_status = ExecutionStatus.RUNNING
    await session.flush()
    await _emit_execution_event(
        session,
        execution=execution,
        event_type=InvestigationEventType.ACTION_EXECUTED,
        payload={"execution_id": str(execution.id), "status": ExecutionStatus.RUNNING},
        audit_type=AuditEventType.ACTION_EXECUTED,
    )


async def complete_execution(
    session: AsyncSession,
    *,
    execution: ActionExecution,
    status: ExecutionStatus,
    output_payload: dict[str, Any] | None = None,
    error: str | None = None,
    consume_approval: bool = True,
) -> ActionExecution:
    execution.execution_status = status.value
    execution.output_payload = output_payload
    execution.error = error
    execution.completed_at = datetime.now(UTC)

    action = await session.get(ProposedAction, execution.proposed_action_id)
    approval = await session.get(Approval, execution.approval_id)
    if action is not None:
        if status == ExecutionStatus.SUCCEEDED:
            action.status = ProposedActionStatus.EXECUTED
        elif status in {ExecutionStatus.FAILED, ExecutionStatus.ROLLED_BACK}:
            action.status = ProposedActionStatus.FAILED

    if consume_approval and approval is not None and status == ExecutionStatus.SUCCEEDED:
        await consume_execution_approval(session, approval)

    audit_type = (
        AuditEventType.ACTION_ROLLED_BACK
        if status == ExecutionStatus.ROLLED_BACK
        else AuditEventType.ACTION_EXECUTED
    )
    await _emit_execution_event(
        session,
        execution=execution,
        event_type=InvestigationEventType.ACTION_EXECUTED,
        payload={
            "execution_id": str(execution.id),
            "status": status.value,
            "error": error,
        },
        audit_type=audit_type,
    )
    await session.flush()
    return execution


async def consume_execution_approval(session: AsyncSession, approval: Approval) -> bool:
    result = await session.execute(
        update(Approval)
        .where(
            Approval.id == approval.id,
            Approval.execution_consumed.is_(False),
            Approval.decision == ApprovalDecision.APPROVED,
        )
        .values(execution_consumed=True)
    )
    if cast(CursorResult[Any], result).rowcount == 0:
        return False
    approval.execution_consumed = True
    return True


async def list_executions_for_incident(
    session: AsyncSession,
    incident_id: uuid.UUID,
) -> list[ActionExecution]:
    result = await session.execute(
        select(ActionExecution)
        .where(ActionExecution.incident_id == incident_id)
        .order_by(ActionExecution.started_at.desc())
    )
    return list(result.scalars().all())


async def _emit_execution_event(
    session: AsyncSession,
    *,
    execution: ActionExecution,
    event_type: InvestigationEventType,
    payload: dict[str, Any],
    audit_type: AuditEventType,
) -> None:
    agent_run_id = None
    approval = await session.get(Approval, execution.approval_id)
    if approval is not None:
        agent_run_id = approval.agent_run_id
    await publish_event(
        session,
        incident_id=execution.incident_id,
        agent_run_id=agent_run_id,
        event_type=event_type,
        payload=payload,
    )
    await record_audit_event(
        session,
        actor_type="agent",
        actor_id=agent_run_id or execution.id,
        event_type=audit_type,
        entity_type="action_execution",
        entity_id=execution.id,
        payload={
            "incident_id": str(execution.incident_id),
            "proposed_action_id": str(execution.proposed_action_id),
            **payload,
        },
    )
