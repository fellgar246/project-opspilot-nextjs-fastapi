from __future__ import annotations

import json
import logging
from typing import Any

from opentelemetry import trace
from opentelemetry.propagate import extract, inject
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

_configured = False
logger = logging.getLogger(__name__)

CORRELATION_ATTRS = (
    "incident.id",
    "agent_run.id",
    "tool.name",
    "request.id",
    "user.id",
)


def configure_tracing(service_name: str, otlp_endpoint: str | None = None) -> None:
    global _configured
    if _configured:
        return
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    if otlp_endpoint:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        exporter: Any = OTLPSpanExporter(endpoint=otlp_endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _configured = True


def get_tracer(name: str) -> trace.Tracer:
    return trace.get_tracer(name)


def current_trace_id() -> str | None:
    span = trace.get_current_span()
    ctx = span.get_span_context()
    if ctx is not None and ctx.is_valid and ctx.trace_id != 0:
        return format(ctx.trace_id, "032x")
    return None


def current_span_id() -> str | None:
    span = trace.get_current_span()
    ctx = span.get_span_context()
    if ctx is not None and ctx.is_valid and ctx.span_id != 0:
        return format(ctx.span_id, "016x")
    return None


def set_correlation_attrs(**attrs: str | None) -> None:
    span = trace.get_current_span()
    for key, value in attrs.items():
        if value is not None:
            span.set_attribute(key, value)


def inject_trace_context() -> dict[str, str]:
    carrier: dict[str, str] = {}
    inject(carrier)
    return carrier


def extract_trace_context(carrier: dict[str, str]) -> Any:
    return extract(carrier)


def serialize_trace_context() -> str:
    return json.dumps(inject_trace_context())


def deserialize_trace_context(payload: str | None) -> dict[str, str]:
    if not payload:
        return {}
    try:
        data = json.loads(payload)
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
    except json.JSONDecodeError:
        logger.warning("invalid_trace_context_payload")
    return {}


class TraceContextLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = current_trace_id()
        record.span_id = current_span_id()
        return True
