from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opspilot.telemetry import APP_INFO, TraceContextLogFilter, configure_tracing
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.api.routes import router as health_router
from app.approvals.router import router as approvals_router
from app.audit.router import router as audit_router
from app.auth.router import router as auth_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestIdLogFilter, RequestIdMiddleware
from app.core.redis import close_redis, init_redis
from app.core.security_middleware import (
    MetricsMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
)
from app.db.session import init_db
from app.evaluations.router import router as evaluations_router
from app.events.router import router as events_router
from app.executions.router import router as executions_router
from app.incidents.router import router as incidents_router
from app.investigation.router import router as investigation_router
from app.reports.router import router as reports_router


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    logging.getLogger().addFilter(RequestIdLogFilter())
    logging.getLogger().addFilter(TraceContextLogFilter())
    configure_tracing(
        "opspilot-api", otlp_endpoint=getattr(settings, "otel_exporter_endpoint", None)
    )
    APP_INFO.info({"version": settings.app_version, "git_sha": settings.git_sha})
    init_db(settings)
    init_redis(settings)
    yield
    await close_redis()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="OpsPilot API", version=settings.app_version, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.cors_origins],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
    )
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestIdMiddleware)
    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(audit_router, prefix="/api/v1")
    app.include_router(incidents_router, prefix="/api/v1")
    app.include_router(investigation_router, prefix="/api/v1")
    app.include_router(events_router, prefix="/api/v1")
    app.include_router(approvals_router, prefix="/api/v1")
    app.include_router(executions_router, prefix="/api/v1")
    app.include_router(reports_router, prefix="/api/v1")
    app.include_router(evaluations_router, prefix="/api/v1")
    FastAPIInstrumentor.instrument_app(app)

    @app.get("/metrics")
    async def metrics() -> Response:
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app
