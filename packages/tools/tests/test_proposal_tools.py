from __future__ import annotations

import pytest
from opspilot.tools.bootstrap import build_default_registry
from opspilot.tools.base import ToolContext, ToolRole
from opspilot.tools.write_proposals.schemas import ProposeRollbackInput


@pytest.mark.asyncio
async def test_propose_rollback_is_not_write() -> None:
    registry = build_default_registry()
    tool = registry.require("propose_rollback")
    assert tool.spec.is_write is False

    ctx = ToolContext(
        incident_id=__import__("uuid").uuid4(),
        actor_type="agent",
        actor_id=__import__("uuid").uuid4(),
        role=ToolRole.OPERATOR,
        request_id="req-1",
    )
    output = await tool.run(
        ProposeRollbackInput(
            service="checkout",
            deployment_id="deploy-1",
            hypothesis_ids=["hyp-1"],
            supporting_evidence=["ev-1"],
            expected_result="Errors drop",
            rollback_plan="Redeploy previous version",
        ),
        ctx,
    )
    assert output.action_type == "rollback_deployment"
    assert output.target == "checkout/deploy-1"


@pytest.mark.asyncio
async def test_propose_feature_flag_is_not_write() -> None:
    registry = build_default_registry()
    tool = registry.require("propose_feature_flag_change")
    assert tool.spec.is_write is False
