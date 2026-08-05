from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_capability
from app.auth.models import User
from app.auth.policy import Capability
from app.core.errors import AppError
from app.db.session import get_session
from app.incidents import repository, service
from app.incidents.models import (
    Evidence,
    Hypothesis,
    Incident,
    IncidentSeverity,
    IncidentStatus,
    Service,
)
from app.incidents.schemas import (
    EvidenceListResponse,
    EvidenceRead,
    HypothesisListResponse,
    HypothesisRead,
    IncidentCreate,
    IncidentListResponse,
    IncidentNoteCreate,
    IncidentRead,
    IncidentStatusUpdate,
    ServiceCreate,
    ServiceRead,
    ServiceUpdate,
    TimelineEntryRead,
    TimelineResponse,
)
from app.incidents.timeline import assemble_timeline

router = APIRouter(tags=["incidents"])


def _service_to_read(svc: Service) -> ServiceRead:
    return ServiceRead(
        id=str(svc.id),
        name=svc.name,
        description=svc.description,
        repository=svc.repository,
        environment=svc.environment,
        owner_team=svc.owner_team,
        is_active=svc.is_active,
        created_at=svc.created_at,
        updated_at=svc.updated_at,
    )


def _incident_to_read(incident: Incident) -> IncidentRead:
    return IncidentRead(
        id=str(incident.id),
        title=incident.title,
        description=incident.description,
        severity=incident.severity,
        status=incident.status,
        source=incident.source,
        started_at=incident.started_at,
        resolved_at=incident.resolved_at,
        created_by=str(incident.created_by) if incident.created_by else None,
        service_ids=[str(link.service_id) for link in incident.service_links],
        created_at=incident.created_at,
        updated_at=incident.updated_at,
    )


def _evidence_to_read(evidence: Evidence) -> EvidenceRead:
    return EvidenceRead(
        id=str(evidence.id),
        incident_id=str(evidence.incident_id),
        source_type=evidence.source_type.value,
        source_reference=evidence.source_reference,
        title=evidence.title,
        content=evidence.content,
        structured_data=evidence.structured_data,
        observed_at=evidence.observed_at,
        collected_at=evidence.collected_at,
        relevance_score=evidence.relevance_score,
    )


def _hypothesis_to_read(hypothesis: Hypothesis) -> HypothesisRead:
    return HypothesisRead(
        id=str(hypothesis.id),
        incident_id=str(hypothesis.incident_id),
        statement=hypothesis.statement,
        confidence=hypothesis.confidence,
        status=hypothesis.status.value,
        supporting_evidence=[str(eid) for eid in hypothesis.supporting_evidence],
        contradicting_evidence=[str(eid) for eid in hypothesis.contradicting_evidence],
        created_at=hypothesis.created_at,
        updated_at=hypothesis.updated_at,
    )


# --- Services (admin) ---


@router.get("/services", response_model=list[ServiceRead])
async def list_services(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(require_capability(Capability.READ_INCIDENTS))],
    include_inactive: bool = False,
) -> list[ServiceRead]:
    services = await repository.list_services(session, include_inactive=include_inactive)
    return [_service_to_read(svc) for svc in services]


@router.post("/services", response_model=ServiceRead, status_code=201)
async def create_service(
    request: Request,
    body: ServiceCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_capability(Capability.MANAGE_USERS))],
) -> ServiceRead:
    svc = await service.create_service(
        session,
        name=body.name,
        description=body.description,
        repository=body.repository,
        environment=body.environment,
        owner_team=body.owner_team,
        actor=actor,
        request_id=getattr(request.state, "request_id", None),
    )
    await session.commit()
    await session.refresh(svc)
    return _service_to_read(svc)


@router.patch("/services/{service_id}", response_model=ServiceRead)
async def update_service(
    request: Request,
    service_id: UUID,
    body: ServiceUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_capability(Capability.MANAGE_USERS))],
) -> ServiceRead:
    svc = await service.require_service(session, service_id)
    svc = await service.update_service(
        session,
        svc,
        name=body.name,
        description=body.description,
        repository=body.repository,
        environment=body.environment,
        owner_team=body.owner_team,
        is_active=body.is_active,
        actor=actor,
        request_id=getattr(request.state, "request_id", None),
    )
    await session.commit()
    await session.refresh(svc)
    return _service_to_read(svc)


@router.delete("/services/{service_id}", status_code=204, response_class=Response)
async def delete_service(
    request: Request,
    service_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_capability(Capability.MANAGE_USERS))],
) -> Response:
    svc = await service.require_service(session, service_id)
    await service.delete_service(
        session,
        svc,
        actor=actor,
        request_id=getattr(request.state, "request_id", None),
    )
    await session.commit()
    return Response(status_code=204)


# --- Incidents ---


@router.get("/incidents", response_model=IncidentListResponse)
async def list_incidents(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(require_capability(Capability.READ_INCIDENTS))],
    status: IncidentStatus | None = None,
    severity: IncidentSeverity | None = None,
    service_id: UUID | None = None,
    started_from: Annotated[str | None, Query(alias="from")] = None,
    started_to: Annotated[str | None, Query(alias="to")] = None,
    search: str | None = None,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
) -> IncidentListResponse:
    from datetime import datetime

    page = await repository.list_incidents(
        session,
        status=status,
        severity=severity,
        service_id=service_id,
        started_from=datetime.fromisoformat(started_from) if started_from else None,
        started_to=datetime.fromisoformat(started_to) if started_to else None,
        search=search,
        cursor=cursor,
        limit=limit,
    )
    return IncidentListResponse(
        items=[_incident_to_read(inc) for inc in page.items],
        next_cursor=page.next_cursor,
        total_estimate=page.total_estimate,
    )


@router.post("/incidents", response_model=IncidentRead, status_code=201)
async def create_incident(
    request: Request,
    body: IncidentCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_capability(Capability.CREATE_INCIDENTS))],
) -> IncidentRead:
    incident = await service.create_incident(
        session,
        title=body.title,
        description=body.description,
        severity=body.severity,
        service_ids=list(body.service_ids),
        started_at=body.started_at,
        source=body.source,
        actor=actor,
        request_id=getattr(request.state, "request_id", None),
    )
    await session.commit()
    incident = await service.require_incident(session, incident.id)
    return _incident_to_read(incident)


@router.get("/incidents/{incident_id}", response_model=IncidentRead)
async def get_incident(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(require_capability(Capability.READ_INCIDENTS))],
    incident_id: UUID,
) -> IncidentRead:
    incident = await service.require_incident(session, incident_id)
    return _incident_to_read(incident)


@router.patch("/incidents/{incident_id}", response_model=IncidentRead)
async def update_incident_status(
    request: Request,
    incident_id: UUID,
    body: IncidentStatusUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_capability(Capability.MANAGE_INVESTIGATION))],
) -> IncidentRead:
    incident = await service.require_incident(session, incident_id)
    incident = await service.update_incident_status(
        session,
        incident,
        target_status=body.status,
        reason=body.reason,
        actor=actor,
        request_id=getattr(request.state, "request_id", None),
    )
    await session.commit()
    incident = await service.require_incident(session, incident.id)
    return _incident_to_read(incident)


@router.get("/incidents/{incident_id}/timeline", response_model=TimelineResponse)
async def get_incident_timeline(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(require_capability(Capability.READ_INCIDENTS))],
    incident_id: UUID,
) -> TimelineResponse:
    await service.require_incident(session, incident_id)
    entries = await assemble_timeline(session, incident_id)
    return TimelineResponse(
        items=[
            TimelineEntryRead(
                id=str(entry.id),
                occurred_at=entry.occurred_at,
                kind=entry.kind,
                actor_type=entry.actor_type,
                actor_id=str(entry.actor_id) if entry.actor_id else None,
                title=entry.title,
                description=entry.description,
                reference=entry.reference,
            )
            for entry in entries
        ]
    )


@router.post("/incidents/{incident_id}/notes", status_code=201)
async def add_incident_note(
    request: Request,
    incident_id: UUID,
    body: IncidentNoteCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_capability(Capability.MANAGE_INVESTIGATION))],
) -> TimelineEntryRead:
    incident = await service.require_incident(session, incident_id)
    note = await service.add_incident_note(
        session,
        incident,
        content=body.content,
        actor=actor,
        request_id=getattr(request.state, "request_id", None),
    )
    await session.commit()
    return TimelineEntryRead(
        id=str(note.id),
        occurred_at=note.created_at,
        kind="note",
        actor_type=note.actor_type,
        actor_id=str(note.actor_id) if note.actor_id else None,
        title="Manual note",
        description=note.content,
        reference={"note_id": str(note.id)},
    )


@router.get("/incidents/{incident_id}/evidence", response_model=EvidenceListResponse)
async def list_incident_evidence(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(require_capability(Capability.READ_INCIDENTS))],
    incident_id: UUID,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
) -> EvidenceListResponse:
    await service.require_incident(session, incident_id)
    try:
        page = await repository.list_evidence(session, incident_id, cursor=cursor, limit=limit)
    except ValueError as exc:
        raise AppError(str(exc), status_code=400) from exc
    return EvidenceListResponse(
        items=[_evidence_to_read(item) for item in page.items],
        next_cursor=page.next_cursor,
        total_estimate=page.total_estimate,
    )


@router.get("/incidents/{incident_id}/hypotheses", response_model=HypothesisListResponse)
async def list_incident_hypotheses(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(require_capability(Capability.READ_INCIDENTS))],
    incident_id: UUID,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
) -> HypothesisListResponse:
    await service.require_incident(session, incident_id)
    try:
        page = await repository.list_hypotheses(session, incident_id, cursor=cursor, limit=limit)
    except ValueError as exc:
        raise AppError(str(exc), status_code=400) from exc
    return HypothesisListResponse(
        items=[_hypothesis_to_read(item) for item in page.items],
        next_cursor=page.next_cursor,
        total_estimate=page.total_estimate,
    )
