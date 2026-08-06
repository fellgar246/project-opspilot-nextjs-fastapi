from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from opspilot.agent.graph.checkpointer import create_memory_checkpointer
from opspilot.agent.nodes.triage import make_triage_node
from opspilot.agent.providers.mock import MockProvider
from opspilot.agent.runner import create_provider, run_investigation
from opspilot.agent.state.graph_state import initial_state
from opspilot.tools.base import ToolResult, ToolSpec
from opspilot.tools.gateway import ToolGateway
from opspilot.tools.persistence import ToolPersistence
from opspilot.tools.registry import ToolRegistry
from pydantic import BaseModel


class _EmptyInput(BaseModel):
    pass


class _EmptyOutput(BaseModel):
    ok: bool = True


class _StubTool:
    spec = ToolSpec(
        name="get_service_health",
        version="1.0.0",
        description="stub",
        input_schema=_EmptyInput,
        output_schema=_EmptyOutput,
        is_write=False,
    )

    async def run(self, payload, ctx):
        return _EmptyOutput()


class _MemoryPersistence(ToolPersistence):
    async def persist_invocation(self, *, tool_call, audit_event, evidence):
        return [uuid4()]


class _StubGateway(ToolGateway):
    async def invoke(self, tool_name, payload, ctx, *, collect_evidence=True) -> ToolResult:
        return ToolResult(
            status="ok",
            tool_name=tool_name,
            tool_version="1.0.0",
            data=_EmptyOutput(),
            evidence_ids=[uuid4()],
            latency_ms=1,
        )


@pytest.mark.asyncio
async def test_triage_node_updates_state() -> None:
    provider = MockProvider()
    node = make_triage_node(provider)
    state = initial_state(
        incident_id="inc-1",
        agent_run_id="run-1",
        graph_thread_id="thread-1",
        incident_title="t",
        incident_description="d",
        incident_severity="sev2",
        service_names=["demo-service"],
        repository=None,
        prompt_version="v1",
        model="mock-v1",
        started_at=datetime.now(UTC).isoformat(),
    )
    updates = await node(state)
    assert updates["perceived_severity"] == "sev2"
    assert "triage_incident" in updates["completed_nodes"]


@pytest.mark.asyncio
async def test_run_investigation_with_stub_gateway() -> None:
    registry = ToolRegistry()
    registry.register(_StubTool())
    gateway = _StubGateway(registry, _MemoryPersistence())
    provider = create_provider()
    checkpointer = create_memory_checkpointer()
    incident = {
        "id": str(uuid4()),
        "title": "Outage",
        "description": "Errors spiking",
        "severity": "sev2",
        "service_names": ["demo-service"],
        "repository": None,
        "started_at": datetime.now(UTC).isoformat(),
    }
    final = await run_investigation(
        provider=provider,
        gateway=gateway,
        checkpointer=checkpointer,
        incident=incident,
        agent_run_id=uuid4(),
        graph_thread_id="thread-test",
    )
    assert final["investigation_status"] in {"completed", "iteration_limit_reached", "timeout"}
    assert final.get("hypotheses") or final.get("negative_findings") or final.get("evidence_refs")
