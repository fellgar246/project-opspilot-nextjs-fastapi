from __future__ import annotations

from arq.connections import RedisSettings

from worker.config import get_worker_settings
from worker.logging import configure_logging
from worker.tasks.ping import ping

settings = get_worker_settings()
configure_logging(settings.log_level)


class WorkerSettings:
    functions = [ping]
    redis_settings = RedisSettings.from_dsn(str(settings.redis_url))
    max_jobs = 10
    job_timeout = 300
