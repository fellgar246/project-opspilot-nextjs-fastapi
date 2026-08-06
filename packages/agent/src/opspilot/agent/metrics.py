from __future__ import annotations

from collections import defaultdict
from typing import Any

NODE_METRICS: dict[str, list[dict[str, Any]]] = defaultdict(list)


def record_node_metric(
    *,
    node: str,
    duration_ms: int,
    prompt_tokens: int,
    completion_tokens: int,
    retries: int = 0,
) -> None:
    NODE_METRICS[node].append(
        {
            "duration_ms": duration_ms,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "retries": retries,
        }
    )


def get_node_metrics() -> dict[str, list[dict[str, Any]]]:
    return dict(NODE_METRICS)


def reset_node_metrics() -> None:
    NODE_METRICS.clear()
