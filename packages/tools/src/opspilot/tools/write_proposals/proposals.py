from __future__ import annotations

from opspilot.tools.base import RetryPolicy, RiskLevel, ToolContext, ToolRole, ToolSpec
from opspilot.tools.write_proposals.schemas import (
    ProposeFeatureFlagChangeInput,
    ProposeFeatureFlagChangeOutput,
    ProposeRollbackInput,
    ProposeRollbackOutput,
)


class ProposeRollbackTool:
    spec = ToolSpec(
        name="propose_rollback",
        version="1.0.0",
        description="Propose rolling back a deployment (does not execute).",
        input_schema=ProposeRollbackInput,
        output_schema=ProposeRollbackOutput,
        risk_level=RiskLevel.HIGH,
        required_role=ToolRole.OPERATOR,
        timeout_seconds=5.0,
        retry_policy=RetryPolicy(max_attempts=1, idempotent=True),
        is_write=False,
    )

    async def run(self, payload: ProposeRollbackInput, ctx: ToolContext) -> ProposeRollbackOutput:
        target = f"{payload.service}/{payload.deployment_id}"
        return ProposeRollbackOutput(
            target=target,
            parameters={
                "service": payload.service,
                "deployment_id": payload.deployment_id,
            },
            description=payload.description,
            expected_result=payload.expected_result,
            rollback_plan=payload.rollback_plan,
            hypothesis_ids=payload.hypothesis_ids,
            supporting_evidence=payload.supporting_evidence,
        )


class ProposeFeatureFlagChangeTool:
    spec = ToolSpec(
        name="propose_feature_flag_change",
        version="1.0.0",
        description="Propose toggling a feature flag (does not execute).",
        input_schema=ProposeFeatureFlagChangeInput,
        output_schema=ProposeFeatureFlagChangeOutput,
        risk_level=RiskLevel.MEDIUM,
        required_role=ToolRole.OPERATOR,
        timeout_seconds=5.0,
        retry_policy=RetryPolicy(max_attempts=1, idempotent=True),
        is_write=False,
    )

    async def run(
        self,
        payload: ProposeFeatureFlagChangeInput,
        ctx: ToolContext,
    ) -> ProposeFeatureFlagChangeOutput:
        target = f"{payload.service}/{payload.flag_name}"
        return ProposeFeatureFlagChangeOutput(
            target=target,
            parameters={
                "service": payload.service,
                "flag_name": payload.flag_name,
                "desired_value": payload.desired_value,
            },
            description=payload.description,
            expected_result=payload.expected_result,
            rollback_plan=payload.rollback_plan,
            hypothesis_ids=payload.hypothesis_ids,
            supporting_evidence=payload.supporting_evidence,
        )
