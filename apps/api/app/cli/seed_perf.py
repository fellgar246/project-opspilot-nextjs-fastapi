from __future__ import annotations

import asyncio
import logging
import random
import uuid
from datetime import UTC, datetime, timedelta

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import get_session, init_db
from app.incidents.models import (
    Incident,
    IncidentService,
    IncidentSeverity,
    IncidentSource,
    IncidentStatus,
    Service,
)
from sqlalchemy import func, select

logger = logging.getLogger(__name__)

SEVERITIES = list(IncidentSeverity)
STATUSES = list(IncidentStatus)
SOURCES = list(IncidentSource)
TITLES = [
    "Elevated error rate on checkout",
    "Database connection pool saturation",
    "Latency spike on catalog endpoint",
    "External dependency timeout",
    "Memory usage climbing steadily",
    "Feature flag causing checkout failures",
    "Post-deployment regression detected",
]


async def _seed(count: int = 10_000) -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    init_db(settings)

    async for session in get_session():
        services = list((await session.execute(select(Service))).scalars().all())
        if not services:
            logger.error("seed_perf_no_services", extra={"hint": "Run seed-services first"})
            return

        existing_count = await session.scalar(select(func.count()).select_from(Incident))
        if existing_count and existing_count >= count:
            logger.info("seed_perf_skipped", extra={"existing": existing_count})
            return

        base_time = datetime.now(UTC) - timedelta(days=365)
        created = 0

        for i in range(count):
            started_at = base_time + timedelta(minutes=i * 5 + random.randint(0, 30))
            incident = Incident(
                id=uuid.uuid4(),
                title=f"{random.choice(TITLES)} #{i + 1}",
                description=f"Synthetic incident {i + 1} for performance testing.",
                severity=random.choice(SEVERITIES),
                status=random.choice(STATUSES),
                source=random.choice(SOURCES),
                started_at=started_at,
                created_by=None,
            )
            session.add(incident)
            session.add(IncidentService(incident_id=incident.id, service_id=random.choice(services).id))
            created += 1

            if created % 500 == 0:
                await session.flush()
                logger.info("seed_perf_progress", extra={"created": created})

        await session.commit()
        logger.info("seed_perf_complete", extra={"created": created})


def main() -> None:
    asyncio.run(_seed())


if __name__ == "__main__":
    main()
