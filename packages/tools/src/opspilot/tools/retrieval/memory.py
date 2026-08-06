from __future__ import annotations

import math
import re
from dataclasses import dataclass

from opspilot.tools.retrieval.fusion import merge_sources, reciprocal_rank_fusion
from opspilot.tools.retrieval.protocol import RetrievalStore, RunbookHit, SimilarIncidentHit


@dataclass
class _RunbookRecord:
    runbook_id: str
    title: str
    heading_path: str
    content: str
    chunk_index: int
    version: int
    service_name: str | None
    embedding: list[float]
    tags: list[str]


@dataclass
class _IncidentRecord:
    incident_id: str
    title: str
    service: str
    root_cause: str
    resolution: str
    search_text: str
    embedding: list[float]
    tags: list[str]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _lexical_score(query: str, text: str) -> float:
    tokens = {token for token in re.findall(r"\w+", query.lower()) if len(token) > 2}
    if not tokens:
        return 0.0
    haystack = text.lower()
    hits = sum(1 for token in tokens if token in haystack)
    return hits / len(tokens)


class InMemoryRetrievalStore(RetrievalStore):
    def __init__(
        self,
        *,
        min_score: float = 0.01,
        runbooks: list[_RunbookRecord] | None = None,
        incidents: list[_IncidentRecord] | None = None,
    ) -> None:
        self.min_score = min_score
        self.runbooks = runbooks or []
        self.incidents = incidents or []

    async def search_runbooks(
        self,
        query: str,
        *,
        service: str | None = None,
        tags: list[str] | None = None,
        top_k: int = 5,
        query_embedding: list[float] | None = None,
    ) -> list[RunbookHit]:
        candidates = self.runbooks
        if service:
            candidates = [item for item in candidates if item.service_name == service]
        if tags:
            tag_set = set(tags)
            candidates = [item for item in candidates if tag_set.intersection(item.tags)]

        vector_ranked: list[str] = []
        lexical_ranked: list[str] = []
        vector_scores: dict[str, float] = {}
        lexical_scores: dict[str, float] = {}

        for item in candidates:
            key = f"{item.runbook_id}:{item.chunk_index}"
            if query_embedding is not None:
                vector_scores[key] = _cosine(query_embedding, item.embedding)
            lexical_scores[key] = _lexical_score(query, item.content)

        vector_ranked = sorted(vector_scores, key=lambda k: vector_scores[k], reverse=True)
        lexical_ranked = sorted(lexical_scores, key=lambda k: lexical_scores[k], reverse=True)
        fused = reciprocal_rank_fusion([vector_ranked, lexical_ranked])
        source_map = merge_sources(set(vector_ranked), set(lexical_ranked))

        by_key = {f"{item.runbook_id}:{item.chunk_index}": item for item in candidates}
        hits: list[RunbookHit] = []
        for key, score in sorted(fused.items(), key=lambda pair: pair[1], reverse=True):
            if score < self.min_score:
                continue
            record = by_key.get(key)
            if record is None:
                continue
            hits.append(
                RunbookHit(
                    score=score,
                    source=source_map.get(key, "vector"),
                    runbook_id=record.runbook_id,
                    title=record.title,
                    heading_path=record.heading_path,
                    content=record.content,
                    chunk_index=record.chunk_index,
                    version=record.version,
                    service_name=record.service_name,
                )
            )
            if len(hits) >= top_k:
                break
        return hits

    async def search_similar_incidents(
        self,
        query: str,
        *,
        service: str | None = None,
        time_range: str | None = None,
        top_k: int = 5,
        query_embedding: list[float] | None = None,
    ) -> list[SimilarIncidentHit]:
        del time_range  # historical corpus is static; filter reserved for SQL store
        candidates = self.incidents
        if service:
            candidates = [item for item in candidates if item.service == service]

        vector_scores: dict[str, float] = {}
        lexical_scores: dict[str, float] = {}
        for item in candidates:
            if query_embedding is not None:
                vector_scores[item.incident_id] = _cosine(query_embedding, item.embedding)
            lexical_scores[item.incident_id] = _lexical_score(query, item.search_text)

        vector_ranked = sorted(vector_scores, key=lambda k: vector_scores[k], reverse=True)
        lexical_ranked = sorted(lexical_scores, key=lambda k: lexical_scores[k], reverse=True)
        fused = reciprocal_rank_fusion([vector_ranked, lexical_ranked])
        source_map = merge_sources(set(vector_ranked), set(lexical_ranked))
        by_id = {item.incident_id: item for item in candidates}

        hits: list[SimilarIncidentHit] = []
        for incident_id, score in sorted(fused.items(), key=lambda pair: pair[1], reverse=True):
            if score < self.min_score:
                continue
            record = by_id.get(incident_id)
            if record is None:
                continue
            hits.append(
                SimilarIncidentHit(
                    score=score,
                    source=source_map.get(incident_id, "vector"),
                    incident_id=record.incident_id,
                    title=record.title,
                    service=record.service,
                    root_cause=record.root_cause,
                    resolution=record.resolution,
                )
            )
            if len(hits) >= top_k:
                break
        return hits
