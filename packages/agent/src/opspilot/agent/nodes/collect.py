from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from opspilot.agent.nodes.base import as_uuid, record_node_timing
from opspilot.agent.state.graph_state import IncidentInvestigationState
from opspilot.agent.state.schema import (
    TOOL_BY_COLLECTION_NODE,
    TOOL_EVIDENCE_SOURCE_TYPE,
    EvidenceRef,
    NegativeFinding,
    TimelineEntry,
)
from opspilot.tools.base import ToolContext, ToolResult, ToolRole
from opspilot.tools.gateway import ToolGateway


def _primary_service(state: IncidentInvestigationState) -> str:
    services = state.get("affected_services") or state.get("service_names") or ["demo-service"]
    return services[0]


def _time_range(state: IncidentInvestigationState) -> dict[str, str]:
    window = state.get("time_window") or {}
    if window:
        return {
            "label": "incident_window",
            "start": window.get("start") or "",
            "end": window.get("end") or "",
        }
    return {"label": "last_1h"}


async def _invoke_tool(
    gateway: ToolGateway,
    *,
    state: IncidentInvestigationState,
    tool_name: str,
    payload: dict[str, Any],
) -> ToolResult:
    ctx = ToolContext(
        incident_id=as_uuid(state["incident_id"]),
        agent_run_id=as_uuid(state["agent_run_id"]),
        actor_type="agent",
        actor_id=as_uuid(state["agent_run_id"]),
        role=ToolRole.OPERATOR,
        request_id=state["graph_thread_id"],
    )
    return await gateway.invoke(tool_name, payload, ctx)


def _tool_updates(
    *,
    state: IncidentInvestigationState,
    node: str,
    tool_name: str,
    service: str,
    result: ToolResult,
    started: float,
) -> dict[str, Any]:
    updates: dict[str, Any] = {
        "current_node": node,
        "completed_nodes": [node],
        "explored_tools": [tool_name],
        "tool_call_count": state["tool_call_count"] + 1,
        "node_metrics": [
            record_node_timing(
                node=node,
                started=started,
                prompt_tokens=0,
                completion_tokens=0,
            )
        ],
    }

    if result.status != "ok" or not result.evidence_ids:
        updates["negative_findings"] = [
            NegativeFinding(
                tool_name=tool_name,
                service=service,
                message=result.error.message if result.error else "No evidence returned",
            )
        ]
        return updates

    evidence_refs: list[EvidenceRef] = []
    timeline: list[TimelineEntry] = []
    now = datetime.now(UTC).isoformat()
    for evidence_id in result.evidence_ids:
        summary = f"{tool_name} returned evidence for {service}"
        evidence_refs.append(
            EvidenceRef(
                evidence_id=str(evidence_id),
                source_type=TOOL_EVIDENCE_SOURCE_TYPE.get(tool_name, tool_name),
                title=f"{tool_name} result",
                summary=summary[:500],
                tool_name=tool_name,
            )
        )
        timeline.append(
            TimelineEntry(
                occurred_at=now,
                kind="evidence",
                title=f"Collected {tool_name}",
                summary=summary[:300],
                evidence_id=str(evidence_id),
            )
        )

    updates["evidence_refs"] = evidence_refs
    updates["timeline"] = timeline
    return updates


def make_collect_node(
    gateway: ToolGateway,
    *,
    node: str,
    build_payload: Callable[[IncidentInvestigationState, str], dict[str, Any]],
) -> Callable[[IncidentInvestigationState], Awaitable[dict[str, Any]]]:
    tool_name = TOOL_BY_COLLECTION_NODE[node]

    async def collect(state: IncidentInvestigationState) -> dict[str, Any]:
        started = time.perf_counter()
        service = _primary_service(state)
        payload = build_payload(state, service)
        result = await _invoke_tool(gateway, state=state, tool_name=tool_name, payload=payload)
        return _tool_updates(
            state=state,
            node=node,
            tool_name=tool_name,
            service=service,
            result=result,
            started=started,
        )

    return collect


def make_service_health_node(
    gateway: ToolGateway,
) -> Callable[[IncidentInvestigationState], Awaitable[dict[str, Any]]]:
    return make_collect_node(
        gateway,
        node="collect_service_health",
        build_payload=lambda _state, service: {"service": service},
    )


def make_metrics_node(
    gateway: ToolGateway,
) -> Callable[[IncidentInvestigationState], Awaitable[dict[str, Any]]]:
    return make_collect_node(
        gateway,
        node="collect_metrics",
        build_payload=lambda state, service: {
            "service": service,
            "metric": "http_request_duration_seconds",
            "time_range": _time_range(state),
        },
    )


def make_logs_node(
    gateway: ToolGateway,
) -> Callable[[IncidentInvestigationState], Awaitable[dict[str, Any]]]:
    return make_collect_node(
        gateway,
        node="collect_logs",
        build_payload=lambda state, service: {
            "service": service,
            "query": "error OR exception OR timeout",
            "time_range": _time_range(state),
            "limit": 50,
        },
    )


def make_deployments_node(
    gateway: ToolGateway,
) -> Callable[[IncidentInvestigationState], Awaitable[dict[str, Any]]]:
    return make_collect_node(
        gateway,
        node="collect_deployments",
        build_payload=lambda state, service: {
            "service": service,
            "time_range": _time_range(state),
        },
    )


def make_code_changes_node(
    gateway: ToolGateway,
) -> Callable[[IncidentInvestigationState], Awaitable[dict[str, Any]]]:
    def build_payload(state: IncidentInvestigationState, service: str) -> dict[str, Any]:
        repository = state.get("repository") or "ops-pilot/demo-service"
        return {
            "repository": repository,
            "time_range": _time_range(state),
        }

    return make_collect_node(
        gateway,
        node="collect_code_changes",
        build_payload=build_payload,
    )
