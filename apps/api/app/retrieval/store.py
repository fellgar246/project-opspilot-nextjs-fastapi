from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from opspilot.agent.retrieval.embeddings import DEFAULT_MODEL_NAME, EMBEDDING_DIM, pad_embedding
from opspilot.tools.retrieval.fusion import merge_sources, reciprocal_rank_fusion
from opspilot.tools.retrieval.protocol import RetrievalStore, RunbookHit, SimilarIncidentHit
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession


class SqlRetrievalStore(RetrievalStore):
    def __init__(
        self,
        session: AsyncSession,
        *,
        min_score: float = 0.01,
        embedding_dim: int = EMBEDDING_DIM,
        model_name: str = DEFAULT_MODEL_NAME,
    ) -> None:
        self.session = session
        self.min_score = min_score
        self.embedding_dim = embedding_dim
        self.model_name = model_name

    async def search_runbooks(
        self,
        query: str,
        *,
        service: str | None = None,
        tags: list[str] | None = None,
        top_k: int = 5,
        query_embedding: list[float] | None = None,
    ) -> list[RunbookHit]:
        del tags  # tag filtering reserved for future metadata
        vector = pad_embedding(query_embedding or [], dim=self.embedding_dim)
        params: dict[str, Any] = {
            "query": query,
            "top_k": top_k,
            "min_score": self.min_score,
            "embedding": str(vector),
        }
        service_filter = ""
        if service:
            service_filter = "AND s.name = :service"
            params["service"] = service

        vector_rows = await self.session.execute(
            text(
                f"""
                SELECT rc.id::text AS chunk_key, rb.id::text AS runbook_id, rb.title,
                       rc.heading_path, rc.content, rc.chunk_index, rb.version,
                       s.name AS service_name,
                       1 - (rc.embedding <=> :embedding::vector) AS score
                FROM runbook_chunks rc
                JOIN runbooks rb ON rb.id = rc.runbook_id
                LEFT JOIN services s ON s.id = rb.service_id
                WHERE rb.is_current = true {service_filter}
                ORDER BY rc.embedding <=> :embedding::vector
                LIMIT :top_k
                """
            ),
            params,
        )
        lexical_rows = await self.session.execute(
            text(
                f"""
                SELECT rc.id::text AS chunk_key, rb.id::text AS runbook_id, rb.title,
                       rc.heading_path, rc.content, rc.chunk_index, rb.version,
                       s.name AS service_name,
                       ts_rank(rc.content_tsv, plainto_tsquery('spanish', :query)) AS score
                FROM runbook_chunks rc
                JOIN runbooks rb ON rb.id = rc.runbook_id
                LEFT JOIN services s ON s.id = rb.service_id
                WHERE rb.is_current = true
                  AND rc.content_tsv @@ plainto_tsquery('spanish', :query)
                  {service_filter}
                ORDER BY score DESC
                LIMIT :top_k
                """
            ),
            params,
        )

        return self._fuse_runbook_rows(
            vector_rows.mappings().all(), lexical_rows.mappings().all(), top_k
        )

    async def search_similar_incidents(
        self,
        query: str,
        *,
        service: str | None = None,
        time_range: str | None = None,
        top_k: int = 5,
        query_embedding: list[float] | None = None,
    ) -> list[SimilarIncidentHit]:
        del time_range
        vector = pad_embedding(query_embedding or [], dim=self.embedding_dim)
        params: dict[str, Any] = {
            "query": query,
            "top_k": top_k,
            "min_score": self.min_score,
            "embedding": str(vector),
        }
        service_filter = ""
        if service:
            service_filter = "AND service_name = :service"
            params["service"] = service

        vector_rows = await self.session.execute(
            text(
                f"""
                SELECT external_id AS incident_id, title, service_name AS service,
                       root_cause, resolution,
                       1 - (embedding <=> :embedding::vector) AS score,
                       external_id AS chunk_key
                FROM historical_incidents
                WHERE true {service_filter}
                ORDER BY embedding <=> :embedding::vector
                LIMIT :top_k
                """
            ),
            params,
        )
        lexical_rows = await self.session.execute(
            text(
                f"""
                SELECT external_id AS incident_id, title, service_name AS service,
                       root_cause, resolution,
                       ts_rank(search_tsv, plainto_tsquery('spanish', :query)) AS score,
                       external_id AS chunk_key
                FROM historical_incidents
                WHERE search_tsv @@ plainto_tsquery('spanish', :query)
                  {service_filter}
                ORDER BY score DESC
                LIMIT :top_k
                """
            ),
            params,
        )
        return self._fuse_incident_rows(
            vector_rows.mappings().all(),
            lexical_rows.mappings().all(),
            top_k,
        )

    def _fuse_runbook_rows(
        self,
        vector_rows: Sequence[Any],
        lexical_rows: Sequence[Any],
        top_k: int,
    ) -> list[RunbookHit]:
        by_key = {row["chunk_key"]: row for row in list(vector_rows) + list(lexical_rows)}
        vector_ranked = [row["chunk_key"] for row in vector_rows]
        lexical_ranked = [row["chunk_key"] for row in lexical_rows]
        fused = reciprocal_rank_fusion([vector_ranked, lexical_ranked])
        source_map = merge_sources(set(vector_ranked), set(lexical_ranked))
        hits: list[RunbookHit] = []
        for key, score in sorted(fused.items(), key=lambda pair: pair[1], reverse=True):
            if score < self.min_score:
                continue
            row = by_key[key]
            hits.append(
                RunbookHit(
                    score=score,
                    source=source_map.get(key, "vector"),
                    runbook_id=row["runbook_id"],
                    title=row["title"],
                    heading_path=row["heading_path"],
                    content=row["content"],
                    chunk_index=row["chunk_index"],
                    version=row["version"],
                    service_name=row.get("service_name"),
                )
            )
            if len(hits) >= top_k:
                break
        return hits

    def _fuse_incident_rows(
        self,
        vector_rows: Sequence[Any],
        lexical_rows: Sequence[Any],
        top_k: int,
    ) -> list[SimilarIncidentHit]:
        by_key = {row["chunk_key"]: row for row in list(vector_rows) + list(lexical_rows)}
        vector_ranked = [row["chunk_key"] for row in vector_rows]
        lexical_ranked = [row["chunk_key"] for row in lexical_rows]
        fused = reciprocal_rank_fusion([vector_ranked, lexical_ranked])
        source_map = merge_sources(set(vector_ranked), set(lexical_ranked))
        hits: list[SimilarIncidentHit] = []
        for key, score in sorted(fused.items(), key=lambda pair: pair[1], reverse=True):
            if score < self.min_score:
                continue
            row = by_key[key]
            hits.append(
                SimilarIncidentHit(
                    score=score,
                    source=source_map.get(key, "vector"),
                    incident_id=row["incident_id"],
                    title=row["title"],
                    service=row["service"],
                    root_cause=row["root_cause"],
                    resolution=row["resolution"],
                )
            )
            if len(hits) >= top_k:
                break
        return hits


async def resolve_service_id(session: AsyncSession, service_name: str | None) -> UUID | None:
    if not service_name:
        return None
    from app.incidents.models import Service

    result = await session.scalar(select(Service.id).where(Service.name == service_name))
    return result
