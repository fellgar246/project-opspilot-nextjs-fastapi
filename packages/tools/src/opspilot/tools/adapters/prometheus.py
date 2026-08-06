from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from opspilot.tools.adapters.base import MetricsBackend


class PrometheusAdapter(MetricsBackend):
    METRIC_MAP = {
        "http_requests_total": 'sum(rate(http_requests_total{service="%s"}[5m]))',
        "http_request_duration_seconds": (
            'histogram_quantile(0.95, '
            'sum(rate(http_request_duration_seconds_bucket{service="%s"}[5m])) by (le))'
        ),
        "db_pool_connections_in_use": 'db_pool_connections_in_use{service="%s"}',
        "db_pool_wait_seconds": 'db_pool_wait_seconds{service="%s"}',
        "external_dependency_errors_total": (
            'sum(rate(external_dependency_errors_total{service="%s"}[5m]))'
        ),
        "process_resident_memory_bytes": 'process_resident_memory_bytes{service="%s"}',
    }

    def __init__(
        self,
        *,
        prometheus_url: str,
        sim_url: str,
        fixtures_path: Path | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.prometheus_url = prometheus_url.rstrip("/")
        self.sim_url = sim_url.rstrip("/")
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
    ) -> dict[str, Any]:
        try:
            client = await self._get_client()
            promql = self.METRIC_MAP.get(metric, metric).replace("%s", service)
            params = {
                "query": promql,
                "start": start,
                "end": end,
                "step": step,
            }
            response = await client.get(
                f"{self.prometheus_url}/api/v1/query_range",
                params=params,
            )
            response.raise_for_status()
            body = response.json()
            if body.get("status") == "success":
                return self._parse_prometheus(body, metric, service, aggregation)
        except httpx.HTTPError:
            pass

        snapshot = await self._snapshot_from_sim(service)
        if snapshot:
            return self._from_snapshot(snapshot, metric, start, end, service, aggregation)

        if self.fixtures_path and self.fixtures_path.exists():
            return json.loads(self.fixtures_path.read_text(encoding="utf-8"))

        return self._synthetic_series(metric, service, start, end, aggregation)

    def _parse_prometheus(
        self,
        body: dict[str, Any],
        metric: str,
        service: str,
        aggregation: str,
    ) -> dict[str, Any]:
        series: list[dict[str, Any]] = []
        for result in body.get("data", {}).get("result", []):
            for ts, value in result.get("values", []):
                try:
                    numeric = float(value)
                except (TypeError, ValueError):
                    continue
                series.append(
                    {"timestamp": datetime.fromtimestamp(ts, tz=UTC).isoformat(), "value": numeric}
                )
        return {
            "metric": metric,
            "service": service,
            "series": series,
            "statistics": _compute_stats(series, aggregation),
            "baseline_comparison": _baseline_comparison(series),
            "unit": _metric_unit(metric),
        }

    async def _snapshot_from_sim(self, service: str) -> dict[str, float] | None:
        try:
            client = await self._get_client()
            response = await client.get(f"{self.sim_url}/metrics")
            response.raise_for_status()
            return _parse_text_metrics(response.text)
        except httpx.HTTPError:
            return None

    def _from_snapshot(
        self,
        snapshot: dict[str, float],
        metric: str,
        start: float,
        end: float,
        service: str,
        aggregation: str,
    ) -> dict[str, Any]:
        value = snapshot.get(metric, 0.0)
        points = max(2, min(20, int((end - start) / 60)))
        series = []
        for i in range(points):
            ts = start + (end - start) * i / max(points - 1, 1)
            series.append(
                {
                    "timestamp": datetime.fromtimestamp(ts, tz=UTC).isoformat(),
                    "value": value * (1 + 0.05 * (i % 3 - 1)),
                }
            )
        return {
            "metric": metric,
            "service": service,
            "series": series,
            "statistics": _compute_stats(series, aggregation),
            "baseline_comparison": _baseline_comparison(series),
            "unit": _metric_unit(metric),
        }

    def _synthetic_series(
        self,
        metric: str,
        service: str,
        start: float,
        end: float,
        aggregation: str,
    ) -> dict[str, Any]:
        points = max(5, min(30, int((end - start) / 120)))
        series = []
        for i in range(points):
            ts = start + (end - start) * i / max(points - 1, 1)
            series.append(
                {
                    "timestamp": datetime.fromtimestamp(ts, tz=UTC).isoformat(),
                    "value": float(i % 7),
                }
            )
        return {
            "metric": metric,
            "service": service,
            "series": series,
            "statistics": _compute_stats(series, aggregation),
            "baseline_comparison": _baseline_comparison(series),
            "unit": _metric_unit(metric),
        }


def _parse_text_metrics(text: str) -> dict[str, float]:
    values: dict[str, float] = {}
    for line in text.splitlines():
        if line.startswith("#") or not line.strip():
            continue
        match = re.match(
            r"^([a-zA-Z_:][a-zA-Z0-9_:]*(?:\{[^}]*\})?) ([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)$", line
        )
        if not match:
            continue
        name = match.group(1).split("{", 1)[0]
        values[name] = float(match.group(2))
    return values


def _compute_stats(series: list[dict[str, Any]], aggregation: str) -> dict[str, float]:
    if not series:
        return {"min": 0.0, "max": 0.0, "avg": 0.0}
    values = [float(p["value"]) for p in series]
    return {
        "min": min(values),
        "max": max(values),
        "avg": sum(values) / len(values),
        "aggregation": aggregation,
    }


def _baseline_comparison(series: list[dict[str, Any]]) -> dict[str, float]:
    if len(series) < 4:
        return {"delta_pct": 0.0}
    values = [float(p["value"]) for p in series]
    mid = len(values) // 2
    baseline = sum(values[:mid]) / max(mid, 1)
    recent = sum(values[mid:]) / max(len(values) - mid, 1)
    if baseline == 0:
        return {"delta_pct": 0.0}
    return {"delta_pct": round((recent - baseline) / baseline * 100, 2)}


def _metric_unit(metric: str) -> str | None:
    if metric.endswith("_seconds"):
        return "seconds"
    if metric.endswith("_bytes"):
        return "bytes"
    if metric.endswith("_total"):
        return "count"
    return None


def decimate_series(
    series: list[dict[str, Any]], max_points: int
) -> tuple[list[dict[str, Any]], bool]:
    if len(series) <= max_points:
        return series, False
    bucket_size = len(series) / max_points
    decimated: list[dict[str, Any]] = []
    for i in range(max_points):
        start = int(i * bucket_size)
        end = int((i + 1) * bucket_size)
        bucket = series[start:end]
        if not bucket:
            continue
        peak = max(bucket, key=lambda p: float(p["value"]))
        decimated.append(peak)
    return decimated, True
