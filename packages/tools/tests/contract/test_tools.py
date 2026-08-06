from __future__ import annotations

from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import pytest
from opspilot.tools.base import ToolContext, ToolRole
from opspilot.tools.bootstrap import build_default_registry
from opspilot.tools.config import ToolGatewaySettings
from opspilot.tools.gateway import ToolGateway
from opspilot.tools.persistence import InMemoryToolPersistence
from opspilot.tools.read.schemas import QueryMetricsOutput
from opspilot.tools.time_range import TimeRangeInput, resolve_time_range

REPO_ROOT = Path(__file__).resolve().parents[4]


@pytest.fixture
def gateway() -> ToolGateway:
    settings = ToolGatewaySettings(repo_root=REPO_ROOT)
    registry = build_default_registry(settings)
    return ToolGateway(registry, InMemoryToolPersistence(), settings=settings)


@pytest.fixture
def ctx() -> ToolContext:
    return ToolContext(
        incident_id=uuid4(),
        agent_run_id=uuid4(),
        actor_type="agent",
        actor_id=uuid4(),
        role=ToolRole.OPERATOR,
        request_id="contract-req",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tool_name,payload",
    [
        ("list_services", {}),
        ("get_service_health", {"service": "demo-service"}),
        (
            "query_metrics",
            {
                "service": "demo-service",
                "metric": "http_requests_total",
                "time_range": {"relative": "last_30m"},
                "aggregation": "avg",
            },
        ),
        (
            "search_logs",
            {
                "service": "demo-service",
                "query": "PoolTimeout",
                "time_range": {"relative": "last_30m"},
                "limit": 10,
            },
        ),
        (
            "get_recent_deployments",
            {"service": "demo-service", "time_range": {"relative": "last_7d"}},
        ),
        ("get_deployment_details", {"deployment_id": "dep-seed-001"}),
        (
            "get_recent_commits",
            {
                "repository": "simulator/data/repos/demo-service.git",
                "time_range": {"relative": "last_30d"},
            },
        ),
        (
            "get_pull_request",
            {"repository": "simulator/data/repos/demo-service.git", "number": 101},
        ),
        ("get_feature_flags", {"service": "demo-service"}),
    ],
)
async def test_read_tool_contract(
    gateway: ToolGateway, ctx: ToolContext, tool_name: str, payload: dict[str, Any]
) -> None:
    result = await gateway.invoke(tool_name, payload, ctx)
    assert result.status == "ok", result.error
    assert result.data is not None
    assert result.latency_ms >= 0
    assert len(gateway.registry.require(tool_name).spec.output_schema.model_fields) > 0


def test_time_range_clipped_with_note() -> None:
    _, _, notes = resolve_time_range(
        TimeRangeInput(relative="last_48h"),
        max_hours=24.0,
    )
    assert any("clipped" in note for note in notes)


@pytest.mark.asyncio
async def test_search_logs_invalid_input(gateway: ToolGateway, ctx: ToolContext) -> None:
    result = await gateway.invoke(
        "search_logs",
        {"service": "demo-service", "time_range": {"relative": "last_30m"}},
        ctx,
    )
    assert result.status == "ok"


@pytest.mark.asyncio
async def test_query_metrics_decimation_note(gateway: ToolGateway, ctx: ToolContext) -> None:
    result = await gateway.invoke(
        "query_metrics",
        {
            "service": "demo-service",
            "metric": "http_requests_total",
            "time_range": {"relative": "last_24h"},
            "aggregation": "max",
        },
        ctx,
    )
    assert result.status == "ok"
    assert result.data is not None
    metrics = cast(QueryMetricsOutput, result.data)
    assert len(metrics.series) <= gateway.settings.max_metric_points
