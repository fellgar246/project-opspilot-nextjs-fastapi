from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def ping(ctx: dict[str, object]) -> str:
    logger.info("ping_task_executed")
    return "pong"
