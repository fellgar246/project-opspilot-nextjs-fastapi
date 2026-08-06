from __future__ import annotations

import resource
from typing import Any

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

REGISTRY = CollectorRegistry()

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["endpoint", "status"],
    registry=REGISTRY,
)
HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=REGISTRY,
)
DB_POOL_IN_USE = Gauge(
    "db_pool_connections_in_use",
    "Database pool connections currently in use",
    registry=REGISTRY,
)
DB_POOL_WAIT = Gauge(
    "db_pool_wait_seconds",
    "Seconds spent waiting for a pool connection",
    registry=REGISTRY,
)
EXTERNAL_ERRORS = Counter(
    "external_dependency_errors_total",
    "Errors from simulated external providers",
    ["provider"],
    registry=REGISTRY,
)
PROCESS_MEMORY = Gauge(
    "process_resident_memory_bytes",
    "Resident set size of the demo-service process",
    registry=REGISTRY,
)


def observe_request(endpoint: str, status: int, duration_seconds: float) -> None:
    HTTP_REQUESTS_TOTAL.labels(endpoint=endpoint, status=str(status)).inc()
    HTTP_REQUEST_DURATION.labels(endpoint=endpoint).observe(duration_seconds)


def set_pool_gauges(*, in_use: float, wait_seconds: float) -> None:
    DB_POOL_IN_USE.set(in_use)
    DB_POOL_WAIT.set(wait_seconds)


def inc_external_error(provider: str = "payments") -> None:
    EXTERNAL_ERRORS.labels(provider=provider).inc()


def refresh_memory_gauge(leak_bytes: float = 0.0) -> None:
    usage = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    # macOS reports bytes; Linux reports kilobytes — normalize roughly.
    if usage < 10_000_000:
        usage *= 1024
    PROCESS_MEMORY.set(usage + leak_bytes)


def metrics_payload() -> tuple[bytes, str]:
    refresh_memory_gauge()
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST


def snapshot_counters() -> dict[str, Any]:
    """Lightweight snapshot used by reproducibility tests."""
    return {
        "db_pool_connections_in_use": DB_POOL_IN_USE._value.get(),
        "db_pool_wait_seconds": DB_POOL_WAIT._value.get(),
        "process_resident_memory_bytes": PROCESS_MEMORY._value.get(),
    }
