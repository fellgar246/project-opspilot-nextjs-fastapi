from __future__ import annotations

import pytest
from arq import create_pool
from arq.connections import RedisSettings
from arq.worker import Worker
from worker.main import WorkerSettings
from worker.tasks.ping import ping


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ping_task_enqueue_and_execute() -> None:
    pytest.importorskip("testcontainers")
    try:
        import docker

        docker.from_env().ping()
    except Exception:
        pytest.skip("Docker is not available")

    from testcontainers.redis import RedisContainer

    with RedisContainer("redis:7-alpine") as redis_container:
        host = redis_container.get_container_host_ip()
        port = int(redis_container.get_exposed_port(6379))
        redis_settings = RedisSettings(host=host, port=port)

        pool = await create_pool(redis_settings)
        try:
            job = await pool.enqueue_job("ping")
            assert job is not None

            worker = Worker(
                functions=WorkerSettings.functions,
                redis_settings=redis_settings,
                burst=True,
            )
            await worker.async_run()
            result = await job.result(timeout=10)
            assert result == "pong"
        finally:
            await pool.aclose()


@pytest.mark.asyncio
async def test_ping_task_returns_pong() -> None:
    result = await ping({})
    assert result == "pong"
