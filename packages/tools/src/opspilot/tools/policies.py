from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from opspilot.tools.base import RetryPolicy
from pydantic import BaseModel


@dataclass
class CircuitBreaker:
    threshold: int
    cooldown_seconds: float
    consecutive_failures: int = 0
    opened_at: float | None = None

    def record_success(self) -> None:
        self.consecutive_failures = 0
        self.opened_at = None

    def record_failure(self) -> None:
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.threshold:
            self.opened_at = time.monotonic()

    def is_open(self) -> bool:
        if self.opened_at is None:
            return False
        if time.monotonic() - self.opened_at >= self.cooldown_seconds:
            self.opened_at = None
            self.consecutive_failures = 0
            return False
        return True


@dataclass
class ConcurrencyLimiter:
    global_limit: int
    per_tool_limit: int
    _global_active: int = 0
    _per_tool: dict[str, int] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def try_acquire(self, tool_name: str) -> bool:
        async with self._lock:
            if self._global_active >= self.global_limit:
                return False
            tool_count = self._per_tool.get(tool_name, 0)
            if tool_count >= self.per_tool_limit:
                return False
            self._global_active += 1
            self._per_tool[tool_name] = tool_count + 1
            return True

    async def release(self, tool_name: str) -> None:
        async with self._lock:
            self._global_active = max(0, self._global_active - 1)
            current = self._per_tool.get(tool_name, 0)
            if current <= 1:
                self._per_tool.pop(tool_name, None)
            else:
                self._per_tool[tool_name] = current - 1


async def run_with_timeout(coro: Awaitable[Any], timeout_seconds: float) -> Any:
    return await asyncio.wait_for(coro, timeout=timeout_seconds)


async def run_with_retries(
    fn: Callable[[], Awaitable[BaseModel]],
    *,
    policy: RetryPolicy,
    timeout_seconds: float,
) -> tuple[BaseModel, int]:
    last_exc: Exception | None = None
    attempts = 0
    max_attempts = 1 if not policy.idempotent else policy.max_attempts

    for attempt in range(max_attempts):
        attempts = attempt + 1
        try:
            result = await run_with_timeout(fn(), timeout_seconds)
            return result, attempts - 1
        except TimeoutError:
            raise
        except Exception as exc:
            last_exc = exc
            if attempt + 1 >= max_attempts:
                break
            delay = policy.backoff_base_seconds * (2**attempt)
            jitter = random.uniform(0, delay * 0.25)
            await asyncio.sleep(delay + jitter)

    assert last_exc is not None
    raise last_exc
