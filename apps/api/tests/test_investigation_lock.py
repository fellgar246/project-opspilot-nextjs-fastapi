from __future__ import annotations

import uuid

import pytest
from app.investigation.lock import (
    acquire_investigation_lock,
    get_lock_owner,
    release_investigation_lock,
)
from fakeredis import FakeAsyncRedis


@pytest.mark.asyncio
async def test_investigation_lock_prevents_double_acquire() -> None:
    redis = FakeAsyncRedis(decode_responses=True)
    incident_id = uuid.uuid4()
    first_run = uuid.uuid4()
    second_run = uuid.uuid4()

    assert await acquire_investigation_lock(redis, incident_id=incident_id, agent_run_id=first_run)
    assert not await acquire_investigation_lock(redis, incident_id=incident_id, agent_run_id=second_run)
    assert await get_lock_owner(redis, incident_id=incident_id) == str(first_run)

    await release_investigation_lock(redis, incident_id=incident_id)
    assert await acquire_investigation_lock(redis, incident_id=incident_id, agent_run_id=second_run)
