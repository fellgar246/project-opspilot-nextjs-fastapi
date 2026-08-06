from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from opspilot.telemetry.metrics import HTTP_LATENCY, HTTP_REQUESTS


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
        )
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        started = time.perf_counter()
        response = await call_next(request)
        endpoint = request.url.path
        if endpoint.startswith("/metrics"):
            return response
        duration = time.perf_counter() - started
        HTTP_REQUESTS.labels(
            method=request.method,
            endpoint=endpoint,
            status=str(response.status_code),
        ).inc()
        HTTP_LATENCY.labels(method=request.method, endpoint=endpoint).observe(duration)
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiter for sensitive endpoints."""

    def __init__(self, app: object, *, max_requests: int = 30, window_seconds: int = 60) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: dict[str, list[float]] = {}

    def _key(self, request: Request) -> str:
        user = getattr(request.state, "current_user", None)
        user_id = getattr(user, "id", "anon")
        return f"{user_id}:{request.url.path}"

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        sensitive = request.url.path.startswith(
            ("/api/v1/evaluations", "/api/v1/investigation", "/api/v1/executions")
        )
        if sensitive:
            key = self._key(request)
            now = time.time()
            bucket = [t for t in self._buckets.get(key, []) if now - t < self.window_seconds]
            if len(bucket) >= self.max_requests:
                return Response("Rate limit exceeded", status_code=429)
            bucket.append(now)
            self._buckets[key] = bucket
        return await call_next(request)
