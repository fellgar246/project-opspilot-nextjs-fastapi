from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from langgraph.types import interrupt
from opspilot.agent.approvals.protocol import ApprovalStore
from opspilot.agent.nodes.base import as_uuid
from opspilot.agent.state.graph_state import IncidentInvestigationState
from opspilot.agent.state.schema import HypothesisDraft
from opspilot.tools.base import ToolContext, ToolRole
from opspilot.tools.gateway import ToolGateway


def _top_hypothesis(state: IncidentInvestigationState) -> HypothesisDraft | None:
    hypotheses = [
        item for item in (state.get("hypotheses") or []) if item.get("status") != "rejected"
    ]
    if not hypotheses:
        return None
    return max(hypotheses, key=lambda item: item.get("confidence", 0.0))


def make_propose_mitigation_node(
    gateway: ToolGateway,
    store: ApprovalStore | None = None,
) -> Callable[[IncidentInvestigationState], Awaitable[dict[str, Any]]]:
    async def propose_mitigation(state: IncidentInvestigationState) -> dict[str, Any]:
        hypothesis = _top_hypothesis(state)
        if hypothesis is None:
            return {
                "current_node": "propose_mitigation",
                "completed_nodes": ["propose_mitigation"],
                "errors": ["No hypothesis available for mitigation proposal"],
            }

        service = (
            state.get("affected_services") or state.get("service_names") or ["demo-service"]
        )[0]
        evidence_ids = hypothesis.get("supporting_evidence") or []
        if not evidence_ids:
            evidence_ids = [ref["evidence_id"] for ref in (state.get("evidence_refs") or [])[:1]]
        if not evidence_ids:
            return {
                "current_node": "propose_mitigation",
                "completed_nodes": ["propose_mitigation"],
                "errors": ["Cannot propose mitigation without supporting evidence"],
            }

        ctx = ToolContext(
            incident_id=as_uuid(state["incident_id"]),
            agent_run_id=as_uuid(state["agent_run_id"]),
            actor_type="agent",
            actor_id=as_uuid(state["agent_run_id"]),
            role=ToolRole.OPERATOR,
            request_id=state["graph_thread_id"],
        )
        tool_payload: dict[str, Any] = {
            "service": service,
            "deployment_id": "latest",
            "hypothesis_ids": [str(hypothesis.get("id", "draft"))],
            "supporting_evidence": evidence_ids,
            "expected_result": "Error rate returns to baseline within 5 minutes",
            "rollback_plan": f"Re-deploy previous stable version of {service}",
            "description": (
                f"Mitigate incident based on hypothesis: {hypothesis['statement'][:120]}"
            ),
        }
        tool_name = "propose_rollback"
        attempts = state.get("proposal_attempts", 0)
        if attempts >= 1:
            tool_name = "propose_feature_flag_change"
            tool_payload = {
                "service": service,
                "flag_name": "incident_mitigation_mode",
                "desired_value": False,
                "hypothesis_ids": [str(hypothesis.get("id", "draft"))],
                "supporting_evidence": evidence_ids,
                "expected_result": "Mitigation flag disabled to reduce blast radius",
                "rollback_plan": f"Re-enable feature flag {service}/incident_mitigation_mode",
                "description": (
                    f"Alternative mitigation after rejection: {hypothesis['statement'][:120]}"
                ),
            }
        result = await gateway.invoke(tool_name, tool_payload, ctx, collect_evidence=False)
        if result.status != "ok" or result.data is None:
            error_msg = result.error.message if result.error else result.status
            return {
                "current_node": "propose_mitigation",
                "completed_nodes": ["propose_mitigation"],
                "errors": [f"Proposal tool failed: {error_msg}"],
            }

        output = result.data.model_dump()
        pending_action_id: str | None = None
        if store is not None:
            action_id = await store.create_proposed_action(
                incident_id=as_uuid(state["incident_id"]),
                agent_run_id=as_uuid(state["agent_run_id"]),
                action_type=output["action_type"],
                description=output["description"],
                target=output["target"],
                parameters=output["parameters"],
                expected_result=output["expected_result"],
                rollback_plan=output["rollback_plan"],
                hypothesis_ids=[as_uuid(item) for item in output["hypothesis_ids"]],
                supporting_evidence=[as_uuid(item) for item in output["supporting_evidence"]],
                hypothesis_confidence=float(hypothesis.get("confidence", 0.0)),
            )
            pending_action_id = str(action_id)

        return {
            "current_node": "propose_mitigation",
            "completed_nodes": ["propose_mitigation"],
            "pending_action_id": pending_action_id,
            "proposal": output,
            "proposal_confidence": float(hypothesis.get("confidence", 0.0)),
        }

    return propose_mitigation


def make_risk_assessment_node() -> Callable[
    [IncidentInvestigationState], Awaitable[dict[str, Any]]
]:
    async def risk_assessment(state: IncidentInvestigationState) -> dict[str, Any]:
        proposal = state.get("proposal") or {}
        risk_level = proposal.get("risk_level")
        if risk_level is None and state.get("pending_action_id"):
            risk_level = "medium"
        if proposal.get("action_type") == "rollback_deployment":
            risk_level = "high"
        return {
            "current_node": "risk_assessment",
            "completed_nodes": ["risk_assessment"],
            "assessed_risk_level": risk_level or "high",
        }

    return risk_assessment


def make_request_human_approval_node(
    store: ApprovalStore | None = None,
) -> Callable[[IncidentInvestigationState], Awaitable[dict[str, Any]]]:
    async def request_human_approval(state: IncidentInvestigationState) -> dict[str, Any]:
        pending_action_id = state.get("pending_action_id")
        risk_level = state.get("assessed_risk_level", "high")
        if pending_action_id is None:
            return {
                "current_node": "request_human_approval",
                "completed_nodes": ["request_human_approval"],
                "investigation_status": "completed",
                "approval_decision": {"decision": "skipped"},
            }

        if risk_level not in {"medium", "high"}:
            return {
                "current_node": "request_human_approval",
                "completed_nodes": ["request_human_approval"],
                "investigation_status": "completed",
                "approval_decision": {"decision": "skipped"},
            }

        approval_id_value: str | None = None
        resume_token: str | None = None
        if store is not None:
            created_approval_id, resume_token = await store.create_pending_approval(
                proposed_action_id=UUID(pending_action_id),
                agent_run_id=as_uuid(state["agent_run_id"]),
                graph_thread_id=state["graph_thread_id"],
            )
            approval_id_value = str(created_approval_id)

        decision = interrupt(
            {
                "approval_id": approval_id_value,
                "resume_token": resume_token,
                "pending_action_id": pending_action_id,
            }
        )
        branch = (decision or {}).get("decision", "rejected")
        status = "completed"
        updates: dict[str, Any] = {
            "current_node": "request_human_approval",
            "completed_nodes": ["request_human_approval"],
            "approval_decision": decision,
        }
        if branch == "approved":
            status = "awaiting_execution"
            updates["investigation_status"] = status
            return updates

        rejected_ids = list(state.get("rejected_action_ids") or [])
        if pending_action_id:
            rejected_ids.append(pending_action_id)
        updates["rejected_action_ids"] = rejected_ids
        updates["pending_action_id"] = None
        updates["proposal"] = None
        updates["proposal_attempts"] = state.get("proposal_attempts", 0) + 1
        updates["investigation_status"] = "running"
        return updates

    return request_human_approval
