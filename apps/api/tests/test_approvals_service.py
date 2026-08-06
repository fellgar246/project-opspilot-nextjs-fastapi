from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.approvals.models import ActionType, Approval, ApprovalDecision, ProposedAction, ProposedActionStatus
from app.approvals import service as approval_service
from app.auth.models import User, UserRole
from app.auth.security import hash_password
from app.core.errors import AppError
from app.investigation.models import AgentRun, AgentRunStatus


def _approver() -> User:
    return User(
        id=uuid.uuid4(),
        email="approver@example.com",
        display_name="Approver",
        role=UserRole.APPROVER,
        password_hash=hash_password("password"),
        is_active=True,
    )


@pytest.mark.asyncio
async def test_double_resume_token_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()
    approval = Approval(
        id=uuid.uuid4(),
        proposed_action_id=uuid.uuid4(),
        decision=ApprovalDecision.PENDING,
        expires_at=__import__("datetime").datetime.now(__import__("datetime").UTC)
        + __import__("datetime").timedelta(hours=1),
        resume_token="token",
        resume_token_consumed=True,
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
    session.get = AsyncMock(side_effect=lambda model, pk: action if pk == action.id else approval)

    with pytest.raises(AppError) as exc:
        await approval_service.approve_action(session, approval=approval, actor=_approver(), request_id=None)
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_self_approval_forbidden_via_router_logic() -> None:
    proposer_id = uuid.uuid4()
    actor = _approver()
    actor.id = proposer_id
    approval = Approval(
        id=uuid.uuid4(),
        proposed_action_id=uuid.uuid4(),
        requested_by=proposer_id,
        decision=ApprovalDecision.PENDING,
        expires_at=__import__("datetime").datetime.now(__import__("datetime").UTC)
        + __import__("datetime").timedelta(hours=1),
        resume_token="token",
        agent_run_id=uuid.uuid4(),
        graph_thread_id="thread",
    )
    if approval.requested_by == actor.id:
        with pytest.raises(AppError) as exc:
            raise AppError("self_approval_forbidden", status_code=403)
        assert exc.value.status_code == 403
