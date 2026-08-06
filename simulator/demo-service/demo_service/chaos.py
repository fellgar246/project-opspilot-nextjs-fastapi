from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChaosEffects:
    """Aggregated degradation applied to request handling."""

    error_rate: float = 0.0
    error_status: int = 500
    error_type: str = "InternalError"
    latency_multiplier: float = 1.0
    extra_latency_ms: float = 0.0
    n_plus_one_queries: int = 0
    pool_saturation: float = 0.0
    pool_max_size: int | None = None
    external_error_rate: float = 0.0
    memory_leak_bytes: float = 0.0
    missing_env: str | None = None
    feature_flag_override: dict[str, Any] | None = None
    log_patterns: list[tuple[str, float]] = field(default_factory=list)
    active_scenario_ids: list[str] = field(default_factory=list)

    def merge(self, other: ChaosEffects) -> ChaosEffects:
        return ChaosEffects(
            error_rate=max(self.error_rate, other.error_rate),
            error_status=(
                other.error_status if other.error_rate >= self.error_rate else self.error_status
            ),
            error_type=(
                other.error_type if other.error_rate >= self.error_rate else self.error_type
            ),
            latency_multiplier=max(self.latency_multiplier, other.latency_multiplier),
            extra_latency_ms=self.extra_latency_ms + other.extra_latency_ms,
            n_plus_one_queries=max(self.n_plus_one_queries, other.n_plus_one_queries),
            pool_saturation=max(self.pool_saturation, other.pool_saturation),
            pool_max_size=(
                min(x for x in (self.pool_max_size, other.pool_max_size) if x is not None)
                if self.pool_max_size is not None or other.pool_max_size is not None
                else None
            ),
            external_error_rate=max(self.external_error_rate, other.external_error_rate),
            memory_leak_bytes=self.memory_leak_bytes + other.memory_leak_bytes,
            missing_env=other.missing_env or self.missing_env,
            feature_flag_override=other.feature_flag_override or self.feature_flag_override,
            log_patterns=[*self.log_patterns, *other.log_patterns],
            active_scenario_ids=[*self.active_scenario_ids, *other.active_scenario_ids],
        )
