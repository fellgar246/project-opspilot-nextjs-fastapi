from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import uuid4

import pytest
from opspilot.tools.base import (
    RetryPolicy,
    RiskLevel,
    ToolContext,
    ToolRole,
    ToolSpec,
)
from opspilot.tools.config import ToolGatewaySettings
from opspilot.tools.gateway import ToolGateway
from opspilot.tools.persistence import InMemoryToolPersistence
from opspilot.tools.policies import CircuitBreaker
from opspilot.tools.registry import ToolRegistry
from pydantic import BaseModel

REPO_ROOT = Path(__file__).resolve().parents[3]


class EchoInput(BaseModel):
    value: str


class EchoOutput(BaseModel):
    value: str


class EchoTool:
    spec = ToolSpec(
        name="echo",
        version="1.0.0",
        description="echo",
        input_schema=EchoInput,
        output_schema=EchoOutput,
        risk_level=RiskLevel.LOW,
        required_role=ToolRole.VIEWER,
        timeout_seconds=1.0,
        retry_policy=RetryPolicy(max_attempts=3, idempotent=True),
        is_write=False,
    )

    def __init__(self, delay: float = 0.0, fail_times: int = 0) -> None:
        self.delay = delay
        self.fail_times = fail_times
        self.calls = 0

    async def run(self, payload: EchoInput, ctx: ToolContext) -> EchoOutput:
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.calls <= self.fail_times:
            raise RuntimeError("transient")
        return EchoOutput(value=payload.value)


class WriteInput(BaseModel):
    action: str


class WriteOutput(BaseModel):
    ok: bool


class FakeWriteTool:
    spec = ToolSpec(
        name="fake_write",
        version="1.0.0",
        description="write test",
        input_schema=WriteInput,
        output_schema=WriteOutput,
        risk_level=RiskLevel.HIGH,
        required_role=ToolRole.APPROVER,
        timeout_seconds=1.0,
        is_write=True,
    )

    async def run(self, payload: WriteInput, ctx: ToolContext) -> WriteOutput:
        return WriteOutput(ok=True)


@pytest.fixture
def ctx() -> ToolContext:
    return ToolContext(
        incident_id=uuid4(),
        agent_run_id=uuid4(),
        actor_type="agent",
        actor_id=uuid4(),
        role=ToolRole.OPERATOR,
        request_id="req-1",
    )


def _gateway(*tools) -> tuple[ToolGateway, InMemoryToolPersistence]:
    registry = ToolRegistry()
    for tool in tools:
        registry.register(tool)
    persistence = InMemoryToolPersistence()
    settings = ToolGatewaySettings(
        repo_root=REPO_ROOT,
        circuit_breaker_threshold=3,
        circuit_breaker_cooldown_seconds=60.0,
    )
    return ToolGateway(registry, persistence, settings=settings), persistence


@pytest.mark.asyncio
async def test_invalid_input_returns_without_persist(ctx: ToolContext) -> None:
    gateway, persistence = _gateway(EchoTool())
    result = await gateway.invoke("echo", {}, ctx)
    assert result.status == "invalid_input"
    assert len(persistence.tool_calls) == 0


@pytest.mark.asyncio
async def test_timeout_status(ctx: ToolContext) -> None:
    tool = EchoTool(delay=0.15)
    tool.spec = tool.spec.model_copy(update={"timeout_seconds": 0.05})
    gateway, _ = _gateway(tool)
    result = await gateway.invoke("echo", {"value": "x"}, ctx)
    assert result.status == "timeout"


@pytest.mark.asyncio
async def test_retry_then_success(ctx: ToolContext) -> None:
    gateway, persistence = _gateway(EchoTool(fail_times=1))
    result = await gateway.invoke("echo", {"value": "ok"}, ctx)
    assert result.status == "ok"
    assert persistence.tool_calls[-1].retry_count == 1


@pytest.mark.asyncio
async def test_forbidden_role(ctx: ToolContext) -> None:
    gateway, persistence = _gateway(FakeWriteTool())
    low_role_ctx = ctx.model_copy(update={"role": ToolRole.VIEWER})
    result = await gateway.invoke("fake_write", {"action": "rollback"}, low_role_ctx)
    assert result.status == "forbidden"
    assert len(persistence.tool_calls) == 1


@pytest.mark.asyncio
async def test_write_without_approval_rejected(ctx: ToolContext) -> None:
    gateway, persistence = _gateway(FakeWriteTool())
    approver_ctx = ctx.model_copy(update={"role": ToolRole.APPROVER, "approval_id": None})
    result = await gateway.invoke("fake_write", {"action": "rollback"}, approver_ctx)
    assert result.status == "forbidden"
    assert result.error is not None
    assert "approval" in result.error.message.lower()


@pytest.mark.asyncio
async def test_circuit_breaker_opens(ctx: ToolContext) -> None:
    gateway, _ = _gateway(EchoTool(fail_times=99))
    for _ in range(3):
        await gateway.invoke("echo", {"value": "x"}, ctx)
    result = await gateway.invoke("echo", {"value": "x"}, ctx)
    assert result.status == "circuit_open"


@pytest.mark.asyncio
async def test_persistence_failure_marks_audit_failed(ctx: ToolContext) -> None:
    gateway, persistence = _gateway(EchoTool())
    persistence.fail_next = True
    result = await gateway.invoke("echo", {"value": "x"}, ctx)
    assert result.status == "audit_failed"


@pytest.mark.asyncio
async def test_tool_call_and_audit_event_pairing(ctx: ToolContext) -> None:
    gateway, persistence = _gateway(EchoTool())
    await gateway.invoke("echo", {"value": "x"}, ctx, collect_evidence=False)
    assert len(persistence.tool_calls) == 1
    assert len(persistence.audit_events) == 1
    assert persistence.audit_events[0].event_type == "tool.invoked"


def test_circuit_breaker_recovers_after_cooldown() -> None:
    breaker = CircuitBreaker(threshold=2, cooldown_seconds=0.01)
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.is_open()
    import time

    time.sleep(0.02)
    assert not breaker.is_open()
