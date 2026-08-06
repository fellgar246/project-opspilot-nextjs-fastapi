from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from opspilot.tools.retrieval.fusion import merge_sources, reciprocal_rank_fusion


@dataclass(frozen=True)
class SearchResult:
    score: float
    source: Literal["vector", "lexical", "both"]
    runbook_id: str
    title: str
    heading_path: str
    content: str
    chunk_index: int
    version: int
    service_id: str | None = None


@dataclass(frozen=True)
class SimilarIncidentResult:
    score: float
    source: Literal["vector", "lexical", "both"]
    incident_id: str
    title: str
    service: str
    root_cause: str
    resolution: str


def filter_by_threshold(results: list[SearchResult], *, min_score: float) -> list[SearchResult]:
    return [item for item in results if item.score >= min_score]


__all__ = [
    "SearchResult",
    "SimilarIncidentResult",
    "filter_by_threshold",
    "merge_sources",
    "reciprocal_rank_fusion",
]
