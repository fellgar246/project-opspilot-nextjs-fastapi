from __future__ import annotations

import pytest
from app.core.security_middleware import RateLimitMiddleware
from starlette.requests import Request


@pytest.mark.asyncio
async def test_rate_limit_blocks_excessive_requests() -> None:
    middleware = RateLimitMiddleware(app=None, max_requests=2, window_seconds=60)  # type: ignore[arg-type]
    calls = 0

    async def call_next(request: Request):
        nonlocal calls
        calls += 1
        from starlette.responses import Response

        return Response("ok", status_code=200)

    scope = {"type": "http", "method": "GET", "path": "/api/v1/evaluations/runs", "headers": []}
    request = Request(scope)

    assert (await middleware.dispatch(request, call_next)).status_code == 200
    assert (await middleware.dispatch(request, call_next)).status_code == 200
    blocked = await middleware.dispatch(request, call_next)
    assert blocked.status_code == 429
