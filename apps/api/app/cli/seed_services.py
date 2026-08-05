from __future__ import annotations

import asyncio
import logging

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import get_session, init_db
from app.incidents.models import Service, ServiceEnvironment
from sqlalchemy import select

logger = logging.getLogger(__name__)

SIMULATOR_SERVICES = [
    {
        "name": "demo-service",
        "description": "Primary demo service with checkout, catalog, and orders endpoints",
        "repository": "simulator/data/repos/demo-service.git",
        "environment": ServiceEnvironment.DEMO,
        "owner_team": "platform",
    },
]


async def _seed() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    init_db(settings)

    created = 0
    async for session in get_session():
        for spec in SIMULATOR_SERVICES:
            existing = await session.scalar(select(Service).where(Service.name == spec["name"]))
            if existing is not None:
                logger.info("seed_service_skipped", extra={"name": spec["name"]})
                continue
            session.add(Service(**spec, is_active=True))
            created += 1
            logger.info("seed_service_created", extra={"name": spec["name"]})
        await session.commit()

    logger.info("seed_services_complete", extra={"created": created})


def main() -> None:
    asyncio.run(_seed())


if __name__ == "__main__":
    main()
