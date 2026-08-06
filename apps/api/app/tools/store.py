from __future__ import annotations

import uuid
from datetime import datetime

from opspilot.tools.persistence import (
    AuditEventRecord,
    EvidenceRecord,
    ToolCallRecord,
    ToolPersistence,
)
from sqlalchemy import DateTime, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.audit.service import record_audit_event
from app.db.base import Base
from app.incidents.models import EvidenceSourceType
from app.incidents.service import upsert_evidence


class ToolCall(Base):
    __tablename__ = "tool_calls"
    __table_args__ = (Index("ix_tool_calls_incident", "incident_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    incident_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    tool_version: Mapped[str] = mapped_column(String(32), nullable=False)
    input_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    output_summary: Mapped[str] = mapped_column(String(4000), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False, default="low")
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class SqlAlchemyToolPersistence(ToolPersistence):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def persist_invocation(
        self,
        *,
        tool_call: ToolCallRecord,
        audit_event: AuditEventRecord,
        evidence: list[EvidenceRecord],
    ) -> list[uuid.UUID]:
        self.session.add(
            ToolCall(
                id=tool_call.id,
                agent_run_id=tool_call.agent_run_id,
                incident_id=tool_call.incident_id,
                tool_name=tool_call.tool_name,
                tool_version=tool_call.tool_version,
                input_payload=tool_call.input_payload,
                output_summary=tool_call.output_summary,
                status=tool_call.status,
                risk_level=tool_call.risk_level,
                latency_ms=tool_call.latency_ms,
                retry_count=tool_call.retry_count,
                created_at=tool_call.created_at,
            )
        )
        await record_audit_event(
            self.session,
            actor_type=audit_event.actor_type,
            actor_id=audit_event.actor_id,
            event_type=audit_event.event_type,
            entity_type=audit_event.entity_type,
            entity_id=audit_event.entity_id,
            payload=audit_event.payload,
            request_id=audit_event.request_id,
        )
        stored_ids: list[uuid.UUID] = []
        for item in evidence:
            row = await upsert_evidence(
                self.session,
                incident_id=item.incident_id,
                source_type=EvidenceSourceType(item.source_type),
                source_reference=item.source_reference,
                title=item.title,
                content=item.content,
                structured_data=item.structured_data,
                observed_at=item.observed_at,
                relevance_score=item.relevance_score,
            )
            stored_ids.append(row.id)
        await self.session.flush()
        return stored_ids
