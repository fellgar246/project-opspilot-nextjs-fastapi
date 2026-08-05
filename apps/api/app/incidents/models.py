from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ServiceEnvironment(enum.StrEnum):
    PRODUCTION = "production"
    STAGING = "staging"
    DEMO = "demo"


class IncidentSeverity(enum.StrEnum):
    SEV1 = "sev1"
    SEV2 = "sev2"
    SEV3 = "sev3"
    SEV4 = "sev4"


class IncidentStatus(enum.StrEnum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    MITIGATING = "mitigating"
    MONITORING = "monitoring"
    RESOLVED = "resolved"
    CLOSED = "closed"


class IncidentSource(enum.StrEnum):
    MANUAL = "manual"
    ALERT = "alert"
    SIMULATOR = "simulator"


class EvidenceSourceType(enum.StrEnum):
    METRIC = "metric"
    LOG = "log"
    DEPLOYMENT = "deployment"
    COMMIT = "commit"
    PULL_REQUEST = "pull_request"
    FEATURE_FLAG = "feature_flag"
    RUNBOOK = "runbook"
    SIMILAR_INCIDENT = "similar_incident"
    NOTE = "note"


class HypothesisStatus(enum.StrEnum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class Service(Base):
    __tablename__ = "services"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    repository: Mapped[str | None] = mapped_column(String(500), nullable=True)
    environment: Mapped[ServiceEnvironment] = mapped_column(
        Enum(ServiceEnvironment, name="service_environment", native_enum=False),
        nullable=False,
    )
    owner_team: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
    )

    incident_links: Mapped[list[IncidentService]] = relationship(back_populates="service")


class Incident(Base):
    __tablename__ = "incidents"
    __table_args__ = (
        Index("ix_incidents_started_at", "started_at", "id"),
        Index("ix_incidents_status_sev", "status", "severity"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[IncidentSeverity] = mapped_column(
        Enum(IncidentSeverity, name="incident_severity", native_enum=False),
        nullable=False,
    )
    status: Mapped[IncidentStatus] = mapped_column(
        Enum(IncidentStatus, name="incident_status", native_enum=False),
        nullable=False,
        default=IncidentStatus.OPEN,
    )
    source: Mapped[IncidentSource] = mapped_column(
        Enum(IncidentSource, name="incident_source", native_enum=False),
        nullable=False,
        default=IncidentSource.MANUAL,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
    )

    service_links: Mapped[list[IncidentService]] = relationship(
        back_populates="incident",
        cascade="all, delete-orphan",
    )
    notes: Mapped[list[IncidentNote]] = relationship(
        back_populates="incident",
        cascade="all, delete-orphan",
    )
    status_history: Mapped[list[IncidentStatusHistory]] = relationship(
        back_populates="incident",
        cascade="all, delete-orphan",
    )
    evidence_items: Mapped[list[Evidence]] = relationship(
        back_populates="incident",
        cascade="all, delete-orphan",
    )
    hypotheses: Mapped[list[Hypothesis]] = relationship(
        back_populates="incident",
        cascade="all, delete-orphan",
    )


class IncidentService(Base):
    __tablename__ = "incident_services"
    __table_args__ = (Index("ix_incident_services_svc", "service_id"),)

    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("services.id", ondelete="RESTRICT"),
        primary_key=True,
    )

    incident: Mapped[Incident] = relationship(back_populates="service_links")
    service: Mapped[Service] = relationship(back_populates="incident_links")


class IncidentNote(Base):
    __tablename__ = "incident_notes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False, default="user")
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    incident: Mapped[Incident] = relationship(back_populates="notes")


class IncidentStatusHistory(Base):
    __tablename__ = "incident_status_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_status: Mapped[IncidentStatus | None] = mapped_column(
        Enum(IncidentStatus, name="incident_status", native_enum=False, create_constraint=False),
        nullable=True,
    )
    to_status: Mapped[IncidentStatus] = mapped_column(
        Enum(IncidentStatus, name="incident_status", native_enum=False, create_constraint=False),
        nullable=False,
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False, default="user")
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    incident: Mapped[Incident] = relationship(back_populates="status_history")


class Evidence(Base):
    __tablename__ = "evidence"
    __table_args__ = (
        Index("ix_evidence_incident", "incident_id", "observed_at"),
        UniqueConstraint(
            "incident_id",
            "source_type",
            "source_reference",
            "checksum",
            name="ux_evidence_dedup",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_type: Mapped[EvidenceSourceType] = mapped_column(
        Enum(EvidenceSourceType, name="evidence_source_type", native_enum=False),
        nullable=False,
    )
    source_reference: Mapped[str] = mapped_column(String(500), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    structured_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)

    incident: Mapped[Incident] = relationship(back_populates="evidence_items")


class Hypothesis(Base):
    __tablename__ = "hypotheses"
    __table_args__ = (Index("ix_hypotheses_incident", "incident_id", "confidence"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
    )
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[HypothesisStatus] = mapped_column(
        Enum(HypothesisStatus, name="hypothesis_status", native_enum=False),
        nullable=False,
        default=HypothesisStatus.PROPOSED,
    )
    supporting_evidence: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)),
        nullable=False,
        default=list,
    )
    contradicting_evidence: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)),
        nullable=False,
        default=list,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
    )

    incident: Mapped[Incident] = relationship(back_populates="hypotheses")
