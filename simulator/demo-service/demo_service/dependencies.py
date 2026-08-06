from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

from demo_service.chaos import ChaosEffects
from demo_service.config import get_settings
from demo_service.metrics import inc_external_error, set_pool_gauges


@dataclass
class SimulatedDeps:
    """Simulated database, cache and external payment provider."""

    async def db_query(self, effects: ChaosEffects, rng_roll: float) -> dict[str, float]:
        settings = get_settings()
        pool_max = effects.pool_max_size or settings.default_db_pool_max_size
        in_use = min(pool_max, 2 + effects.pool_saturation * pool_max)
        wait = effects.pool_saturation * 0.8
        set_pool_gauges(in_use=in_use, wait_seconds=wait)

        queries = 1 + effects.n_plus_one_queries
        base_ms = 3.0
        total_ms = (base_ms * queries) * effects.latency_multiplier + effects.extra_latency_ms
        if effects.pool_saturation > 0.7 and rng_roll < effects.pool_saturation:
            await asyncio.sleep(min(0.05, wait / 10))
            raise TimeoutError("connection pool timeout")
        await asyncio.sleep(min(0.05, total_ms / 1000.0))
        return {"queries": float(queries), "latency_ms": total_ms, "pool_in_use": in_use}

    async def cache_get(self, key: str) -> str | None:
        await asyncio.sleep(0.001)
        return f"cached:{key}" if key else None

    async def external_charge(self, effects: ChaosEffects, rng_roll: float) -> dict[str, str]:
        if rng_roll < effects.external_error_rate:
            inc_external_error("payments")
            raise ConnectionError("payments provider unavailable")
        await asyncio.sleep(0.005 * effects.latency_multiplier)
        return {"status": "authorized", "provider": "payments", "at": str(time.time())}


deps = SimulatedDeps()
