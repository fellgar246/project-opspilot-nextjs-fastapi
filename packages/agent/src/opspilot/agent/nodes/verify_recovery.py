from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, Literal

from opspilot.agent.nodes.base import as_uuid
from opspilot.agent.state.graph_state import IncidentInvestigationState
from opspilot.agent.state.schema import MetricComparison, RecoveryVerdict
from opspilot.tools.base import ToolContext, ToolRole
from opspilot.tools.config import get_tool_settings
from opspilot.tools.gateway import ToolGateway


def _metric_stats(series: list[dict[str, Any]]) -> float | None:
    values = [float(point.get("value", 0)) for point in series if point.get("value") is not None]
    if not values:
        return None
    return sum(values) / len(values)


def _determine_verdict(
    *,
    baseline: float | None,
    degraded: float | None,
    post_action: float | None,
    error_threshold: float,
    partial_threshold: float,
) -> Literal["recovered", "partially_recovered", "not_recovered", "inconclusive"]:
    if baseline is None or post_action is None:
        return "inconclusive"
    if degraded is not None and post_action >= degraded:
        return "not_recovered"
    delta = abs(post_action - baseline)
    if delta <= error_threshold:
        return "recovered"
    if delta <= partial_threshold:
        return "partially_recovered"
    return "not_recovered"


def make_verify_recovery_node(
    gateway: ToolGateway,
) -> Callable[[IncidentInvestigationState], Awaitable[dict[str, Any]]]:
    async def verify_recovery(state: IncidentInvestigationState) -> dict[str, Any]:
        execution_status = state.get("execution_status")
        if execution_status and execution_status != "succeeded":
            return {
                "current_node": "verify_recovery",
                "completed_nodes": ["verify_recovery"],
                "recovery_verdict": {"status": "inconclusive", "metrics": [], "rationale": ""},
            }

        tool_settings = get_tool_settings()
        stabilization = tool_settings.recovery_stabilization_seconds
        await asyncio.sleep(min(stabilization, 1.0))

        service = (
            state.get("affected_services") or state.get("service_names") or ["demo-service"]
        )[0]
        metric_name = "http_error_rate"
        ctx = ToolContext(
            incident_id=as_uuid(state["incident_id"]),
            agent_run_id=as_uuid(state["agent_run_id"]),
            actor_type="agent",
            actor_id=as_uuid(state["agent_run_id"]),
            role=ToolRole.VIEWER,
            request_id=state["graph_thread_id"],
        )

        windows = [
            ("baseline", "-2h", "-1h"),
            ("degraded", "-1h", "-15m"),
            ("post_action", "-15m", "now"),
        ]
        comparisons: list[MetricComparison] = []
        evidence_ids: list[str] = []
        stats: dict[str, float | None] = {}

        for label, start, end in windows:
            result = await gateway.invoke(
                "query_metrics",
                {
                    "service": service,
                    "metric": metric_name,
                    "time_range": {"start": start, "end": end},
                    "aggregation": "avg",
                },
                ctx,
            )
            avg: float | None = None
            if result.status == "ok" and result.data is not None:
                series = result.data.model_dump().get("series") or []
                avg = _metric_stats(series)
                evidence_ids.extend(str(item) for item in (result.evidence_ids or []))
            stats[label] = avg
            comparisons.append(
                MetricComparison(
                    metric=metric_name,
                    window=label,
                    baseline_value=stats.get("baseline"),
                    degraded_value=stats.get("degraded") if label == "degraded" else None,
                    post_action_value=stats.get("post_action") if label == "post_action" else avg,
                    unit="ratio",
                )
            )

        status = _determine_verdict(
            baseline=stats.get("baseline"),
            degraded=stats.get("degraded"),
            post_action=stats.get("post_action"),
            error_threshold=tool_settings.recovery_error_rate_threshold,
            partial_threshold=tool_settings.recovery_partial_threshold,
        )
        rationale = (
            f"Compared {metric_name} baseline={stats.get('baseline')} "
            f"degraded={stats.get('degraded')} post_action={stats.get('post_action')}"
        )
        verdict = RecoveryVerdict(
            status=status,
            metrics=comparisons,
            window_seconds=stabilization,
            rationale=rationale,
            evidence_ids=evidence_ids,
        )

        investigation_status = "running"
        if status == "recovered" or status == "partially_recovered":
            investigation_status = "monitoring"
        elif status == "not_recovered":
            investigation_status = "running"

        return {
            "current_node": "verify_recovery",
            "completed_nodes": ["verify_recovery"],
            "recovery_verdict": verdict.model_dump(),
            "investigation_status": investigation_status,
        }

    return verify_recovery
