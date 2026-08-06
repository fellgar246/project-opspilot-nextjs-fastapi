from __future__ import annotations

from pathlib import Path

import yaml  # type: ignore[import-untyped]

from demo_service.scenarios.models import ScenarioDefinition


def load_scenarios(directory: Path) -> dict[str, ScenarioDefinition]:
    scenarios: dict[str, ScenarioDefinition] = {}
    if not directory.exists():
        return scenarios
    for path in sorted(directory.glob("*.yaml")) + sorted(directory.glob("*.yml")):
        with path.open(encoding="utf-8") as handle:
            raw = yaml.safe_load(handle)
        if not raw:
            continue
        definition = ScenarioDefinition.model_validate(raw)
        scenarios[definition.id] = definition
    return scenarios
