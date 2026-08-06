from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ExpectedSignal:
    name: str
    tool: str
    payload_keys: tuple[str, ...]


HYPOTHESIS_SIGNALS: dict[str, list[ExpectedSignal]] = {
    "deployment_regression": [
        ExpectedSignal("recent_deployment", "get_recent_deployments", ("service",)),
        ExpectedSignal("recent_commits", "get_recent_commits", ("repository",)),
    ],
    "config_error": [
        ExpectedSignal("service_health", "get_service_health", ("service",)),
        ExpectedSignal("error_logs", "search_logs", ("service", "query")),
    ],
    "resource_exhaustion": [
        ExpectedSignal("metrics_anomaly", "query_metrics", ("service", "metric")),
        ExpectedSignal("service_health", "get_service_health", ("service",)),
    ],
    "external_dependency": [
        ExpectedSignal("dependency_health", "get_service_health", ("service",)),
        ExpectedSignal("error_logs", "search_logs", ("service", "query")),
    ],
}


def detect_hypothesis_type(statement: str) -> str:
    text = statement.lower()
    if re.search(r"deploy|release|rollout|canary", text):
        return "deployment_regression"
    if re.search(r"env|config|secret|flag|variable", text):
        return "config_error"
    if re.search(r"pool|memory|cpu|disk|latency|timeout|exhaust", text):
        return "resource_exhaustion"
    if re.search(r"payment|external|dependency|upstream|third.?party", text):
        return "external_dependency"
    return "deployment_regression"


def detect_missing_evidence(
    hypothesis_type: str,
    explored_tools: set[str],
) -> list[ExpectedSignal]:
    expected = HYPOTHESIS_SIGNALS.get(hypothesis_type, [])
    return [signal for signal in expected if signal.tool not in explored_tools]
