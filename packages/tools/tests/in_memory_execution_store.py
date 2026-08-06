from __future__ import annotations

import uuid
from typing import Any
from uuid import UUID


class InMemoryExecutionStore:
    def __init__(self) -> None:
        self.executions: dict[UUID, dict[str, Any]] = {}
        self.consumed: set[UUID] = set()
        self.approved: dict[UUID, dict[str, Any]] = {}

    def seed_approval(
        self,
        *,
        approval_id: UUID,
        proposed_action_id: UUID,
        parameters: dict[str, Any],
        parameters_hash: str,
        rollback_plan: str = "reverse change",
    ) -> None:
        self.approved[approval_id] = {
            "approval_id": str(approval_id),
            "proposed_action_id": str(proposed_action_id),
            "incident_id": str(uuid.uuid4()),
            "parameters_hash": parameters_hash,
            "idempotency_key": f"{approval_id}:{parameters_hash}",
            "rollback_plan": rollback_plan,
            "action_type": "rollback_deployment",
        }

    async def validate_and_prepare(
        self,
        *,
        approval_id: UUID,
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        from app.executions.hash import canonical_parameters_hash

        record = self.approved.get(approval_id)
        if record is None:
            raise PermissionError("Approval not found")
        if approval_id in self.consumed:
            raise PermissionError("Approval already consumed for execution")
        params_hash = canonical_parameters_hash(parameters)
        if params_hash != record["parameters_hash"]:
            raise PermissionError("Parameters do not match approved action")
        return dict(record)

    async def begin_execution(
        self,
        *,
        validation: dict[str, Any],
        input_payload: dict[str, Any],
    ) -> dict[str, Any]:
        key = validation["idempotency_key"]
        for existing in self.executions.values():
            if existing["idempotency_key"] == key:
                return existing
        execution_id = uuid.uuid4()
        record = {
            "execution_id": execution_id,
            "status": "running",
            "idempotency_key": key,
        }
        self.executions[execution_id] = record
        return record

    async def complete_execution(
        self,
        *,
        execution_id: UUID,
        status: str,
        output_payload: dict[str, Any] | None = None,
        error: str | None = None,
        consume_approval: bool = True,
    ) -> dict[str, Any]:
        record = self.executions[execution_id]
        record["status"] = status
        record["output_payload"] = output_payload
        record["error"] = error
        if consume_approval and status == "succeeded":
            for approval_id, approved in self.approved.items():
                if approved["idempotency_key"].startswith(str(approval_id)):
                    self.consumed.add(approval_id)
        return {"execution_id": str(execution_id), "status": status}
