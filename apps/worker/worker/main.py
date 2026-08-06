from __future__ import annotations

import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from arq.connections import RedisSettings
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from opspilot.telemetry import TraceContextLogFilter, configure_tracing

from worker.config import get_worker_settings
from worker.logging import configure_logging
from worker.tasks.approvals import expire_pending_approvals, resume_investigation
from worker.tasks.investigate import investigate_incident
from worker.tasks.ping import ping

settings = get_worker_settings()
configure_logging(settings.log_level)
logging.getLogger().addFilter(TraceContextLogFilter())
configure_tracing("opspilot-worker", otlp_endpoint=getattr(settings, "otel_exporter_endpoint", None))


class _MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path != "/metrics":
            self.send_response(404)
            self.end_headers()
            return
        payload = generate_latest()
        self.send_response(200)
        self.send_header("Content-Type", CONTENT_TYPE_LATEST)
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:
        return


def _start_metrics_server(port: int = 9091) -> None:
    server = HTTPServer(("0.0.0.0", port), _MetricsHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()


_start_metrics_server()


async def on_job_start(ctx: dict[str, object]) -> None:
    from opentelemetry import context as otel_context
    from opspilot.telemetry.tracing import deserialize_trace_context, extract_trace_context

    trace_payload = ctx.get("trace_context")
    if isinstance(trace_payload, str):
        carrier = deserialize_trace_context(trace_payload)
        if carrier:
            otel_context.attach(extract_trace_context(carrier))


class WorkerSettings:
    functions = [ping, investigate_incident, resume_investigation, expire_pending_approvals]
    redis_settings = RedisSettings.from_dsn(str(settings.redis_url))
    max_jobs = 10
    job_timeout = 900
    on_job_start = on_job_start
    cron_jobs = [
        ("expire_pending_approvals", 60),
    ]
