from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import httpx
from opspilot.tools.adapters.base import (
    DeploymentBackend,
    FeatureFlagBackend,
    ServiceCatalogBackend,
)


class SimulatorApiAdapter(DeploymentBackend, FeatureFlagBackend, ServiceCatalogBackend):
    def __init__(
        self,
        *,
        base_url: str,
        data_dir: Path | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.data_dir = data_dir or Path("simulator/data")
        self._client = client
        self._owns_client = client is None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()

    async def list_deployments(
        self,
        *,
        service: str | None,
        from_ts: float | None,
        to_ts: float | None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if service:
            params["service"] = service
        if from_ts is not None:
            params["from_ts"] = from_ts
        if to_ts is not None:
            params["to_ts"] = to_ts
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/sim/deployments", params=params)
            response.raise_for_status()
            items = cast(list[dict[str, Any]], response.json())
            if items:
                return items
        except httpx.HTTPError:
            pass
        return self._load_json_file("deployments.json", service, from_ts, to_ts)

    def _load_json_file(
        self,
        filename: str,
        service: str | None,
        from_ts: float | None,
        to_ts: float | None,
    ) -> list[dict[str, Any]]:
        candidates = [self.data_dir / filename, self.data_dir.parent / filename]
        if self.data_dir.name == "data":
            candidates.append(self.data_dir / filename)
        repo_data = self.data_dir.parent.parent / "data" / filename
        candidates.append(repo_data)
        path = next((p for p in candidates if p.exists()), None)
        if path is None:
            return []
        items = json.loads(path.read_text(encoding="utf-8"))
        result = []
        for item in items:
            if service and item.get("service") != service:
                continue
            deployed_at = float(item.get("deployed_at", 0))
            if from_ts is not None and deployed_at < from_ts:
                continue
            if to_ts is not None and deployed_at > to_ts:
                continue
            result.append(item)
        result.sort(key=lambda x: float(x["deployed_at"]), reverse=True)
        return result

    async def get_deployment(self, deployment_id: str) -> dict[str, Any] | None:
        deployments = await self.list_deployments(service=None, from_ts=None, to_ts=None)
        for dep in deployments:
            if dep.get("deployment_id") == deployment_id:
                return self._enrich_deployment(dep)
        for dep in self._load_json_file("deployments.json", None, None, None):
            if dep.get("deployment_id") == deployment_id:
                return self._enrich_deployment(dep)
        return None

    def _enrich_deployment(self, dep: dict[str, Any]) -> dict[str, Any]:
        enriched = dict(dep)
        enriched["commits"] = [dep.get("commit_sha")]
        enriched["diff_summary"] = dep.get("changelog", "")
        return enriched

    async def list_flags(
        self,
        *,
        service: str | None,
        key: str | None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if service:
            params["service"] = service
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/sim/feature-flags", params=params)
            response.raise_for_status()
            flags = response.json()
        except httpx.HTTPError:
            path = self.data_dir / "feature_flags.json"
            if not path.exists():
                path = self.data_dir.parent.parent / "data" / "feature_flags.json"
            flags = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        if key:
            flags = [f for f in flags if f.get("key") == key]
        return cast(list[dict[str, Any]], flags)

    async def list_services(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "demo-service",
                "description": "Primary demo service with checkout, catalog, and orders endpoints",
                "repository": "simulator/data/repos/demo-service.git",
                "environment": "demo",
                "owner_team": "platform",
            }
        ]

    async def get_health(self, service: str) -> dict[str, Any]:
        try:
            client = await self._get_client()
            health = await client.get(f"{self.base_url}/health")
            health.raise_for_status()
            state = await client.get(f"{self.base_url}/sim/state")
            state.raise_for_status()
            state_body = state.json()
        except httpx.HTTPError:
            health_body = {"status": "ok", "service": service}
            state_body = {"effects": {}, "active": []}
        else:
            health_body = health.json()

        deployments = await self.list_deployments(service=service, from_ts=None, to_ts=None)
        version = deployments[0]["version"] if deployments else "unknown"
        effects = state_body.get("effects", {})
        dependencies = [
            {
                "name": "postgres",
                "status": "degraded" if effects.get("pool_saturation") else "healthy",
            },
            {
                "name": "payments-api",
                "status": "degraded" if effects.get("external_error_rate", 0) > 0.1 else "healthy",
            },
            {"name": "redis", "status": "healthy"},
        ]
        status = (
            "healthy"
            if health_body.get("status") == "ok" and not effects.get("active_scenario_ids")
            else "degraded"
        )
        if effects.get("error_rate", 0) > 0.3:
            status = "unhealthy"
        return {
            "service": service,
            "status": status,
            "version": version,
            "dependencies": dependencies,
            "active_scenarios": effects.get("active_scenario_ids", []),
        }
