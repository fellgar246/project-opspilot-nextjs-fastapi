from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

SERVICE_NAME = "worker"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "service": getattr(record, "service", SERVICE_NAME),
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
            "incident_id": getattr(record, "incident_id", None),
            "agent_run_id": getattr(record, "agent_run_id", None),
            "trace_id": getattr(record, "trace_id", None),
        }
        return json.dumps(payload, ensure_ascii=True)


def configure_logging(level: str) -> None:
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(level)
