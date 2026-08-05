from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.incidents.models import (
    IncidentSeverity,
    IncidentSource,
    IncidentStatus,
    ServiceEnvironment,
)


class ServiceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    repository: str | None = Field(default=None, max_length=500)
    environment: ServiceEnvironment
    owner_team: str | None = Field(default=None, max_length=200)


class ServiceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    repository: str | None = Field(default=None, max_length=500)
    environment: ServiceEnvironment | None = None
    owner_team: str | None = Field(default=None, max_length=200)
    is_active: bool | None = None


class ServiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None
    repository: str | None
    environment: ServiceEnvironment
    owner_team: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class IncidentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str = Field(min_length=1)
    severity: IncidentSeverity
    service_ids: list[UUID] = Field(default_factory=list)
    started_at: datetime
    source: IncidentSource = IncidentSource.MANUAL


class IncidentStatusUpdate(BaseModel):
    status: IncidentStatus
    reason: str | None = None


class IncidentNoteCreate(BaseModel):
    content: str = Field(min_length=1)


class IncidentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    description: str
    severity: IncidentSeverity
    status: IncidentStatus
    source: IncidentSource
    started_at: datetime
    resolved_at: datetime | None
    created_by: str | None
    service_ids: list[str]
    created_at: datetime
    updated_at: datetime


class IncidentListResponse(BaseModel):
    items: list[IncidentRead]
    next_cursor: str | None
    total_estimate: int


class TimelineEntryRead(BaseModel):
    id: str
    occurred_at: datetime
    kind: str
    actor_type: str
    actor_id: str | None
    title: str
    description: str | None
    reference: dict[str, Any] | None


class TimelineResponse(BaseModel):
    items: list[TimelineEntryRead]


class EvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    incident_id: str
    source_type: str
    source_reference: str
    title: str
    content: str
    structured_data: dict[str, Any]
    observed_at: datetime
    collected_at: datetime
    relevance_score: float | None


class EvidenceListResponse(BaseModel):
    items: list[EvidenceRead]
    next_cursor: str | None
    total_estimate: int


class HypothesisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    incident_id: str
    statement: str
    confidence: float
    status: str
    supporting_evidence: list[str]
    contradicting_evidence: list[str]
    created_at: datetime
    updated_at: datetime


class HypothesisListResponse(BaseModel):
    items: list[HypothesisRead]
    next_cursor: str | None
    total_estimate: int
