from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from opspilot.schemas.evidence import validate_structured_data
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.event_types import AuditEventType
from app.audit.service import record_audit_event
from app.auth.models import User, UserRole
from app.core.errors import AppError
from app.incidents.models import (
    Evidence,
    EvidenceSourceType,
    Hypothesis,
    HypothesisStatus,
    Incident,
    IncidentNote,
    IncidentService,
    IncidentSeverity,
    IncidentSource,
    IncidentStatus,
    IncidentStatusHistory,
    Service,
    ServiceEnvironment,
)
from app.incidents.repository import get_incident, get_service
from app.incidents.state_machine import allowed_transitions, can_transition


def compute_evidence_checksum(content: str, structured_data: dict[str, Any]) -> str:
    normalized = json.dumps(
        {"content": content.strip(), "structured_data": structured_data},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(normalized.encode()).hexdigest()


async def _validate_service_ids(
    session: AsyncSession,
    service_ids: list[uuid.UUID],
) -> list[Service]:
    if not service_ids:
        return []
    result = await session.execute(select(Service).where(Service.id.in_(service_ids)))
    services = {service.id: service for service in result.scalars().all()}
    missing = [str(sid) for sid in service_ids if sid not in services]
    if missing:
        raise AppError(f"Unknown service_id(s): {', '.join(missing)}", status_code=422)
    inactive = [str(sid) for sid in service_ids if not services[sid].is_active]
    if inactive:
        raise AppError(f"Inactive service_id(s): {', '.join(inactive)}", status_code=422)
    return [services[sid] for sid in service_ids]


async def create_service(
    session: AsyncSession,
    *,
    name: str,
    description: str | None,
    repository: str | None,
    environment: ServiceEnvironment,
    owner_team: str | None,
    actor: User,
    request_id: str | None,
) -> Service:
    existing = await session.scalar(select(Service).where(Service.name == name))
    if existing is not None:
        raise AppError(f"Service name already exists: {name}", status_code=409)

    service = Service(
        name=name,
        description=description,
        repository=repository,
        environment=environment,
        owner_team=owner_team,
        is_active=True,
    )
    session.add(service)
    await session.flush()

    await record_audit_event(
        session,
        actor_type="user",
        actor_id=actor.id,
        event_type=AuditEventType.SERVICE_CREATED,
        entity_type="service",
        entity_id=service.id,
        payload={"name": name, "environment": environment.value},
        request_id=request_id,
    )
    return service


async def update_service(
    session: AsyncSession,
    service: Service,
    *,
    name: str | None,
    description: str | None,
    repository: str | None,
    environment: ServiceEnvironment | None,
    owner_team: str | None,
    is_active: bool | None,
    actor: User,
    request_id: str | None,
) -> Service:
    changes: dict[str, Any] = {}
    if name is not None and name != service.name:
        existing = await session.scalar(select(Service).where(Service.name == name))
        if existing is not None:
            raise AppError(f"Service name already exists: {name}", status_code=409)
        changes["name"] = {"from": service.name, "to": name}
        service.name = name
    if description is not None:
        changes["description"] = description
        service.description = description
    if repository is not None:
        changes["repository"] = repository
        service.repository = repository
    if environment is not None:
        changes["environment"] = environment.value
        service.environment = environment
    if owner_team is not None:
        changes["owner_team"] = owner_team
        service.owner_team = owner_team
    if is_active is not None:
        changes["is_active"] = is_active
        service.is_active = is_active

    await record_audit_event(
        session,
        actor_type="user",
        actor_id=actor.id,
        event_type=AuditEventType.SERVICE_UPDATED,
        entity_type="service",
        entity_id=service.id,
        payload=changes,
        request_id=request_id,
    )
    return service


async def delete_service(
    session: AsyncSession,
    service: Service,
    *,
    actor: User,
    request_id: str | None,
) -> None:
    from app.incidents.repository import count_incidents_for_service

    count = await count_incidents_for_service(session, service.id)
    if count > 0:
        raise AppError(
            f"Cannot delete service with {count} associated incident(s). Deactivate it instead.",
            status_code=409,
        )
    await record_audit_event(
        session,
        actor_type="user",
        actor_id=actor.id,
        event_type=AuditEventType.SERVICE_DEACTIVATED,
        entity_type="service",
        entity_id=service.id,
        payload={"name": service.name, "deleted": True},
        request_id=request_id,
    )
    await session.delete(service)


async def create_incident(
    session: AsyncSession,
    *,
    title: str,
    description: str,
    severity: IncidentSeverity,
    service_ids: list[uuid.UUID],
    started_at: datetime,
    source: IncidentSource,
    actor: User,
    request_id: str | None,
) -> Incident:
    now = datetime.now(UTC)
    if started_at > now:
        raise AppError("started_at cannot be in the future", status_code=422)

    services = await _validate_service_ids(session, service_ids)

    incident = Incident(
        title=title,
        description=description,
        severity=severity,
        status=IncidentStatus.OPEN,
        source=source,
        started_at=started_at,
        created_by=actor.id,
    )
    session.add(incident)
    await session.flush()

    for service in services:
        session.add(IncidentService(incident_id=incident.id, service_id=service.id))

    session.add(
        IncidentStatusHistory(
            incident_id=incident.id,
            from_status=None,
            to_status=IncidentStatus.OPEN,
            reason="Incident created",
            actor_type="user",
            actor_id=actor.id,
            occurred_at=now,
        )
    )

    await record_audit_event(
        session,
        actor_type="user",
        actor_id=actor.id,
        event_type=AuditEventType.INCIDENT_CREATED,
        entity_type="incident",
        entity_id=incident.id,
        payload={
            "title": title,
            "severity": severity.value,
            "status": IncidentStatus.OPEN.value,
            "service_ids": [str(sid) for sid in service_ids],
        },
        request_id=request_id,
    )
    return incident


async def update_incident_status(
    session: AsyncSession,
    incident: Incident,
    *,
    target_status: IncidentStatus,
    reason: str | None,
    actor: User,
    request_id: str | None,
) -> Incident:
    is_admin = actor.role == UserRole.ADMIN
    if not can_transition(incident.status, target_status, is_admin=is_admin):
        valid = sorted(s.value for s in allowed_transitions(incident.status, is_admin=is_admin))
        raise AppError(
            f"Invalid transition from '{incident.status.value}' to '{target_status.value}'. "
            f"Valid transitions: {', '.join(valid) or 'none'}",
            status_code=409,
        )

    from_status = incident.status
    incident.status = target_status
    if target_status == IncidentStatus.RESOLVED and incident.resolved_at is None:
        incident.resolved_at = datetime.now(UTC)

    session.add(
        IncidentStatusHistory(
            incident_id=incident.id,
            from_status=from_status,
            to_status=target_status,
            reason=reason,
            actor_type="user",
            actor_id=actor.id,
        )
    )

    await record_audit_event(
        session,
        actor_type="user",
        actor_id=actor.id,
        event_type=AuditEventType.INCIDENT_UPDATED,
        entity_type="incident",
        entity_id=incident.id,
        payload={
            "from_status": from_status.value,
            "to_status": target_status.value,
            "reason": reason,
        },
        request_id=request_id,
    )
    return incident


async def add_incident_note(
    session: AsyncSession,
    incident: Incident,
    *,
    content: str,
    actor: User,
    request_id: str | None,
) -> IncidentNote:
    note = IncidentNote(
        incident_id=incident.id,
        content=content,
        actor_type="user",
        actor_id=actor.id,
    )
    session.add(note)
    await session.flush()

    await record_audit_event(
        session,
        actor_type="user",
        actor_id=actor.id,
        event_type=AuditEventType.INCIDENT_UPDATED,
        entity_type="incident",
        entity_id=incident.id,
        payload={"note_id": str(note.id), "action": "note_added"},
        request_id=request_id,
    )
    return note


async def upsert_evidence(
    session: AsyncSession,
    *,
    incident_id: uuid.UUID,
    source_type: EvidenceSourceType,
    source_reference: str,
    title: str,
    content: str,
    structured_data: dict[str, Any],
    observed_at: datetime,
    relevance_score: float | None = None,
) -> Evidence:
    try:
        validate_structured_data(source_type.value, structured_data)
    except ValueError as exc:
        raise AppError(str(exc), status_code=422) from exc
    checksum = compute_evidence_checksum(content, structured_data)

    existing = await session.scalar(
        select(Evidence).where(
            Evidence.incident_id == incident_id,
            Evidence.source_type == source_type,
            Evidence.source_reference == source_reference,
            Evidence.checksum == checksum,
        )
    )
    if existing is not None:
        return existing

    evidence = Evidence(
        incident_id=incident_id,
        source_type=source_type,
        source_reference=source_reference,
        title=title,
        content=content,
        structured_data=structured_data,
        observed_at=observed_at,
        relevance_score=relevance_score,
        checksum=checksum,
    )
    session.add(evidence)
    await session.flush()
    return evidence


async def create_hypothesis(
    session: AsyncSession,
    *,
    incident_id: uuid.UUID,
    statement: str,
    confidence: float,
    supporting_evidence: list[uuid.UUID],
    contradicting_evidence: list[uuid.UUID] | None = None,
    status: HypothesisStatus = HypothesisStatus.PROPOSED,
    confidence_breakdown: dict[str, Any] | None = None,
    grounding: str | None = None,
    critic_verdict: str | None = None,
    assumptions: list[str] | None = None,
    missing_evidence: list[str] | None = None,
    rejection_reason: str | None = None,
    hypothesis_type: str | None = None,
) -> Hypothesis:
    if not supporting_evidence:
        raise AppError("Hypothesis requires at least one supporting evidence", status_code=422)

    all_evidence_ids = set(supporting_evidence) | set(contradicting_evidence or [])
    result = await session.execute(
        select(Evidence.id).where(
            Evidence.incident_id == incident_id,
            Evidence.id.in_(all_evidence_ids),
        )
    )
    found = {row[0] for row in result.all()}
    missing = all_evidence_ids - found
    if missing:
        raise AppError(
            f"Unknown evidence_id(s) for incident: {', '.join(str(m) for m in missing)}",
            status_code=422,
        )

    hypothesis = Hypothesis(
        incident_id=incident_id,
        statement=statement,
        confidence=confidence,
        status=status,
        supporting_evidence=supporting_evidence,
        contradicting_evidence=contradicting_evidence or [],
        confidence_breakdown=confidence_breakdown or {},
        grounding=grounding,
        critic_verdict=critic_verdict,
        assumptions=assumptions or [],
        missing_evidence=missing_evidence or [],
        rejection_reason=rejection_reason,
        hypothesis_type=hypothesis_type,
    )
    session.add(hypothesis)
    await session.flush()
    return hypothesis


async def require_incident(session: AsyncSession, incident_id: uuid.UUID) -> Incident:
    incident = await get_incident(session, incident_id)
    if incident is None:
        raise AppError("Incident not found", status_code=404)
    return incident


async def require_service(session: AsyncSession, service_id: uuid.UUID) -> Service:
    service = await get_service(session, service_id)
    if service is None:
        raise AppError("Service not found", status_code=404)
    return service
