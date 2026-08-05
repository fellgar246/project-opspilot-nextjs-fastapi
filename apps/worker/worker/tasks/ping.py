from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def ping(ctx: dict[str, object]) -> str:
    request_id = ctx.get("request_id")
    logger.info("ping_task_executed", extra={"request_id": request_id})
    return "pong"
