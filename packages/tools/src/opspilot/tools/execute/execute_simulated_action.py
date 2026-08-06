from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from opspilot.tools.adapters.simulator_api import SimulatorApiAdapter
from opspilot.tools.base import RetryPolicy, RiskLevel, ToolContext, ToolRole, ToolSpec
from opspilot.tools.execute.protocol import ExecutionStore
from opspilot.tools.execute.schemas import ExecuteSimulatedActionInput, ExecuteSimulatedActionOutput


def assert_simulator_url(base_url: str) -> None:
    parsed = urlparse(base_url.rstrip("/"))
    host = (parsed.hostname or "").lower()
    if host not in {"127.0.0.1", "localhost", "demo-service", "simulator"}:
        raise ValueError(f"Write actions may only target the simulator, got host: {host}")


class ExecuteSimulatedActionTool:
    spec = ToolSpec(
        name="execute_simulated_action",
        version="1.0.0",
        description="Execute an approved mitigation action against the simulator only.",
        input_schema=ExecuteSimulatedActionInput,
        output_schema=ExecuteSimulatedActionOutput,
        risk_level=RiskLevel.HIGH,
        required_role=ToolRole.APPROVER,
        timeout_seconds=30.0,
        retry_policy=RetryPolicy(max_attempts=1, idempotent=True),
        is_write=True,
    )

    def __init__(
        self,
        simulator: SimulatorApiAdapter,
        execution_store: ExecutionStore,
        *,
        internal_auth_token: str = "sim-internal-dev-token",
    ) -> None:
        self.simulator = simulator
        self.execution_store = execution_store
        self.internal_auth_token = internal_auth_token
        assert_simulator_url(simulator.base_url)

    async def run(
        self,
        payload: ExecuteSimulatedActionInput,
        ctx: ToolContext,
    ) -> ExecuteSimulatedActionOutput:
        if ctx.approval_id is None or ctx.approval_id != payload.approval_id:
            raise PermissionError("Write tool requires matching approval_id in context")

        validation = await self.execution_store.validate_and_prepare(
            approval_id=payload.approval_id,
            parameters=payload.parameters,
        )
        if validation.get("proposed_action_id") != str(payload.proposed_action_id):
            raise PermissionError("proposed_action_id does not match approval")

        execution = await self.execution_store.begin_execution(
            validation=validation,
            input_payload=payload.model_dump(mode="json"),
        )
        execution_id = execution["execution_id"]

        try:
            result = await self._apply_action(payload)
            completed = await self.execution_store.complete_execution(
                execution_id=execution_id,
                status="succeeded",
                output_payload=result,
                consume_approval=True,
            )
            return ExecuteSimulatedActionOutput(
                execution_id=execution_id,
                action_type=payload.action_type,
                status=completed.get("status", "succeeded"),
                result=result,
            )
        except Exception as exc:
            rollback_result: dict[str, Any] | None = None
            rolled_back = False
            try:
                rollback_result = await self._apply_rollback(payload, validation)
                rolled_back = True
                status = "rolled_back"
            except Exception:
                status = "failed"

            await self.execution_store.complete_execution(
                execution_id=execution_id,
                status=status,
                output_payload=rollback_result,
                error=str(exc),
                consume_approval=False,
            )
            return ExecuteSimulatedActionOutput(
                execution_id=execution_id,
                action_type=payload.action_type,
                status=status,
                result=rollback_result or {},
                rolled_back=rolled_back,
            )

    async def _apply_action(self, payload: ExecuteSimulatedActionInput) -> dict[str, Any]:
        params = payload.parameters
        if payload.action_type == "rollback_deployment":
            deployment_id = str(params.get("deployment_id", "latest"))
            return await self.simulator.rollback_deployment(
                deployment_id,
                auth_token=self.internal_auth_token,
            )
        if payload.action_type == "toggle_feature_flag":
            return await self.simulator.mutate_feature_flag(
                str(params.get("flag_name", "")),
                enabled=bool(params.get("desired_value", False)),
                auth_token=self.internal_auth_token,
            )
        raise ValueError(f"Unsupported action_type: {payload.action_type}")

    async def _apply_rollback(
        self,
        payload: ExecuteSimulatedActionInput,
        validation: dict[str, Any],
    ) -> dict[str, Any]:
        rollback_plan = validation.get("rollback_plan", "")
        if payload.action_type == "toggle_feature_flag":
            current = payload.parameters.get("desired_value")
            return await self.simulator.mutate_feature_flag(
                str(payload.parameters.get("flag_name", "")),
                enabled=not bool(current),
                auth_token=self.internal_auth_token,
            )
        if "re-enable" in rollback_plan.lower() or "flag" in rollback_plan.lower():
            flag_name = payload.parameters.get("flag_name", "incident_mitigation_mode")
            return await self.simulator.mutate_feature_flag(
                str(flag_name),
                enabled=True,
                auth_token=self.internal_auth_token,
            )
        return {"rollback_plan": rollback_plan, "applied": False}
