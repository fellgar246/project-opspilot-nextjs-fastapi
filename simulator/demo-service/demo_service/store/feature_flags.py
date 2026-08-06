from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Any

from demo_service.clock import clock


class FeatureFlagStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = Lock()
        self._items: dict[str, dict[str, Any]] = {}
        self.reload()

    def reload(self) -> None:
        with self._lock:
            if self.path.exists():
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                self._items = {item["key"]: item for item in raw}
            else:
                self._items = {
                    "new-checkout-flow": {
                        "key": "new-checkout-flow",
                        "service": "demo-service",
                        "enabled": False,
                        "rollout_percentage": 0.0,
                        "updated_at": clock.now(),
                        "updated_by": "seed",
                    },
                    "catalog-v2": {
                        "key": "catalog-v2",
                        "service": "demo-service",
                        "enabled": True,
                        "rollout_percentage": 100.0,
                        "updated_at": clock.now(),
                        "updated_by": "seed",
                    },
                }

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(list(self._items.values()), indent=2), encoding="utf-8")

    def list(self, service: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            items = list(self._items.values())
        if service:
            items = [i for i in items if i["service"] == service]
        return items

    def get(self, key: str) -> dict[str, Any] | None:
        with self._lock:
            return self._items.get(key)

    def upsert(
        self,
        *,
        key: str,
        service: str,
        enabled: bool,
        rollout_percentage: float,
        updated_by: str,
        updated_at: float | None = None,
    ) -> dict[str, Any]:
        record = {
            "key": key,
            "service": service,
            "enabled": enabled,
            "rollout_percentage": rollout_percentage,
            "updated_at": updated_at if updated_at is not None else clock.now(),
            "updated_by": updated_by,
        }
        with self._lock:
            self._items[key] = record
            self._persist()
        return record
