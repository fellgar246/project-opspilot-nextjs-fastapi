from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol


@dataclass(frozen=True)
class RunbookHit:
    score: float
    source: Literal["vector", "lexical", "both"]
    runbook_id: str
    title: str
    heading_path: str
    content: str
    chunk_index: int
    version: int
    service_name: str | None = None


@dataclass(frozen=True)
class SimilarIncidentHit:
    score: float
    source: Literal["vector", "lexical", "both"]
    incident_id: str
    title: str
    service: str
    root_cause: str
    resolution: str


class RetrievalStore(Protocol):
    async def search_runbooks(
        self,
        query: str,
        *,
        service: str | None = None,
        tags: list[str] | None = None,
        top_k: int = 5,
        query_embedding: list[float] | None = None,
    ) -> list[RunbookHit]: ...

    async def search_similar_incidents(
        self,
        query: str,
        *,
        service: str | None = None,
        time_range: str | None = None,
        top_k: int = 5,
        query_embedding: list[float] | None = None,
    ) -> list[SimilarIncidentHit]: ...
