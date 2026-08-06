from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.core.errors import AppError
from app.incidents.models import Incident, IncidentSeverity, IncidentSource, IncidentStatus
from app.investigation.models import AgentRun, AgentRunStatus
from app.investigation.service import (
    finalize_agent_run,
    get_active_run,
    list_agent_runs,
    load_incident_context,
    pause_investigation,
    resume_investigation,
    start_investigation,
)


def _incident(status: IncidentStatus = IncidentStatus.OPEN) -> Incident:
    return Incident(
        id=uuid.uuid4(),
        title="Test",
        description="desc",
        severity=IncidentSeverity.SEV2,
        status=status,
        source=IncidentSource.MANUAL,
        started_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_start_investigation_creates_agent_run() -> None:
    session = AsyncMock()
    session.flush = AsyncMock()
    incident = _incident()
    actor = MagicMock(id=uuid.uuid4())

    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=scalar_result)

    with (
        patch(
            "app.investigation.service.acquire_investigation_lock", new=AsyncMock(return_value=True)
        ),
        patch("app.investigation.service._enqueue_investigation", new=AsyncMock()),
        patch("app.investigation.service.update_incident_status", new=AsyncMock()),
        patch("app.investigation.service.record_audit_event", new=AsyncMock()),
    ):
        run = await start_investigation(session, incident=incident, actor=actor, request_id="req-1")

    assert run.status == AgentRunStatus.PENDING
    assert run.prompt_version == "v1"
    session.add.assert_called()


@pytest.mark.asyncio
async def test_start_investigation_rejects_active_run() -> None:
    session = AsyncMock()
    incident = _incident()
    actor = MagicMock(id=uuid.uuid4())
    existing = AgentRun(
        id=uuid.uuid4(),
        incident_id=incident.id,
        graph_thread_id="existing",
        status=AgentRunStatus.RUNNING,
        model="mock-v1",
        prompt_version="v1",
    )

    with (
        patch(
            "app.investigation.service.get_active_run",
            new=AsyncMock(return_value=existing),
        ),
        pytest.raises(AppError, match="active investigation"),
    ):
        await start_investigation(session, incident=incident, actor=actor, request_id=None)


@pytest.mark.asyncio
async def test_pause_and_resume_investigation() -> None:
    session = AsyncMock()
    session.flush = AsyncMock()
    incident = _incident(IncidentStatus.INVESTIGATING)
    actor = MagicMock(id=uuid.uuid4())
    run = AgentRun(
        id=uuid.uuid4(),
        incident_id=incident.id,
        graph_thread_id="thread",
        status=AgentRunStatus.RUNNING,
        model="mock-v1",
        prompt_version="v1",
    )

    with (
        patch("app.investigation.service.get_active_run", new=AsyncMock(return_value=run)),
        patch("app.investigation.service.record_audit_event", new=AsyncMock()),
    ):
        paused = await pause_investigation(session, incident=incident, actor=actor, request_id=None)
        assert paused.status == AgentRunStatus.PAUSED

    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none = MagicMock(return_value=run)
    session.execute = AsyncMock(return_value=scalar_result)

    with (
        patch("app.investigation.service._enqueue_investigation", new=AsyncMock()),
        patch("app.investigation.service.record_audit_event", new=AsyncMock()),
    ):
        resumed = await resume_investigation(
            session, incident=incident, actor=actor, request_id=None
        )
        assert resumed.status == AgentRunStatus.RUNNING


@pytest.mark.asyncio
async def test_get_active_run_returns_none_when_missing() -> None:
    session = AsyncMock()
    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=scalar_result)
    assert await get_active_run(session, uuid.uuid4()) is None


@pytest.mark.asyncio
async def test_get_active_run_returns_existing_run() -> None:
    session = AsyncMock()
    run = AgentRun(
        id=uuid.uuid4(),
        incident_id=uuid.uuid4(),
        graph_thread_id="thread",
        status=AgentRunStatus.RUNNING,
        model="mock-v1",
        prompt_version="v1",
    )
    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none = MagicMock(return_value=run)
    session.execute = AsyncMock(return_value=scalar_result)
    assert await get_active_run(session, run.incident_id) == run


@pytest.mark.asyncio
async def test_list_agent_runs_returns_rows() -> None:
    session = AsyncMock()
    incident_id = uuid.uuid4()
    run = AgentRun(
        id=uuid.uuid4(),
        incident_id=incident_id,
        graph_thread_id="thread",
        status=AgentRunStatus.COMPLETED,
        model="mock-v1",
        prompt_version="v1",
    )
    scalars = MagicMock()
    scalars.all = MagicMock(return_value=[run])
    result = MagicMock()
    result.scalars = MagicMock(return_value=scalars)
    session.execute = AsyncMock(return_value=result)
    rows = await list_agent_runs(session, incident_id)
    assert rows == [run]


@pytest.mark.asyncio
async def test_finalize_agent_run_persists_progress() -> None:
    session = AsyncMock()
    session.flush = AsyncMock()
    incident_id = uuid.uuid4()
    run = AgentRun(
        id=uuid.uuid4(),
        incident_id=incident_id,
        graph_thread_id="thread",
        status=AgentRunStatus.RUNNING,
        model="mock-v1",
        prompt_version="v1",
    )
    final_state = {
        "investigation_status": "completed",
        "token_usage": {"prompt_tokens": 3, "completion_tokens": 2},
        "completed_nodes": ["triage_incident"],
        "current_node": "close_investigation",
        "iteration_count": 1,
        "tool_call_count": 2,
        "errors": [],
    }
    with patch("app.investigation.service.release_investigation_lock", new=AsyncMock()):
        await finalize_agent_run(session, run, final_state=final_state)
    assert run.status == "completed"
    assert run.token_usage["prompt_tokens"] == 3
    assert run.node_progress["completed_nodes"] == ["triage_incident"]


@pytest.mark.asyncio
async def test_finalize_agent_run_records_errors() -> None:
    session = AsyncMock()
    session.flush = AsyncMock()
    run = AgentRun(
        id=uuid.uuid4(),
        incident_id=uuid.uuid4(),
        graph_thread_id="thread",
        status=AgentRunStatus.RUNNING,
        model="mock-v1",
        prompt_version="v1",
    )
    with patch("app.investigation.service.release_investigation_lock", new=AsyncMock()):
        await finalize_agent_run(
            session,
            run,
            final_state={"investigation_status": "failed", "errors": ["e1", "e2"]},
        )
    assert run.error == "e1; e2"


@pytest.mark.asyncio
async def test_start_investigation_rejects_lock_contention() -> None:
    session = AsyncMock()
    incident = _incident()
    actor = MagicMock(id=uuid.uuid4())

    with (
        patch("app.investigation.service.get_active_run", new=AsyncMock(return_value=None)),
        patch(
            "app.investigation.service.acquire_investigation_lock",
            new=AsyncMock(return_value=False),
        ),
        pytest.raises(AppError, match="lock"),
    ):
        await start_investigation(session, incident=incident, actor=actor, request_id=None)


@pytest.mark.asyncio
async def test_pause_investigation_requires_running_run() -> None:
    session = AsyncMock()
    incident = _incident(IncidentStatus.INVESTIGATING)
    actor = MagicMock(id=uuid.uuid4())

    with (
        patch("app.investigation.service.get_active_run", new=AsyncMock(return_value=None)),
        pytest.raises(AppError, match="No running investigation"),
    ):
        await pause_investigation(session, incident=incident, actor=actor, request_id=None)


@pytest.mark.asyncio
async def test_resume_investigation_requires_paused_run() -> None:
    session = AsyncMock()
    incident = _incident(IncidentStatus.INVESTIGATING)
    actor = MagicMock(id=uuid.uuid4())
    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=scalar_result)

    with pytest.raises(AppError, match="No paused investigation"):
        await resume_investigation(session, incident=incident, actor=actor, request_id=None)


@pytest.mark.asyncio
async def test_start_investigation_skips_status_change_when_already_investigating() -> None:
    session = AsyncMock()
    session.flush = AsyncMock()
    incident = _incident(IncidentStatus.INVESTIGATING)
    actor = MagicMock(id=uuid.uuid4())

    with (
        patch("app.investigation.service.get_active_run", new=AsyncMock(return_value=None)),
        patch(
            "app.investigation.service.acquire_investigation_lock", new=AsyncMock(return_value=True)
        ),
        patch("app.investigation.service._enqueue_investigation", new=AsyncMock()),
        patch("app.investigation.service.update_incident_status", new=AsyncMock()) as status_update,
        patch("app.investigation.service.record_audit_event", new=AsyncMock()),
    ):
        run = await start_investigation(session, incident=incident, actor=actor, request_id=None)

    status_update.assert_not_called()
    assert run.incident_id == incident.id


@pytest.mark.asyncio
async def test_start_investigation_rejects_invalid_status() -> None:
    session = AsyncMock()
    incident = _incident(IncidentStatus.RESOLVED)
    actor = MagicMock(id=uuid.uuid4())

    with pytest.raises(AppError, match="Cannot start investigation"):
        await start_investigation(session, incident=incident, actor=actor, request_id=None)


@pytest.mark.asyncio
async def test_load_incident_context_includes_services() -> None:
    session = AsyncMock()
    incident_id = uuid.uuid4()
    service_id = uuid.uuid4()
    incident = Incident(
        id=incident_id,
        title="Outage",
        description="Errors",
        severity=IncidentSeverity.SEV2,
        status=IncidentStatus.INVESTIGATING,
        source=IncidentSource.MANUAL,
        started_at=datetime.now(UTC),
    )
    link = MagicMock(service_id=service_id)
    incident.service_links = [link]
    service = MagicMock(repository="org/repo")
    service.name = "demo-service"

    scalars = MagicMock()
    scalars.all = MagicMock(return_value=[service])
    result = MagicMock()
    result.scalars = MagicMock(return_value=scalars)
    session.execute = AsyncMock(return_value=result)

    with patch("app.investigation.service.require_incident", new=AsyncMock(return_value=incident)):
        context = await load_incident_context(session, incident_id)

    assert context["service_names"] == ["demo-service"]
    assert context["repository"] == "org/repo"
