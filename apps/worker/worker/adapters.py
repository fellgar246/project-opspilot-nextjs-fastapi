from __future__ import annotations

import uuid
from typing import Any
from uuid import UUID

from app.approvals import service as approval_service
from app.investigation.models import AgentRun
from sqlalchemy.ext.asyncio import AsyncSession


class SqlApprovalStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_proposed_action(
        self,
        *,
        incident_id: UUID,
        agent_run_id: UUID,
        action_type: str,
        description: str,
        target: str,
        parameters: dict[str, Any],
        expected_result: str,
        rollback_plan: str,
        hypothesis_ids: list[UUID],
        supporting_evidence: list[UUID],
        hypothesis_confidence: float,
    ) -> UUID:
        action = await approval_service.create_proposed_action(
            self.session,
            incident_id=incident_id,
            agent_run_id=agent_run_id,
            action_type=action_type,
            description=description,
            target=target,
            parameters=parameters,
            expected_result=expected_result,
            rollback_plan=rollback_plan,
            hypothesis_ids=hypothesis_ids,
            supporting_evidence=supporting_evidence,
            hypothesis_confidence=hypothesis_confidence,
        )
        return action.id

    async def create_pending_approval(
        self,
        *,
        proposed_action_id: UUID,
        agent_run_id: UUID,
        graph_thread_id: str,
    ) -> tuple[UUID, str]:
        agent_run = await self.session.get(AgentRun, agent_run_id)
        if agent_run is None:
            raise RuntimeError("Agent run not found")
        from app.approvals.models import ProposedAction

        action = await self.session.get(ProposedAction, proposed_action_id)
        if action is None:
            raise RuntimeError("Proposed action not found")
        approval = await approval_service.create_pending_approval(
            self.session,
            proposed_action=action,
            agent_run=agent_run,
            requested_by=action.requested_by,
        )
        return approval.id, approval.resume_token


class WorkerEventPublisher:
    def __init__(
        self,
        session: AsyncSession,
        *,
        incident_id: uuid.UUID,
        agent_run_id: uuid.UUID,
    ) -> None:
        self.session = session
        self.incident_id = incident_id
        self.agent_run_id = agent_run_id

    async def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        from app.events.bus import publish_event
        from app.events.models import InvestigationEventType

        try:
            enum_type = InvestigationEventType(event_type)
        except ValueError:
            enum_type = event_type
        await publish_event(
            self.session,
            incident_id=self.incident_id,
            agent_run_id=self.agent_run_id,
            event_type=enum_type,
            payload=payload,
        )
