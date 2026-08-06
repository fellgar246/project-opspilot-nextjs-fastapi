from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from opspilot.tools.base import ToolContext, ToolRole
from opspilot.tools.normalize import normalize_to_evidence
from opspilot.tools.read.schemas import ServiceHealthOutput, ServiceInput


def test_evidence_dedup_by_checksum() -> None:
    ctx = ToolContext(
        incident_id=uuid4(),
        agent_run_id=uuid4(),
        actor_type="agent",
        actor_id=uuid4(),
        role=ToolRole.OPERATOR,
        request_id="req-1",
    )
    payload = ServiceInput(service="demo-service")
    output = ServiceHealthOutput(
        service="demo-service",
        status="healthy",
        version="v1",
        dependencies=[{"name": "redis", "status": "healthy"}],
    )
    collected = datetime.now(UTC)
    first, ids1 = normalize_to_evidence(
        tool_name="get_service_health",
        payload=payload,
        output=output,
        ctx=ctx,
        collected_at=collected,
    )
    checksums = {record.checksum for record in first}
    second, ids2 = normalize_to_evidence(
        tool_name="get_service_health",
        payload=payload,
        output=output,
        ctx=ctx,
        collected_at=collected,
        existing_checksums=checksums,
    )
    assert len(first) == 1
    assert len(second) == 0
    assert ids1
    assert ids2 == []


def test_observed_at_differs_from_collected_at() -> None:
    ctx = ToolContext(
        incident_id=uuid4(),
        agent_run_id=None,
        actor_type="agent",
        actor_id=uuid4(),
        role=ToolRole.VIEWER,
        request_id="req-2",
    )
    from opspilot.tools.read.schemas import CommitsInput, CommitsOutput, CommitSummary

    payload = CommitsInput(
        repository="simulator/data/repos/demo-service.git", time_range={"relative": "last_24h"}
    )
    output = CommitsOutput(
        repository="simulator/data/repos/demo-service.git",
        commits=[
            CommitSummary(
                sha="abc",
                author="dev",
                message="fix",
                committed_at="2024-01-01T00:00:00+00:00",
            )
        ],
    )
    collected = datetime(2024, 1, 2, tzinfo=UTC)
    records, _ = normalize_to_evidence(
        tool_name="get_recent_commits",
        payload=payload,
        output=output,
        ctx=ctx,
        collected_at=collected,
    )
    assert records[0].observed_at != records[0].collected_at
