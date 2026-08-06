from __future__ import annotations

from typing import Any, Protocol


class MetricsBackend(Protocol):
    async def query_range(
        self,
        *,
        service: str,
        metric: str,
        start: float,
        end: float,
        step: str,
        aggregation: str,
        group_by: list[str] | None,
    ) -> dict[str, Any]: ...


class LogsBackend(Protocol):
    async def search(
        self,
        *,
        service: str,
        query: str,
        start: float,
        end: float,
        level: str | None,
        limit: int,
    ) -> dict[str, Any]: ...


class DeploymentBackend(Protocol):
    async def list_deployments(
        self,
        *,
        service: str | None,
        from_ts: float | None,
        to_ts: float | None,
    ) -> list[dict[str, Any]]: ...

    async def get_deployment(self, deployment_id: str) -> dict[str, Any] | None: ...


class FeatureFlagBackend(Protocol):
    async def list_flags(
        self,
        *,
        service: str | None,
        key: str | None,
    ) -> list[dict[str, Any]]: ...


class GitBackend(Protocol):
    async def list_commits(
        self,
        *,
        repository: str,
        from_ts: float,
        to_ts: float,
        path: str | None,
    ) -> list[dict[str, Any]]: ...

    async def get_pull_request(self, *, repository: str, number: int) -> dict[str, Any] | None: ...


class ServiceCatalogBackend(Protocol):
    async def list_services(self) -> list[dict[str, Any]]: ...

    async def get_health(self, service: str) -> dict[str, Any]: ...
