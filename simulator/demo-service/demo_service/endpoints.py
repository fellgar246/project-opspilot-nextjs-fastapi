from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response

from demo_service.chaos import ChaosEffects
from demo_service.dependencies import deps
from demo_service.logging import emit_request_log
from demo_service.metrics import metrics_payload, observe_request, refresh_memory_gauge
from demo_service.tracing import current_trace_id, get_tracer

router = APIRouter()

WorkFn = Callable[[ChaosEffects, float], Awaitable[dict[str, Any]]]


async def _handle(request: Request, endpoint: str, work: WorkFn) -> dict[str, Any]:
    engine = request.app.state.engine
    effects = engine.compute_effects()
    scenario_id = effects.active_scenario_ids[0] if effects.active_scenario_ids else None
    rng = engine.rng(scenario_id)
    started = time.perf_counter()
    tracer = get_tracer()
    status = 200
    error_type: str | None = None
    stack_hint: str | None = None
    body: dict[str, Any] = {}

    with tracer.start_as_current_span(f"http{endpoint}"):
        trace_id = current_trace_id()
        try:
            if effects.missing_env:
                raise RuntimeError(f"Missing required environment variable: {effects.missing_env}")

            if effects.feature_flag_override and endpoint == "/checkout":
                flag = effects.feature_flag_override
                bug_rate = float(flag.get("bug_rate", 0.5))
                if flag.get("enabled") and bug_rate > rng.random():
                    raise RuntimeError("feature flag path raised unexpected null pointer")

            if rng.random() < effects.error_rate:
                status = effects.error_status
                error_type = effects.error_type
                raise HTTPException(status_code=status, detail=error_type)

            try:
                await deps.external_charge(effects, rng.random())
            except ConnectionError:
                if effects.external_error_rate >= 0.2:
                    raise
                # Correlated-but-not-causal noise: metric ticks, request continues.

            body = await work(effects, rng.random())
            await deps.cache_get(endpoint)
            body["trace_id"] = trace_id
            body["active_scenarios"] = effects.active_scenario_ids
        except HTTPException as exc:
            status = exc.status_code
            error_type = error_type or "HTTPException"
            stack_hint = str(exc.detail)
            duration = time.perf_counter() - started
            observe_request(endpoint, status, duration)
            refresh_memory_gauge(effects.memory_leak_bytes)
            emit_request_log(
                level="error",
                endpoint=endpoint,
                status=status,
                latency_ms=duration * 1000,
                trace_id=trace_id,
                message=str(exc.detail),
                error_type=error_type,
                stack_hint=stack_hint,
                scenario_id=scenario_id,
            )
            raise
        except TimeoutError as exc:
            status = 503
            duration = time.perf_counter() - started
            observe_request(endpoint, status, duration)
            refresh_memory_gauge(effects.memory_leak_bytes)
            emit_request_log(
                level="error",
                endpoint=endpoint,
                status=status,
                latency_ms=duration * 1000,
                trace_id=trace_id,
                message=str(exc),
                error_type="PoolTimeout",
                stack_hint="db.pool.acquire",
                scenario_id=scenario_id,
            )
            raise HTTPException(status_code=status, detail=str(exc)) from exc
        except Exception as exc:
            status = 500
            duration = time.perf_counter() - started
            observe_request(endpoint, status, duration)
            refresh_memory_gauge(effects.memory_leak_bytes)
            emit_request_log(
                level="error",
                endpoint=endpoint,
                status=status,
                latency_ms=duration * 1000,
                trace_id=trace_id,
                message=str(exc),
                error_type=type(exc).__name__,
                stack_hint=str(exc)[:200],
                scenario_id=scenario_id,
            )
            raise HTTPException(status_code=status, detail=str(exc)) from exc

        duration = time.perf_counter() - started
        synthetic = effects.extra_latency_ms / 1000.0
        observe_request(endpoint, status, duration + synthetic)
        refresh_memory_gauge(effects.memory_leak_bytes)
        for pattern, rate in effects.log_patterns:
            if rng.random() < min(1.0, rate / 60.0):
                emit_request_log(
                    level="warning",
                    endpoint=endpoint,
                    status=status,
                    latency_ms=duration * 1000,
                    trace_id=trace_id,
                    message=pattern,
                    scenario_id=scenario_id,
                )
        emit_request_log(
            level="info",
            endpoint=endpoint,
            status=status,
            latency_ms=duration * 1000,
            trace_id=trace_id,
            message=f"{endpoint} ok",
            scenario_id=scenario_id,
        )
        return body


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "demo-service"}


@router.get("/catalog")
async def catalog(request: Request) -> dict[str, Any]:
    async def work(effects: ChaosEffects, roll: float) -> dict[str, Any]:
        db = await deps.db_query(effects, roll)
        return {"items": [{"id": i, "name": f"sku-{i}"} for i in range(1, 6)], "db": db}

    return await _handle(request, "/catalog", work)


@router.post("/checkout")
async def checkout(request: Request) -> dict[str, Any]:
    async def work(effects: ChaosEffects, roll: float) -> dict[str, Any]:
        db = await deps.db_query(effects, roll)
        payment = await deps.external_charge(effects, roll)
        return {"order_id": "ord-1001", "db": db, "payment": payment}

    return await _handle(request, "/checkout", work)


@router.get("/orders/{order_id}")
async def get_order(order_id: str, request: Request) -> dict[str, Any]:
    async def work(effects: ChaosEffects, roll: float) -> dict[str, Any]:
        db = await deps.db_query(effects, roll)
        return {"order_id": order_id, "status": "paid", "db": db}

    return await _handle(request, "/orders/{id}", work)


@router.get("/metrics")
async def metrics() -> Response:
    payload, content_type = metrics_payload()
    return Response(content=payload, media_type=content_type)
