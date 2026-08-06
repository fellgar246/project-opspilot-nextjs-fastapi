from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID, uuid4

from opspilot.tools.base import ToolContext, ToolResult, ToolStatus
from opspilot.tools.redaction import redact


@dataclass
class ToolCallRecord:
    id: UUID
    agent_run_id: UUID | None
    incident_id: UUID
    tool_name: str
    tool_version: str
    input_payload: dict[str, Any]
    output_summary: str
    status: ToolStatus
    risk_level: str
    latency_ms: int
    retry_count: int
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class AuditEventRecord:
    id: UUID
    actor_type: str
    actor_id: UUID
    event_type: str
    entity_type: str
    entity_id: UUID
    payload: dict[str, Any]
    request_id: str
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class EvidenceRecord:
    id: UUID
    incident_id: UUID
    source_type: str
    source_reference: str
    title: str
    content: str
    structured_data: dict[str, Any]
    observed_at: datetime
    collected_at: datetime
    checksum: str
    relevance_score: float | None = None


class ToolPersistence(Protocol):
    async def persist_invocation(
        self,
        *,
        tool_call: ToolCallRecord,
        audit_event: AuditEventRecord,
        evidence: list[EvidenceRecord],
    ) -> list[UUID]: ...


class InMemoryToolPersistence:
    def __init__(self) -> None:
        self.tool_calls: list[ToolCallRecord] = []
        self.audit_events: list[AuditEventRecord] = []
        self.evidence: list[EvidenceRecord] = []
        self.fail_next: bool = False

    async def persist_invocation(
        self,
        *,
        tool_call: ToolCallRecord,
        audit_event: AuditEventRecord,
        evidence: list[EvidenceRecord],
    ) -> list[UUID]:
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("simulated persistence failure")
        self.tool_calls.append(tool_call)
        self.audit_events.append(audit_event)
        stored_ids: list[UUID] = []
        for item in evidence:
            existing = next(
                (
                    e
                    for e in self.evidence
                    if e.incident_id == item.incident_id and e.checksum == item.checksum
                ),
                None,
            )
            if existing is not None:
                stored_ids.append(existing.id)
                continue
            self.evidence.append(item)
            stored_ids.append(item.id)
        return stored_ids


def compute_evidence_checksum(content: str, structured_data: dict[str, Any]) -> str:
    normalized = json.dumps(
        {"content": content.strip(), "structured_data": structured_data},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(normalized.encode()).hexdigest()


def summarize_output(result: ToolResult, *, max_chars: int) -> str:
    if result.data is None:
        text = result.error.message if result.error is not None else f"status={result.status}"
    else:
        text = result.data.model_dump_json()
    if len(text) > max_chars:
        return text[: max_chars - 3] + "..."
    return text


def build_tool_call_record(
    *,
    ctx: ToolContext,
    tool_name: str,
    tool_version: str,
    input_payload: dict[str, Any],
    result: ToolResult,
    retry_count: int,
    risk_level: str,
    summary_max_chars: int,
) -> ToolCallRecord:
    return ToolCallRecord(
        id=uuid4(),
        agent_run_id=ctx.agent_run_id,
        incident_id=ctx.incident_id,
        tool_name=tool_name,
        tool_version=tool_version,
        input_payload=redact(input_payload),
        output_summary=summarize_output(result, max_chars=summary_max_chars),
        status=result.status,
        risk_level=risk_level,
        latency_ms=result.latency_ms,
        retry_count=retry_count,
    )


def build_audit_event(
    *,
    ctx: ToolContext,
    tool_call_id: UUID,
    tool_name: str,
    status: ToolStatus,
    latency_ms: int,
) -> AuditEventRecord:
    return AuditEventRecord(
        id=uuid4(),
        actor_type=ctx.actor_type,
        actor_id=ctx.actor_id,
        event_type="tool.invoked",
        entity_type="tool_call",
        entity_id=tool_call_id,
        payload=redact(
            {
                "tool_name": tool_name,
                "status": status,
                "latency_ms": latency_ms,
                "incident_id": str(ctx.incident_id),
            }
        ),
        request_id=ctx.request_id,
    )
