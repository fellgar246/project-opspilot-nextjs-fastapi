from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from opspilot.agent.nodes.base import as_uuid
from opspilot.agent.state.graph_state import IncidentInvestigationState
from opspilot.tools.base import ToolContext, ToolRole
from opspilot.tools.gateway import ToolGateway


def make_execute_approved_action_node(
    gateway: ToolGateway,
) -> Callable[[IncidentInvestigationState], Awaitable[dict[str, Any]]]:
    async def execute_approved_action(state: IncidentInvestigationState) -> dict[str, Any]:
        decision = state.get("approval_decision") or {}
        if decision.get("decision") != "approved":
            return {
                "current_node": "execute_approved_action",
                "completed_nodes": ["execute_approved_action"],
                "errors": ["Cannot execute without approved decision"],
            }

        proposal = state.get("proposal") or {}
        pending_action_id = state.get("pending_action_id")
        approval_id = decision.get("approval_id")
        if not pending_action_id or not approval_id:
            return {
                "current_node": "execute_approved_action",
                "completed_nodes": ["execute_approved_action"],
                "errors": ["Missing pending action or approval id"],
            }

        action_type = proposal.get("action_type", "rollback_deployment")
        parameters = proposal.get("parameters") or {}

        ctx = ToolContext(
            incident_id=as_uuid(state["incident_id"]),
            agent_run_id=as_uuid(state["agent_run_id"]),
            actor_type="agent",
            actor_id=as_uuid(state["agent_run_id"]),
            role=ToolRole.APPROVER,
            request_id=state["graph_thread_id"],
            approval_id=UUID(str(approval_id)),
        )
        payload = {
            "approval_id": str(approval_id),
            "proposed_action_id": pending_action_id,
            "action_type": action_type,
            "parameters": parameters,
        }
        result = await gateway.invoke(
            "execute_simulated_action",
            payload,
            ctx,
            collect_evidence=False,
        )

        if result.status != "ok" or result.data is None:
            error_msg = result.error.message if result.error else result.status
            return {
                "current_node": "execute_approved_action",
                "completed_nodes": ["execute_approved_action"],
                "execution_status": "failed",
                "errors": [f"Execution failed: {error_msg}"],
                "investigation_status": "running",
            }

        output = result.data.model_dump()
        exec_status = output.get("status", "succeeded")
        updates: dict[str, Any] = {
            "current_node": "execute_approved_action",
            "completed_nodes": ["execute_approved_action"],
            "execution_id": str(output.get("execution_id")),
            "execution_status": exec_status,
            "execution_result": output.get("result") or {},
        }
        if exec_status in {"failed", "rolled_back"}:
            updates["errors"] = [f"Execution ended with status {exec_status}"]
            updates["investigation_status"] = "running"
            updates["proposal_attempts"] = state.get("proposal_attempts", 0) + 1
            updates["pending_action_id"] = None
            updates["proposal"] = None
        else:
            updates["investigation_status"] = "verifying_recovery"
        return updates

    return execute_approved_action
