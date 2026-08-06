from __future__ import annotations

import json
import random
from pathlib import Path
from threading import Lock
from typing import Any

from demo_service.chaos import ChaosEffects
from demo_service.clock import clock
from demo_service.config import Settings, get_settings
from demo_service.scenarios.loader import load_scenarios
from demo_service.scenarios.models import ActiveScenario, Mode, ScenarioDefinition
from demo_service.store.deployments import DeploymentStore
from demo_service.store.feature_flags import FeatureFlagStore


class ScenarioEngine:
    def __init__(
        self,
        settings: Settings | None = None,
        deployments: DeploymentStore | None = None,
        flags: FeatureFlagStore | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.deployments = deployments or DeploymentStore(
            self.settings.data_dir / "deployments.json"
        )
        self.flags = flags or FeatureFlagStore(self.settings.data_dir / "feature_flags.json")
        self._replay_dir = self.settings.replay_dir or (self.settings.data_dir / "replay")
        self._definitions = load_scenarios(self.settings.scenarios_dir)
        self._active: dict[str, ActiveScenario] = {}
        self._deactivating: dict[str, dict[str, float]] = {}
        self._rngs: dict[str, random.Random] = {}
        self._memory_leak_bytes = 0.0
        self._lock = Lock()
        self._mode: Mode = "live"
        self._replay_frames: list[dict[str, Any]] = []
        self._replay_index = 0

    def reload(self) -> None:
        with self._lock:
            self._definitions = load_scenarios(self.settings.scenarios_dir)

    def list_scenarios(self) -> list[ScenarioDefinition]:
        return list(self._definitions.values())

    def get_definition(self, scenario_id: str) -> ScenarioDefinition | None:
        return self._definitions.get(scenario_id)

    def state(self) -> dict[str, Any]:
        effects = self.compute_effects()
        with self._lock:
            return {
                "mode": self._mode,
                "clock": {
                    "now": clock.now(),
                    "now_iso": clock.now_iso(),
                    "offset_seconds": clock.offset_seconds,
                },
                "active": [a.model_dump() for a in self._active.values()],
                "deactivating": self._deactivating,
                "effects": {
                    "error_rate": effects.error_rate,
                    "latency_multiplier": effects.latency_multiplier,
                    "extra_latency_ms": effects.extra_latency_ms,
                    "pool_saturation": effects.pool_saturation,
                    "pool_max_size": effects.pool_max_size,
                    "external_error_rate": effects.external_error_rate,
                    "memory_leak_bytes": effects.memory_leak_bytes,
                    "missing_env": effects.missing_env,
                    "n_plus_one_queries": effects.n_plus_one_queries,
                    "active_scenario_ids": effects.active_scenario_ids,
                },
                "reproducibility_tolerance": self.settings.reproducibility_tolerance,
            }

    def activate(
        self,
        scenario_id: str,
        *,
        seed: int = 42,
        mode: Mode = "live",
    ) -> ActiveScenario:
        definition = self._definitions.get(scenario_id)
        if definition is None:
            raise KeyError(scenario_id)

        now = clock.now()
        deployment_id: str | None = None
        if definition.deployment is not None:
            dep = definition.deployment
            deployed_at = now + dep.offset_seconds
            record = self.deployments.add(
                service=self.settings.service_name,
                version=dep.version,
                commit_sha=dep.commit_sha or "unknown",
                deployed_at=deployed_at,
                deployed_by=dep.deployed_by,
                changelog=dep.changelog or definition.title,
                status="success",
            )
            deployment_id = record["deployment_id"]

        if definition.feature_flag is not None:
            self.flags.upsert(
                key=str(definition.feature_flag["key"]),
                service=self.settings.service_name,
                enabled=bool(definition.feature_flag.get("enabled", True)),
                rollout_percentage=float(definition.feature_flag.get("rollout_percentage", 100)),
                updated_by="scenario-engine",
                updated_at=now,
            )

        active = ActiveScenario(
            id=scenario_id,
            seed=seed,
            activated_at=now,
            mode=mode,
            intensity=1.0 if mode == "replay" else 0.0,
            deployment_id=deployment_id,
        )
        with self._lock:
            self._active[scenario_id] = active
            self._rngs[scenario_id] = random.Random(seed)
            self._mode = mode
            self._deactivating.pop(scenario_id, None)
            if mode == "replay":
                self._load_replay(scenario_id)

        if mode == "replay":
            # Jump intensity to full immediately for evaluation speed.
            with self._lock:
                self._active[scenario_id].intensity = 1.0
        return active

    def deactivate(self, scenario_id: str) -> None:
        with self._lock:
            active = self._active.pop(scenario_id, None)
            self._rngs.pop(scenario_id, None)
            if active is None:
                return
            definition = self._definitions.get(scenario_id)
            ramp_down = (
                definition.ramp_down_seconds
                if definition and definition.ramp_down_seconds is not None
                else self.settings.ramp_down_seconds
            )
            self._deactivating[scenario_id] = {
                "started_at": clock.now(),
                "from_intensity": active.intensity,
                "ramp_down_seconds": float(ramp_down),
            }

    def reset(self) -> None:
        with self._lock:
            self._active.clear()
            self._deactivating.clear()
            self._rngs.clear()
            self._memory_leak_bytes = 0.0
            self._mode = "live"
            self._replay_frames = []
            self._replay_index = 0
        clock.reset()
        self.deployments.reload()
        self.flags.reload()

    def rng(self, scenario_id: str | None = None) -> random.Random:
        with self._lock:
            if scenario_id and scenario_id in self._rngs:
                return self._rngs[scenario_id]
            if self._rngs:
                return next(iter(self._rngs.values()))
        return random.Random(0)

    def _intensity_for(self, active: ActiveScenario, definition: ScenarioDefinition) -> float:
        if active.mode == "replay":
            return 1.0
        elapsed = max(0.0, clock.now() - active.activated_at)
        ramp = max(definition.ramp_up_seconds, 0.001)
        return min(1.0, elapsed / ramp)

    def _deactivating_intensity(self, scenario_id: str) -> float:
        info = self._deactivating.get(scenario_id)
        if info is None:
            return 0.0
        elapsed = clock.now() - info["started_at"]
        ramp = max(info["ramp_down_seconds"], 0.001)
        remaining = max(0.0, 1.0 - elapsed / ramp) * info["from_intensity"]
        if remaining <= 0.0:
            self._deactivating.pop(scenario_id, None)
            return 0.0
        return remaining

    def compute_effects(self) -> ChaosEffects:
        if self._mode == "replay" and self._replay_frames:
            frame = self._replay_frames[min(self._replay_index, len(self._replay_frames) - 1)]
            self._replay_index = min(self._replay_index + 1, len(self._replay_frames) - 1)
            return ChaosEffects(**frame.get("effects", {}))

        aggregated = ChaosEffects()
        with self._lock:
            actives = list(self._active.items())
            deactivating_ids = list(self._deactivating.keys())

        for scenario_id, active in actives:
            definition = self._definitions[scenario_id]
            intensity = self._intensity_for(active, definition)
            active.intensity = intensity
            aggregated = aggregated.merge(self._effects_from_definition(definition, intensity))
            aggregated.active_scenario_ids.append(scenario_id)

        for scenario_id in deactivating_ids:
            maybe_def = self._definitions.get(scenario_id)
            if maybe_def is None:
                continue
            intensity = self._deactivating_intensity(scenario_id)
            if intensity <= 0:
                continue
            aggregated = aggregated.merge(self._effects_from_definition(maybe_def, intensity))
            aggregated.active_scenario_ids.append(scenario_id)

        # Memory leak accumulates across time for the dedicated scenario.
        if "SCN-005-memory-leak" in aggregated.active_scenario_ids:
            leak_rate = aggregated.memory_leak_bytes or 256_000.0
            self._memory_leak_bytes += leak_rate * 0.05
            aggregated.memory_leak_bytes = self._memory_leak_bytes
        else:
            aggregated.memory_leak_bytes = 0.0
            self._memory_leak_bytes = max(0.0, self._memory_leak_bytes * 0.9)

        return aggregated

    def _effects_from_definition(
        self, definition: ScenarioDefinition, intensity: float
    ) -> ChaosEffects:
        effects = ChaosEffects()
        raw = definition.effects
        effects.error_rate = float(raw.get("error_rate", 0.0)) * intensity
        effects.error_status = int(raw.get("error_status", 500))
        effects.error_type = str(raw.get("error_type", "InternalError"))
        effects.latency_multiplier = (
            1.0 + (float(raw.get("latency_multiplier", 1.0)) - 1.0) * intensity
        )
        effects.extra_latency_ms = float(raw.get("extra_latency_ms", 0.0)) * intensity
        effects.n_plus_one_queries = int(float(raw.get("n_plus_one_queries", 0)) * intensity)
        effects.pool_saturation = float(raw.get("pool_saturation", 0.0)) * intensity
        if "pool_max_size" in raw:
            # Interpolate from nominal max toward the degraded max.
            nominal = self.settings.default_db_pool_max_size
            target = int(raw["pool_max_size"])
            effects.pool_max_size = round(nominal + (target - nominal) * intensity)
        effects.external_error_rate = float(raw.get("external_error_rate", 0.0)) * intensity
        effects.memory_leak_bytes = float(raw.get("memory_leak_bytes_per_tick", 0.0)) * intensity
        if raw.get("missing_env") and intensity > 0.2:
            effects.missing_env = str(raw["missing_env"])
        if definition.feature_flag and intensity > 0.3:
            effects.feature_flag_override = dict(definition.feature_flag)

        for signal in definition.signals:
            if signal.log_pattern and signal.rate_per_minute:
                effects.log_patterns.append(
                    (signal.log_pattern, signal.rate_per_minute * intensity)
                )
            if (
                signal.metric == "http_request_duration_seconds"
                and signal.behavior == "p95_increase"
            ):
                factor = signal.factor or float(raw.get("latency_multiplier", 2.0))
                effects.latency_multiplier = max(
                    effects.latency_multiplier,
                    1.0 + (factor - 1.0) * intensity,
                )
            if signal.metric == "db_pool_connections_in_use" and signal.behavior == "saturate":
                effects.pool_saturation = max(effects.pool_saturation, intensity)
            if (
                signal.metric == "external_dependency_errors_total"
                and signal.behavior == "mild_increase"
            ):
                effects.external_error_rate = max(effects.external_error_rate, 0.05 * intensity)
            if signal.metric == "process_resident_memory_bytes" and signal.behavior == "grow":
                effects.memory_leak_bytes = max(effects.memory_leak_bytes, 512_000 * intensity)
            if signal.metric == "http_requests_total" and signal.behavior == "error_spike":
                effects.error_rate = max(effects.error_rate, 0.4 * intensity)

        return effects

    def _load_replay(self, scenario_id: str) -> None:
        path = self._replay_dir / f"{scenario_id}.json"
        if not path.exists():
            # Synthesize a full-intensity frame so replay never blocks on missing files.
            definition = self._definitions[scenario_id]
            effects = self._effects_from_definition(definition, 1.0)
            self._replay_frames = [
                {
                    "effects": {
                        "error_rate": effects.error_rate,
                        "error_status": effects.error_status,
                        "error_type": effects.error_type,
                        "latency_multiplier": effects.latency_multiplier,
                        "extra_latency_ms": effects.extra_latency_ms,
                        "n_plus_one_queries": effects.n_plus_one_queries,
                        "pool_saturation": effects.pool_saturation,
                        "pool_max_size": effects.pool_max_size,
                        "external_error_rate": effects.external_error_rate,
                        "memory_leak_bytes": effects.memory_leak_bytes,
                        "missing_env": effects.missing_env,
                        "active_scenario_ids": [scenario_id],
                    }
                }
            ]
            self._replay_index = 0
            return
        self._replay_frames = json.loads(path.read_text(encoding="utf-8"))
        self._replay_index = 0

    def write_replay_template(self, scenario_id: str, path: Path | None = None) -> Path:
        definition = self._definitions[scenario_id]
        frames = []
        for step in range(10):
            intensity = (step + 1) / 10
            effects = self._effects_from_definition(definition, intensity)
            frames.append(
                {
                    "t": step,
                    "effects": {
                        "error_rate": effects.error_rate,
                        "error_status": effects.error_status,
                        "error_type": effects.error_type,
                        "latency_multiplier": effects.latency_multiplier,
                        "extra_latency_ms": effects.extra_latency_ms,
                        "n_plus_one_queries": effects.n_plus_one_queries,
                        "pool_saturation": effects.pool_saturation,
                        "pool_max_size": effects.pool_max_size,
                        "external_error_rate": effects.external_error_rate,
                        "memory_leak_bytes": effects.memory_leak_bytes,
                        "missing_env": effects.missing_env,
                        "active_scenario_ids": [scenario_id],
                    },
                }
            )
        target = path or (self._replay_dir / f"{scenario_id}.json")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(frames, indent=2), encoding="utf-8")
        return target
