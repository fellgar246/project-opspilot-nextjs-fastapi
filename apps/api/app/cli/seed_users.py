from __future__ import annotations

import asyncio
import logging

from app.auth.models import UserRole
from app.auth.service import seed_user_if_missing
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import get_session, init_db

logger = logging.getLogger(__name__)


async def _seed() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    init_db(settings)

    seeds = [
        (
            settings.seed_viewer_email,
            settings.seed_viewer_password.get_secret_value(),
            settings.seed_viewer_display_name,
            UserRole.VIEWER,
        ),
        (
            settings.seed_operator_email,
            settings.seed_operator_password.get_secret_value(),
            settings.seed_operator_display_name,
            UserRole.OPERATOR,
        ),
        (
            settings.seed_approver_email,
            settings.seed_approver_password.get_secret_value(),
            settings.seed_approver_display_name,
            UserRole.APPROVER,
        ),
        (
            settings.seed_admin_email,
            settings.seed_admin_password.get_secret_value(),
            settings.seed_admin_display_name,
            UserRole.ADMIN,
        ),
    ]

    created = 0
    async for session in get_session():
        for email, password, display_name, role in seeds:
            if await seed_user_if_missing(
                session,
                email=email,
                password=password,
                display_name=display_name,
                role=role,
            ):
                created += 1
                logger.info("seed_user_created", extra={"email": email, "role": role.value})
            else:
                logger.info("seed_user_skipped", extra={"email": email, "role": role.value})
        await session.commit()

    logger.info("seed_users_complete users_created=%s", created)


def main() -> None:
    asyncio.run(_seed())


if __name__ == "__main__":
    main()
