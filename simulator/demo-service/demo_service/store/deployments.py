from __future__ import annotations

import json
import uuid
from pathlib import Path
from threading import Lock
from typing import Any

from demo_service.clock import clock


class DeploymentStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = Lock()
        self._items: list[dict[str, Any]] = []
        self.reload()

    def reload(self) -> None:
        with self._lock:
            if self.path.exists():
                self._items = json.loads(self.path.read_text(encoding="utf-8"))
            else:
                self._items = []

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._items, indent=2), encoding="utf-8")

    def list(
        self,
        *,
        service: str | None = None,
        from_ts: float | None = None,
        to_ts: float | None = None,
    ) -> list[dict[str, Any]]:
        with self._lock:
            items = list(self._items)
        result = []
        for item in items:
            if service and item["service"] != service:
                continue
            deployed_at = float(item["deployed_at"])
            if from_ts is not None and deployed_at < from_ts:
                continue
            if to_ts is not None and deployed_at > to_ts:
                continue
            result.append(item)
        result.sort(key=lambda x: float(x["deployed_at"]), reverse=True)
        return result

    def add(
        self,
        *,
        service: str,
        version: str,
        commit_sha: str,
        deployed_at: float | None = None,
        deployed_by: str = "ci-bot",
        status: str = "success",
        changelog: str = "",
    ) -> dict[str, Any]:
        record = {
            "deployment_id": f"dep-{uuid.uuid4().hex[:12]}",
            "service": service,
            "version": version,
            "commit_sha": commit_sha,
            "deployed_at": deployed_at if deployed_at is not None else clock.now(),
            "deployed_by": deployed_by,
            "status": status,
            "changelog": changelog,
        }
        with self._lock:
            self._items.append(record)
            self._persist()
        return record

    def get(self, deployment_id: str) -> dict[str, Any] | None:
        with self._lock:
            for item in self._items:
                if item["deployment_id"] == deployment_id:
                    return item
        return None

    def rollback(self, deployment_id: str) -> dict[str, Any]:
        current = self.get(deployment_id)
        if current is None:
            raise KeyError(deployment_id)
        # Mark current as rolled_back and create a rollback deployment to previous version marker.
        with self._lock:
            for item in self._items:
                if item["deployment_id"] == deployment_id:
                    item["status"] = "rolled_back"
            rollback = {
                "deployment_id": f"dep-{uuid.uuid4().hex[:12]}",
                "service": current["service"],
                "version": f"{current['version']}-rollback",
                "commit_sha": current["commit_sha"],
                "deployed_at": clock.now(),
                "deployed_by": "operator",
                "status": "success",
                "changelog": f"Rollback of {deployment_id}",
            }
            self._items.append(rollback)
            self._persist()
        return rollback
