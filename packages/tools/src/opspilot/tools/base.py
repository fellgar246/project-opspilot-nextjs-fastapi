from __future__ import annotations

import enum
from typing import Any, Literal, Protocol, runtime_checkable
from uuid import UUID

from pydantic import BaseModel, Field


class ToolRole(enum.StrEnum):
    VIEWER = "viewer"
    OPERATOR = "operator"
    APPROVER = "approver"
    ADMIN = "admin"


ROLE_ORDER: dict[ToolRole, int] = {
    ToolRole.VIEWER: 0,
    ToolRole.OPERATOR: 1,
    ToolRole.APPROVER: 2,
    ToolRole.ADMIN: 3,
}


class RiskLevel(enum.StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RetryPolicy(BaseModel):
    max_attempts: int = 3
    backoff_base_seconds: float = 0.1
    idempotent: bool = True


class ToolSpec(BaseModel):
    name: str
    version: str
    description: str
    input_schema: type[BaseModel]
    output_schema: type[BaseModel]
    risk_level: RiskLevel = RiskLevel.LOW
    required_role: ToolRole = ToolRole.VIEWER
    timeout_seconds: float = 30.0
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    is_write: bool = False

    model_config = {"arbitrary_types_allowed": True}


class ToolContext(BaseModel):
    incident_id: UUID
    agent_run_id: UUID | None = None
    actor_type: Literal["agent", "user"]
    actor_id: UUID
    role: ToolRole
    request_id: str
    approval_id: UUID | None = None


class ToolError(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


ToolStatus = Literal[
    "ok",
    "invalid_input",
    "timeout",
    "backend_error",
    "forbidden",
    "circuit_open",
    "rate_limited",
    "audit_failed",
]


class ToolResult(BaseModel):
    status: ToolStatus
    tool_name: str
    tool_version: str
    data: BaseModel | None = None
    evidence_ids: list[UUID] = Field(default_factory=list)
    error: ToolError | None = None
    latency_ms: int
    truncated: bool = False
    notes: list[str] = Field(default_factory=list)


@runtime_checkable
class Tool(Protocol):
    spec: ToolSpec

    async def run(self, payload: BaseModel, ctx: ToolContext) -> BaseModel: ...
