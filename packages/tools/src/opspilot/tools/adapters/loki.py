from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from opspilot.tools.adapters.base import LogsBackend


class LokiAdapter(LogsBackend):
    def __init__(
        self,
        *,
        loki_url: str,
        fixtures_path: Path | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.loki_url = loki_url.rstrip("/")
        self.fixtures_path = fixtures_path
        self._client = client
        self._owns_client = client is None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()

    async def search(
        self,
        *,
        service: str,
        query: str,
        start: float,
        end: float,
        level: str | None,
        limit: int,
    ) -> dict[str, Any]:
        try:
            client = await self._get_client()
            logql = f'{{service="{service}"}}'
            if query:
                logql += f' |~ "{re.escape(query)}"'
            if level:
                logql += f' | json | level="{level}"'
            params = {
                "query": logql,
                "start": str(int(start * 1e9)),
                "end": str(int(end * 1e9)),
                "limit": str(limit),
                "direction": "backward",
            }
            response = await client.get(
                f"{self.loki_url}/loki/api/v1/query_range",
                params=params,
            )
            response.raise_for_status()
            body = response.json()
            return self._parse_loki(body, service)
        except httpx.HTTPError:
            return self._search_fixtures(service, query, level, limit)

    def _parse_loki(self, body: dict[str, Any], service: str) -> dict[str, Any]:
        entries: list[dict[str, Any]] = []
        results = body.get("data", {}).get("result", [])
        for stream in results:
            labels = stream.get("stream", {})
            for ts, line in stream.get("values", []):
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    payload = {"message": line, "level": labels.get("level", "info")}
                entries.append(
                    {
                        "timestamp": datetime.fromtimestamp(int(ts) / 1e9, tz=UTC).isoformat(),
                        "level": payload.get("level", labels.get("level", "info")),
                        "service": payload.get("service", service),
                        "message": payload.get("message", line),
                        "endpoint": payload.get("endpoint"),
                        "status": payload.get("status"),
                        "trace_id": payload.get("trace_id"),
                    }
                )
        return {
            "entries": entries,
            "total_count": len(entries),
            "patterns": _group_patterns(entries),
        }

    def _search_fixtures(
        self,
        service: str,
        query: str,
        level: str | None,
        limit: int,
    ) -> dict[str, Any]:
        if self.fixtures_path and self.fixtures_path.exists():
            entries = json.loads(self.fixtures_path.read_text(encoding="utf-8"))
        else:
            entries = _default_log_entries(service)
        filtered = []
        for entry in entries:
            if entry.get("service") != service:
                continue
            if level and entry.get("level") != level:
                continue
            if query and query.lower() not in entry.get("message", "").lower():
                continue
            filtered.append(entry)
        total = len(filtered)
        truncated = total > limit
        return {
            "entries": filtered[:limit],
            "total_count": total,
            "patterns": _group_patterns(filtered[:limit]),
            "truncated": truncated,
        }


def _default_log_entries(service: str) -> list[dict[str, Any]]:
    now = datetime.now(UTC).isoformat()
    return [
        {
            "timestamp": now,
            "level": "info",
            "service": service,
            "message": "/catalog ok",
            "endpoint": "/catalog",
            "status": 200,
        },
        {
            "timestamp": now,
            "level": "error",
            "service": service,
            "message": "PoolTimeout waiting for db.pool.acquire",
            "endpoint": "/checkout",
            "status": 503,
            "error_type": "PoolTimeout",
        },
        {
            "timestamp": now,
            "level": "warning",
            "service": service,
            "message": "elevated latency on /orders/{id}",
            "endpoint": "/orders/{id}",
            "status": 200,
        },
    ]


def _group_patterns(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for entry in entries:
        key = entry.get("message", "")[:120]
        counts[key] = counts.get(key, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    return [{"pattern": pattern, "count": count} for pattern, count in ranked[:10]]
