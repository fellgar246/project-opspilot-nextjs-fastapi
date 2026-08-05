from __future__ import annotations

import pytest
from worker.tasks.ping import ping


@pytest.mark.asyncio
async def test_ping_task_propagates_request_id(caplog: pytest.LogCaptureFixture) -> None:
    await ping({"request_id": "worker-req-42"})
    assert any(
        getattr(record, "request_id", None) == "worker-req-42"
        for record in caplog.records
    )
