from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from app.approvals import service as approval_service
from app.approvals.models import (
    ActionType,
    Approval,
    ApprovalDecision,
    ProposedAction,
    ProposedActionStatus,
)
from app.investigation.models import AgentRun, AgentRunStatus


@pytest.mark.asyncio
async def test_expire_approval_resumes_with_expired_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()
    approval = Approval(
        id=uuid.uuid4(),
        proposed_action_id=uuid.uuid4(),
        decision=ApprovalDecision.PENDING,
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
        resume_token="token",
        resume_token_consumed=False,
        agent_run_id=uuid.uuid4(),
        graph_thread_id="thread",
    )
    action = ProposedAction(
        id=approval.proposed_action_id,
        incident_id=uuid.uuid4(),
        agent_run_id=approval.agent_run_id,
        action_type=ActionType.ROLLBACK_DEPLOYMENT.value,
        description="Rollback",
        target="svc/deploy",
        parameters={},
        risk_level="high",
        risk_rationale="rollback",
        expected_result="stable",
        rollback_plan="redeploy",
        supporting_evidence=[uuid.uuid4()],
        hypothesis_ids=[uuid.uuid4()],
    )
    agent_run = AgentRun(
        id=approval.agent_run_id,
        incident_id=action.incident_id,
        graph_thread_id="thread",
        status=AgentRunStatus.AWAITING_APPROVAL,
        model="mock-v1",
        prompt_version="v1",
    )

    session.get = AsyncMock(
        side_effect=lambda model, pk: {
            action.id: action,
            agent_run.id: agent_run,
        }.get(pk)
    )
    monkeypatch.setattr(approval_service, "publish_event", AsyncMock())
    monkeypatch.setattr(approval_service, "_enqueue_resume", AsyncMock())

    expired = await approval_service.expire_approval(session, approval)

    assert expired is True
    assert approval.decision == ApprovalDecision.EXPIRED
    assert action.status == ProposedActionStatus.CANCELLED
    assert agent_run.status == AgentRunStatus.RUNNING
    approval_service._enqueue_resume.assert_awaited_once()
    resume_args = approval_service._enqueue_resume.await_args
    assert resume_args.args[1]["decision"] == "expired"
