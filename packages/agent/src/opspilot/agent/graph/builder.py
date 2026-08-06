from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langgraph.graph import END, START, StateGraph
from opspilot.agent.approvals.protocol import ApprovalStore
from opspilot.agent.graph.routing import (
    route_after_approval,
    route_after_critique,
    route_after_execution,
    route_after_verify_recovery,
)
from opspilot.agent.nodes.close import make_close_investigation_node
from opspilot.agent.nodes.collect import (
    make_code_changes_node,
    make_deployments_node,
    make_logs_node,
    make_metrics_node,
    make_service_health_node,
)
from opspilot.agent.nodes.critique import make_critique_hypotheses_node
from opspilot.agent.nodes.execute_action import make_execute_approved_action_node
from opspilot.agent.nodes.hypotheses import make_hypotheses_node
from opspilot.agent.nodes.mitigation import (
    make_propose_mitigation_node,
    make_request_human_approval_node,
    make_risk_assessment_node,
)
from opspilot.agent.nodes.plan import make_plan_node
from opspilot.agent.nodes.postmortem import make_generate_postmortem_node
from opspilot.agent.nodes.request_evidence import make_request_more_evidence_node
from opspilot.agent.nodes.retrieve_runbooks import make_retrieve_runbooks_node
from opspilot.agent.nodes.triage import make_triage_node
from opspilot.agent.nodes.verify_recovery import make_verify_recovery_node
from opspilot.agent.providers.base import LLMProvider
from opspilot.agent.state.graph_state import IncidentInvestigationState
from opspilot.agent.state.reducers import (
    merge_claims,
    merge_completed_nodes,
    merge_errors,
    merge_evidence_refs,
    merge_explored_tools,
    merge_hypotheses,
    merge_negative_findings,
    merge_node_metrics,
    merge_parse_errors,
    merge_timeline,
)
from opspilot.tools.gateway import ToolGateway


def build_investigation_graph(
    provider: LLMProvider,
    gateway: ToolGateway,
    *,
    checkpointer: Any,
    approval_store: ApprovalStore | None = None,
    postmortem_store: Any | None = None,
) -> Any:
    graph: Any = StateGraph(IncidentInvestigationState)

    graph.add_node("triage_incident", make_triage_node(provider))
    graph.add_node("build_investigation_plan", make_plan_node(provider))
    graph.add_node("collect_service_health", make_service_health_node(gateway))
    graph.add_node("collect_metrics", make_metrics_node(gateway))
    graph.add_node("collect_logs", make_logs_node(gateway))
    graph.add_node("collect_deployments", make_deployments_node(gateway))
    graph.add_node("collect_code_changes", make_code_changes_node(gateway))
    graph.add_node("retrieve_runbooks", make_retrieve_runbooks_node(gateway))
    graph.add_node("generate_hypotheses", make_hypotheses_node(provider))
    graph.add_node("critique_hypotheses", make_critique_hypotheses_node(provider))
    graph.add_node("request_more_evidence", make_request_more_evidence_node())
    graph.add_node("propose_mitigation", make_propose_mitigation_node(gateway, approval_store))
    graph.add_node("risk_assessment", make_risk_assessment_node())
    graph.add_node("request_human_approval", make_request_human_approval_node(approval_store))
    graph.add_node("execute_approved_action", make_execute_approved_action_node(gateway))
    graph.add_node("verify_recovery", make_verify_recovery_node(gateway))
    graph.add_node("generate_postmortem", make_generate_postmortem_node(postmortem_store))
    graph.add_node("close_investigation", make_close_investigation_node())

    graph.add_edge(START, "triage_incident")
    graph.add_edge("triage_incident", "build_investigation_plan")
    graph.add_edge("build_investigation_plan", "collect_service_health")
    graph.add_edge("collect_service_health", "collect_metrics")
    graph.add_edge("collect_metrics", "collect_logs")
    graph.add_edge("collect_logs", "collect_deployments")
    graph.add_edge("collect_deployments", "collect_code_changes")
    graph.add_edge("collect_code_changes", "retrieve_runbooks")
    graph.add_edge("retrieve_runbooks", "generate_hypotheses")
    graph.add_edge("generate_hypotheses", "critique_hypotheses")

    graph.add_conditional_edges(
        "critique_hypotheses",
        route_after_critique,
        {
            "request_more_evidence": "request_more_evidence",
            "propose_mitigation": "propose_mitigation",
            "close": "close_investigation",
        },
    )

    graph.add_edge("propose_mitigation", "risk_assessment")
    graph.add_edge("risk_assessment", "request_human_approval")
    graph.add_conditional_edges(
        "request_human_approval",
        route_after_approval,
        {
            "propose_mitigation": "propose_mitigation",
            "execute_approved_action": "execute_approved_action",
            "generate_postmortem": "generate_postmortem",
            "close_investigation": "close_investigation",
        },
    )
    graph.add_conditional_edges(
        "execute_approved_action",
        route_after_execution,
        {
            "verify_recovery": "verify_recovery",
            "propose_mitigation": "propose_mitigation",
            "close_investigation": "close_investigation",
        },
    )
    graph.add_conditional_edges(
        "verify_recovery",
        route_after_verify_recovery,
        {
            "generate_postmortem": "generate_postmortem",
            "propose_mitigation": "propose_mitigation",
            "close_investigation": "close_investigation",
        },
    )
    graph.add_edge("generate_postmortem", "close_investigation")

    def route_after_request(state: IncidentInvestigationState) -> str:
        target = state.get("next_collection_node")
        if target:
            return target
        return "close_investigation"

    graph.add_conditional_edges(
        "request_more_evidence",
        route_after_request,
        {
            "collect_service_health": "collect_service_health",
            "collect_metrics": "collect_metrics",
            "collect_logs": "collect_logs",
            "collect_deployments": "collect_deployments",
            "collect_code_changes": "collect_code_changes",
            "retrieve_runbooks": "retrieve_runbooks",
            "close_investigation": "close_investigation",
        },
    )
    graph.add_edge("close_investigation", END)

    return graph.compile(checkpointer=checkpointer)


def graph_reducers() -> dict[str, Callable[..., Any]]:
    """Reducer map used when constructing state manually in tests."""
    return {
        "evidence_refs": merge_evidence_refs,
        "negative_findings": merge_negative_findings,
        "timeline": merge_timeline,
        "hypotheses": merge_hypotheses,
        "claims": merge_claims,
        "completed_nodes": merge_completed_nodes,
        "explored_tools": merge_explored_tools,
        "errors": merge_errors,
        "parse_errors": merge_parse_errors,
        "node_metrics": merge_node_metrics,
    }
