from __future__ import annotations

from opspilot.tools.adapters.base import MetricsBackend
from opspilot.tools.adapters.prometheus import decimate_series
from opspilot.tools.adapters.simulator_api import SimulatorApiAdapter
from opspilot.tools.base import RetryPolicy, RiskLevel, ToolContext, ToolRole, ToolSpec
from opspilot.tools.config import ToolGatewaySettings
from opspilot.tools.read.schemas import (
    QueryMetricsInput,
    QueryMetricsOutput,
    ServiceHealthOutput,
    ServiceInput,
)
from opspilot.tools.time_range import resolve_time_range


class GetServiceHealthTool:
    spec = ToolSpec(
        name="get_service_health",
        version="1.0.0",
        description="Return service health, deployed version, and dependency status.",
        input_schema=ServiceInput,
        output_schema=ServiceHealthOutput,
        risk_level=RiskLevel.LOW,
        required_role=ToolRole.VIEWER,
        timeout_seconds=10.0,
        retry_policy=RetryPolicy(max_attempts=3, idempotent=True),
        is_write=False,
    )

    def __init__(self, simulator: SimulatorApiAdapter) -> None:
        self.simulator = simulator

    async def run(self, payload: ServiceInput, ctx: ToolContext) -> ServiceHealthOutput:
        data = await self.simulator.get_health(payload.service)
        return ServiceHealthOutput.model_validate(data)


class QueryMetricsTool:
    spec = ToolSpec(
        name="query_metrics",
        version="1.0.0",
        description="Query time-series metrics with statistics and baseline comparison.",
        input_schema=QueryMetricsInput,
        output_schema=QueryMetricsOutput,
        risk_level=RiskLevel.LOW,
        required_role=ToolRole.VIEWER,
        timeout_seconds=20.0,
        retry_policy=RetryPolicy(max_attempts=3, idempotent=True),
        is_write=False,
    )

    def __init__(self, metrics_backend: MetricsBackend, settings: ToolGatewaySettings) -> None:
        self.metrics = metrics_backend
        self.settings = settings
        self.last_notes: list[str] = []

    async def run(self, payload: QueryMetricsInput, ctx: ToolContext) -> QueryMetricsOutput:
        start, end, notes = resolve_time_range(
            payload.time_range,
            max_hours=self.settings.max_time_range_hours,
        )
        raw = await self.metrics.query_range(
            service=payload.service,
            metric=payload.metric,
            start=start.timestamp(),
            end=end.timestamp(),
            step="60s",
            aggregation=payload.aggregation,
            group_by=payload.group_by,
        )
        series, decimated = decimate_series(raw["series"], self.settings.max_metric_points)
        if decimated:
            notes.append(f"series decimated to {self.settings.max_metric_points} points")
        self.last_notes = notes
        return QueryMetricsOutput(
            service=payload.service,
            metric=payload.metric,
            unit=raw.get("unit"),
            series=series,
            statistics=raw.get("statistics", {}),
            baseline_comparison=raw.get("baseline_comparison", {}),
            time_range_label=f"{start.isoformat()}..{end.isoformat()}",
        )
