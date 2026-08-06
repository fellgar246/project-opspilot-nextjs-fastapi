from __future__ import annotations

from typing import Any, Protocol, runtime_checkable
from uuid import UUID


@runtime_checkable
class ApprovalStore(Protocol):
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
    ) -> UUID: ...

    async def create_pending_approval(
        self,
        *,
        proposed_action_id: UUID,
        agent_run_id: UUID,
        graph_thread_id: str,
    ) -> tuple[UUID, str]: ...


@runtime_checkable
class InvestigationEventPublisher(Protocol):
    async def publish(self, event_type: str, payload: dict[str, Any]) -> None: ...
