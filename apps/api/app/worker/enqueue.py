from __future__ import annotations

from app.core.context import request_id_var
from opspilot.telemetry.tracing import serialize_trace_context


def get_request_id() -> str | None:
    return request_id_var.get()


def enqueue_kwargs() -> dict[str, str]:
    kwargs: dict[str, str] = {}
    request_id = get_request_id()
    if request_id is not None:
        kwargs["request_id"] = request_id
    trace_context = serialize_trace_context()
    if trace_context != "{}":
        kwargs["trace_context"] = trace_context
    return kwargs
