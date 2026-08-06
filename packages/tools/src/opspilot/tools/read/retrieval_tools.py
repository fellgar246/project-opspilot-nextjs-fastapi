from __future__ import annotations

from opspilot.tools.base import RetryPolicy, RiskLevel, ToolContext, ToolRole, ToolSpec
from opspilot.tools.read.schemas import (
    SearchRunbooksInput,
    SearchRunbooksOutput,
    SearchSimilarIncidentsInput,
    SearchSimilarIncidentsOutput,
)
from opspilot.tools.read.schemas import (
    SimilarIncidentHit as SimilarIncidentHitSchema,
)
from opspilot.tools.retrieval.protocol import RetrievalStore


class SearchRunbooksTool:
    spec = ToolSpec(
        name="search_runbooks",
        version="1.0.0",
        description="Search operational runbooks using hybrid semantic and lexical retrieval.",
        input_schema=SearchRunbooksInput,
        output_schema=SearchRunbooksOutput,
        risk_level=RiskLevel.LOW,
        required_role=ToolRole.VIEWER,
        timeout_seconds=10.0,
        retry_policy=RetryPolicy(max_attempts=2, idempotent=True),
        is_write=False,
    )

    def __init__(self, store: RetrievalStore) -> None:
        self.store = store

    async def run(self, payload: SearchRunbooksInput, ctx: ToolContext) -> SearchRunbooksOutput:
        del ctx
        hits = await self.store.search_runbooks(
            payload.query,
            service=payload.service,
            tags=payload.tags,
            top_k=payload.top_k,
        )
        return SearchRunbooksOutput(
            query=payload.query,
            results=[
                {
                    "score": hit.score,
                    "source": hit.source,
                    "runbook_id": hit.runbook_id,
                    "title": hit.title,
                    "heading_path": hit.heading_path,
                    "content": hit.content,
                    "chunk_index": hit.chunk_index,
                    "version": hit.version,
                }
                for hit in hits
            ],
            total=len(hits),
        )


class SearchSimilarIncidentsTool:
    spec = ToolSpec(
        name="search_similar_incidents",
        version="1.0.0",
        description="Search resolved historical incidents for similar root causes and resolutions.",
        input_schema=SearchSimilarIncidentsInput,
        output_schema=SearchSimilarIncidentsOutput,
        risk_level=RiskLevel.LOW,
        required_role=ToolRole.VIEWER,
        timeout_seconds=10.0,
        retry_policy=RetryPolicy(max_attempts=2, idempotent=True),
        is_write=False,
    )

    def __init__(self, store: RetrievalStore) -> None:
        self.store = store

    async def run(
        self,
        payload: SearchSimilarIncidentsInput,
        ctx: ToolContext,
    ) -> SearchSimilarIncidentsOutput:
        del ctx
        hits = await self.store.search_similar_incidents(
            payload.query,
            service=payload.service,
            time_range=payload.time_range.relative if payload.time_range else None,
            top_k=payload.top_k,
        )
        return SearchSimilarIncidentsOutput(
            query=payload.query,
            results=[
                SimilarIncidentHitSchema(
                    score=hit.score,
                    source=hit.source,
                    incident_id=hit.incident_id,
                    title=hit.title,
                    service=hit.service,
                    root_cause=hit.root_cause,
                    resolution=hit.resolution,
                )
                for hit in hits
            ],
            total=len(hits),
        )
