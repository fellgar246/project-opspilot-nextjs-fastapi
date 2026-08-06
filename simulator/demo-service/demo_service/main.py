from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from demo_service.config import get_settings
from demo_service.endpoints import router as endpoints_router
from demo_service.logging import configure_logging
from demo_service.scenarios.engine import ScenarioEngine
from demo_service.sim_router import router as sim_router
from demo_service.tracing import configure_tracing


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    configure_tracing(settings.service_name, settings.otel_exporter_endpoint)
    if getattr(app.state, "engine", None) is None:
        app.state.engine = ScenarioEngine(settings)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="OpsPilot Demo Service", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = ScenarioEngine(settings)
    app.include_router(endpoints_router)
    app.include_router(sim_router)
    return app


app = create_app()
