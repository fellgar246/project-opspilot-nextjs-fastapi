from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from arq import create_pool
from arq.connections import RedisSettings
from opspilot.agent.config import get_agent_settings
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.event_types import AuditEventType
from app.audit.service import record_audit_event
from app.auth.models import User
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.redis import get_redis
from app.incidents.models import Incident, IncidentStatus, Service
from app.incidents.service import require_incident, update_incident_status
from app.investigation.lock import acquire_investigation_lock, release_investigation_lock
from app.investigation.models import AgentRun, AgentRunStatus

ACTIVE_STATUSES = {
    AgentRunStatus.PENDING,
    AgentRunStatus.RUNNING,
    AgentRunStatus.PAUSED,
    AgentRunStatus.AWAITING_APPROVAL,
}


async def get_active_run(session: AsyncSession, incident_id: uuid.UUID) -> AgentRun | None:
    result = await session.execute(
        select(AgentRun).where(
            AgentRun.incident_id == incident_id,
            AgentRun.status.in_(list(ACTIVE_STATUSES)),
        )
    )
    return result.scalar_one_or_none()


async def list_agent_runs(session: AsyncSession, incident_id: uuid.UUID) -> list[AgentRun]:
    result = await session.execute(
        select(AgentRun)
        .where(AgentRun.incident_id == incident_id)
        .order_by(AgentRun.created_at.desc())
    )
    return list(result.scalars().all())


async def start_investigation(
    session: AsyncSession,
    *,
    incident: Incident,
    actor: User,
    request_id: str | None,
) -> AgentRun:
    if incident.status not in {IncidentStatus.OPEN, IncidentStatus.INVESTIGATING}:
        raise AppError(
            f"Cannot start investigation from status '{incident.status.value}'",
            status_code=409,
        )

    active = await get_active_run(session, incident.id)
    if active is not None:
        raise AppError("An active investigation already exists for this incident", status_code=409)

    settings = get_settings()
    agent_settings = get_agent_settings()
    agent_run_id = uuid.uuid4()
    graph_thread_id = f"inv-{incident.id}-{agent_run_id.hex[:12]}"

    acquired = await acquire_investigation_lock(
        get_redis(),
        incident_id=incident.id,
        agent_run_id=agent_run_id,
    )
    if not acquired:
        raise AppError("Investigation lock already held for this incident", status_code=409)

    model_name = (
        agent_settings.openai_model if agent_settings.model_provider == "openai" else "mock-v1"
    )
    agent_run = AgentRun(
        id=agent_run_id,
        incident_id=incident.id,
        graph_thread_id=graph_thread_id,
        status=AgentRunStatus.PENDING,
        model=model_name,
        prompt_version=agent_settings.prompt_version,
    )
    session.add(agent_run)
    await session.flush()

    if incident.status == IncidentStatus.OPEN:
        await update_incident_status(
            session,
            incident,
            target_status=IncidentStatus.INVESTIGATING,
            reason="Investigation started",
            actor=actor,
            request_id=request_id,
        )

    await record_audit_event(
        session,
        actor_type="agent",
        actor_id=agent_run_id,
        event_type=AuditEventType.INVESTIGATION_STARTED,
        entity_type="incident",
        entity_id=incident.id,
        payload={"agent_run_id": str(agent_run_id), "graph_thread_id": graph_thread_id},
        request_id=request_id,
    )

    await _enqueue_investigation(agent_run_id, settings)
    return agent_run


async def pause_investigation(
    session: AsyncSession,
    *,
    incident: Incident,
    actor: User,
    request_id: str | None,
) -> AgentRun:
    agent_run = await get_active_run(session, incident.id)
    if agent_run is None or agent_run.status not in {
        AgentRunStatus.RUNNING,
        AgentRunStatus.PENDING,
    }:
        raise AppError("No running investigation to pause", status_code=409)

    agent_run.status = AgentRunStatus.PAUSED
    await session.flush()

    await record_audit_event(
        session,
        actor_type="agent",
        actor_id=agent_run.id,
        event_type=AuditEventType.INVESTIGATION_PAUSED,
        entity_type="incident",
        entity_id=incident.id,
        payload={"agent_run_id": str(agent_run.id)},
        request_id=request_id,
    )
    return agent_run


async def resume_investigation(
    session: AsyncSession,
    *,
    incident: Incident,
    actor: User,
    request_id: str | None,
) -> AgentRun:
    result = await session.execute(
        select(AgentRun).where(
            AgentRun.incident_id == incident.id,
            AgentRun.status == AgentRunStatus.PAUSED,
        )
    )
    agent_run = result.scalar_one_or_none()
    if agent_run is None:
        raise AppError("No paused investigation to resume", status_code=409)

    agent_run.status = AgentRunStatus.RUNNING
    await session.flush()

    await record_audit_event(
        session,
        actor_type="agent",
        actor_id=agent_run.id,
        event_type=AuditEventType.INVESTIGATION_RESUMED,
        entity_type="incident",
        entity_id=incident.id,
        payload={"agent_run_id": str(agent_run.id)},
        request_id=request_id,
    )

    await _enqueue_investigation(agent_run.id, get_settings())
    return agent_run


async def finalize_agent_run(
    session: AsyncSession,
    agent_run: AgentRun,
    *,
    final_state: dict[str, Any],
) -> None:
    status = final_state.get("investigation_status", AgentRunStatus.COMPLETED)
    agent_run.status = status
    agent_run.completed_at = datetime.now(UTC)
    agent_run.token_usage = final_state.get("token_usage") or {}
    agent_run.node_progress = {
        "completed_nodes": final_state.get("completed_nodes") or [],
        "current_node": final_state.get("current_node"),
        "iteration_count": final_state.get("iteration_count", 0),
        "tool_call_count": final_state.get("tool_call_count", 0),
    }
    errors = final_state.get("errors") or []
    if errors:
        agent_run.error = "; ".join(errors[:5])
    await release_investigation_lock(get_redis(), incident_id=agent_run.incident_id)
    await session.flush()


async def load_incident_context(session: AsyncSession, incident_id: uuid.UUID) -> dict[str, Any]:
    incident = await require_incident(session, incident_id)
    service_names: list[str] = []
    repository: str | None = None
    if incident.service_links:
        service_ids = [link.service_id for link in incident.service_links]
        result = await session.execute(select(Service).where(Service.id.in_(service_ids)))
        services = list(result.scalars().all())
        service_names = [svc.name for svc in services]
        repository = next((svc.repository for svc in services if svc.repository), None)

    return {
        "id": str(incident.id),
        "title": incident.title,
        "description": incident.description,
        "severity": incident.severity.value,
        "service_names": service_names,
        "repository": repository,
        "started_at": incident.started_at.isoformat(),
    }


async def _enqueue_investigation(agent_run_id: uuid.UUID, settings: Settings) -> None:
    redis_settings = RedisSettings.from_dsn(str(settings.redis_url))
    pool = await create_pool(redis_settings)
    try:
        await pool.enqueue_job("investigate_incident", str(agent_run_id))
    finally:
        await pool.aclose()
