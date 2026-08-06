from __future__ import annotations

import json
import logging
import sys
from typing import Any

from demo_service.clock import clock
from demo_service.config import get_settings


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": clock.now_iso(),
            "level": record.levelname.lower(),
            "service": get_settings().service_name,
            "message": record.getMessage(),
        }
        for key in (
            "endpoint",
            "status",
            "latency_ms",
            "trace_id",
            "error_type",
            "stack_hint",
            "scenario_id",
        ):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        return json.dumps(payload, ensure_ascii=True)


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(level.upper())


def emit_request_log(
    *,
    level: str,
    endpoint: str,
    status: int,
    latency_ms: float,
    trace_id: str,
    message: str,
    error_type: str | None = None,
    stack_hint: str | None = None,
    scenario_id: str | None = None,
) -> None:
    logger = logging.getLogger("demo-service.request")
    extra: dict[str, Any] = {
        "endpoint": endpoint,
        "status": status,
        "latency_ms": round(latency_ms, 3),
        "trace_id": trace_id,
    }
    if error_type is not None:
        extra["error_type"] = error_type
    if stack_hint is not None:
        extra["stack_hint"] = stack_hint
    if scenario_id is not None:
        extra["scenario_id"] = scenario_id
    getattr(logger, level.lower(), logger.info)(message, extra=extra)
