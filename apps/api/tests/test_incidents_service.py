from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.core.errors import AppError
from app.incidents.models import (
    EvidenceSourceType,
    IncidentSeverity,
    IncidentSource,
    IncidentStatus,
    Service,
    ServiceEnvironment,
)
from app.incidents.service import (
    add_incident_note,
    compute_evidence_checksum,
    create_hypothesis,
    create_incident,
    create_service,
    delete_service,
    require_incident,
    require_service,
    update_incident_status,
    update_service,
    upsert_evidence,
)


@pytest.mark.asyncio
async def test_create_service_records_audit() -> None:
    session = AsyncMock()
    session.scalar = AsyncMock(return_value=None)
    session.add = MagicMock()
    session.flush = AsyncMock()
    actor = MagicMock(id=uuid.uuid4())

    service = await create_service(
        session,
        name="demo-service",
        description="Demo",
        repository=None,
        environment=ServiceEnvironment.DEMO,
        owner_team="platform",
        actor=actor,
        request_id="req-1",
    )
    assert service.name == "demo-service"
    session.add.assert_called()


@pytest.mark.asyncio
async def test_delete_service_with_incidents_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()
    service = Service(
        id=uuid.uuid4(),
        name="svc",
        environment=ServiceEnvironment.DEMO,
        is_active=True,
    )
    actor = MagicMock(id=uuid.uuid4())

    async def fake_count(*args, **kwargs):
        return 2

    monkeypatch.setattr("app.incidents.repository.count_incidents_for_service", fake_count)
    with pytest.raises(AppError, match="Cannot delete service"):
        await delete_service(session, service, actor=actor, request_id=None)


@pytest.mark.asyncio
async def test_create_incident_rejects_future_started_at() -> None:
    session = AsyncMock()
    actor = MagicMock(id=uuid.uuid4())
    future = datetime(2099, 1, 1, tzinfo=UTC)
    with pytest.raises(AppError, match="future"):
        await create_incident(
            session,
            title="Test",
            description="Test",
            severity=IncidentSeverity.SEV3,
            service_ids=[],
            started_at=future,
            source=IncidentSource.MANUAL,
            actor=actor,
            request_id=None,
        )


@pytest.mark.asyncio
async def test_update_incident_status_invalid_transition() -> None:
    session = AsyncMock()
    actor = MagicMock(id=uuid.uuid4(), role=MagicMock(value="operator"))
    incident = MagicMock(status=IncidentStatus.OPEN, id=uuid.uuid4(), resolved_at=None)
    with pytest.raises(AppError, match="Invalid transition"):
        await update_incident_status(
            session,
            incident,
            target_status=IncidentStatus.RESOLVED,
            reason=None,
            actor=actor,
            request_id=None,
        )


@pytest.mark.asyncio
async def test_upsert_evidence_deduplicates() -> None:
    session = AsyncMock()
    existing_id = uuid.uuid4()
    existing = MagicMock(id=existing_id)
    session.scalar = AsyncMock(return_value=existing)

    result = await upsert_evidence(
        session,
        incident_id=uuid.uuid4(),
        source_type=EvidenceSourceType.METRIC,
        source_reference="ref",
        title="Metric",
        content="value",
        structured_data={"metric_name": "errors", "value": 1.0},
        observed_at=datetime.now(UTC),
    )
    assert result.id == existing_id


@pytest.mark.asyncio
async def test_create_hypothesis_requires_supporting_evidence() -> None:
    session = AsyncMock()
    with pytest.raises(AppError, match="supporting evidence"):
        await create_hypothesis(
            session,
            incident_id=uuid.uuid4(),
            statement="Cause",
            confidence=0.5,
            supporting_evidence=[],
        )


def test_checksum_changes_with_content() -> None:
    a = compute_evidence_checksum("a", {})
    b = compute_evidence_checksum("b", {})
    assert a != b


@pytest.mark.asyncio
async def test_update_service_duplicate_name() -> None:
    session = AsyncMock()
    session.scalar = AsyncMock(
        return_value=Service(
            id=uuid.uuid4(),
            name="other",
            environment=ServiceEnvironment.DEMO,
            is_active=True,
        )
    )
    service = Service(
        id=uuid.uuid4(),
        name="demo",
        environment=ServiceEnvironment.DEMO,
        is_active=True,
    )
    actor = MagicMock(id=uuid.uuid4())
    with pytest.raises(AppError, match="already exists"):
        await update_service(
            session,
            service,
            name="other",
            description=None,
            repository=None,
            environment=None,
            owner_team=None,
            is_active=None,
            actor=actor,
            request_id=None,
        )


@pytest.mark.asyncio
async def test_create_incident_with_unknown_service() -> None:
    session = AsyncMock()
    session.scalar = AsyncMock(return_value=None)
    result = MagicMock()
    result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
    session.execute = AsyncMock(return_value=result)
    actor = MagicMock(id=uuid.uuid4())
    with pytest.raises(AppError, match="Unknown service_id"):
        await create_incident(
            session,
            title="Test",
            description="Test",
            severity=IncidentSeverity.SEV3,
            service_ids=[uuid.uuid4()],
            started_at=datetime.now(UTC),
            source=IncidentSource.MANUAL,
            actor=actor,
            request_id=None,
        )


@pytest.mark.asyncio
async def test_update_incident_status_success() -> None:
    session = AsyncMock()
    actor = MagicMock(id=uuid.uuid4(), role=MagicMock(value="operator"))
    incident = MagicMock(status=IncidentStatus.OPEN, id=uuid.uuid4(), resolved_at=None)
    updated = await update_incident_status(
        session,
        incident,
        target_status=IncidentStatus.INVESTIGATING,
        reason="Starting investigation",
        actor=actor,
        request_id="req-1",
    )
    assert updated.status == IncidentStatus.INVESTIGATING


@pytest.mark.asyncio
async def test_add_incident_note() -> None:
    session = AsyncMock()
    session.flush = AsyncMock()
    actor = MagicMock(id=uuid.uuid4())
    incident = MagicMock(id=uuid.uuid4())
    note = await add_incident_note(
        session, incident, content="Note body", actor=actor, request_id=None
    )
    assert note.content == "Note body"


@pytest.mark.asyncio
async def test_require_incident_not_found() -> None:
    session = AsyncMock()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("app.incidents.service.get_incident", AsyncMock(return_value=None))
        with pytest.raises(AppError, match="not found"):
            await require_incident(session, uuid.uuid4())


@pytest.mark.asyncio
async def test_delete_service_success(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()
    session.delete = AsyncMock()
    service = Service(
        id=uuid.uuid4(),
        name="svc",
        environment=ServiceEnvironment.DEMO,
        is_active=True,
    )
    actor = MagicMock(id=uuid.uuid4())
    monkeypatch.setattr(
        "app.incidents.repository.count_incidents_for_service",
        AsyncMock(return_value=0),
    )
    await delete_service(session, service, actor=actor, request_id=None)
    session.delete.assert_called_once_with(service)


@pytest.mark.asyncio
async def test_upsert_evidence_creates_new() -> None:
    session = AsyncMock()
    session.scalar = AsyncMock(return_value=None)
    session.add = MagicMock()
    session.flush = AsyncMock()
    evidence = await upsert_evidence(
        session,
        incident_id=uuid.uuid4(),
        source_type=EvidenceSourceType.LOG,
        source_reference="loki/query",
        title="Error log",
        content="stack trace",
        structured_data={"level": "error", "service": "demo"},
        observed_at=datetime.now(UTC),
    )
    assert evidence.title == "Error log"


@pytest.mark.asyncio
async def test_create_service_duplicate_name() -> None:
    session = AsyncMock()
    session.scalar = AsyncMock(
        return_value=Service(
            id=uuid.uuid4(),
            name="demo-service",
            environment=ServiceEnvironment.DEMO,
            is_active=True,
        )
    )
    actor = MagicMock(id=uuid.uuid4())
    with pytest.raises(AppError, match="already exists"):
        await create_service(
            session,
            name="demo-service",
            description=None,
            repository=None,
            environment=ServiceEnvironment.DEMO,
            owner_team=None,
            actor=actor,
            request_id=None,
        )


@pytest.mark.asyncio
async def test_create_hypothesis_with_valid_evidence() -> None:
    session = AsyncMock()
    evidence_id = uuid.uuid4()
    result = MagicMock()
    result.all = MagicMock(return_value=[(evidence_id,)])
    session.execute = AsyncMock(return_value=result)
    session.add = MagicMock()
    session.flush = AsyncMock()
    hypothesis = await create_hypothesis(
        session,
        incident_id=uuid.uuid4(),
        statement="Pool exhausted",
        confidence=0.8,
        supporting_evidence=[evidence_id],
    )
    assert hypothesis.statement == "Pool exhausted"


@pytest.mark.asyncio
async def test_require_service_not_found() -> None:
    session = AsyncMock()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("app.incidents.service.get_service", AsyncMock(return_value=None))
        with pytest.raises(AppError, match="not found"):
            await require_service(session, uuid.uuid4())
