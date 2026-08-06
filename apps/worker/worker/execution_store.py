from __future__ import annotations

import uuid
from typing import Any
from uuid import UUID

from app.approvals.models import Approval
from app.executions import service as execution_service
from app.executions.models import ExecutionStatus
from opspilot.tools.execute.protocol import ExecutionStore
from sqlalchemy.ext.asyncio import AsyncSession


class SqlExecutionStore(ExecutionStore):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def validate_and_prepare(
        self,
        *,
        approval_id: UUID,
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            validation = await execution_service.validate_execution_request(
                self.session,
                approval_id=approval_id,
                parameters=parameters,
            )
        except execution_service.ExecutionValidationError as exc:
            raise PermissionError(exc.message) from exc

        return {
            "approval_id": str(validation.approval.id),
            "proposed_action_id": str(validation.action.id),
            "incident_id": str(validation.action.incident_id),
            "parameters_hash": validation.parameters_hash,
            "idempotency_key": validation.idempotency_key,
            "rollback_plan": validation.action.rollback_plan,
            "action_type": validation.action.action_type,
        }

    async def begin_execution(
        self,
        *,
        validation: dict[str, Any],
        input_payload: dict[str, Any],
    ) -> dict[str, Any]:
        approval = await self.session.get(Approval, uuid.UUID(validation["approval_id"]))
        if approval is None:
            raise RuntimeError("Approval not found")

        from app.approvals.models import ProposedAction

        action = await self.session.get(ProposedAction, uuid.UUID(validation["proposed_action_id"]))
        if action is None:
            raise RuntimeError("Proposed action not found")

        exec_validation = await execution_service.validate_execution_request(
            self.session,
            approval_id=approval.id,
            parameters=input_payload.get("parameters", {}),
        )
        execution = await execution_service.create_execution(
            self.session,
            validation=exec_validation,
            input_payload=input_payload,
        )
        if execution.execution_status == ExecutionStatus.PENDING:
            await execution_service.mark_execution_running(self.session, execution)
        return {
            "execution_id": execution.id,
            "status": execution.execution_status,
            "idempotency_key": execution.idempotency_key,
        }

    async def complete_execution(
        self,
        *,
        execution_id: UUID,
        status: str,
        output_payload: dict[str, Any] | None = None,
        error: str | None = None,
        consume_approval: bool = True,
    ) -> dict[str, Any]:
        from app.executions.models import ActionExecution

        execution = await self.session.get(ActionExecution, execution_id)
        if execution is None:
            raise RuntimeError("Execution not found")
        if execution.execution_status in {
            ExecutionStatus.SUCCEEDED,
            ExecutionStatus.FAILED,
            ExecutionStatus.ROLLED_BACK,
        }:
            return {
                "execution_id": str(execution.id),
                "status": execution.execution_status,
            }

        exec_status = ExecutionStatus(status)
        updated = await execution_service.complete_execution(
            self.session,
            execution=execution,
            status=exec_status,
            output_payload=output_payload,
            error=error,
            consume_approval=consume_approval,
        )
        return {
            "execution_id": str(updated.id),
            "status": updated.execution_status,
        }
