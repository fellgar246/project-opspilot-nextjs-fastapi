from __future__ import annotations

import pytest
from opspilot.agent.retrieval.embeddings import (
    EMBEDDING_DIM,
    EmbeddingDimensionError,
    pad_embedding,
)
from opspilot.agent.scoring.missing_evidence import detect_hypothesis_type, detect_missing_evidence
from opspilot.tools.retrieval.memory import InMemoryRetrievalStore, _RunbookRecord


def test_pad_embedding_to_expected_dim() -> None:
    assert len(pad_embedding([0.1, 0.2], dim=EMBEDDING_DIM)) == EMBEDDING_DIM


def test_missing_evidence_for_deployment_regression() -> None:
    hypothesis_type = detect_hypothesis_type("Canary rollout caused latency regression")
    missing = detect_missing_evidence(hypothesis_type, explored_tools=set())
    assert {item.tool for item in missing} == {"get_recent_deployments", "get_recent_commits"}


@pytest.mark.asyncio
async def test_in_memory_hybrid_search_returns_hits() -> None:
    vector = pad_embedding([0.5] * 16)
    store = InMemoryRetrievalStore(
        runbooks=[
            _RunbookRecord(
                runbook_id="rb-1",
                title="Missing env",
                heading_path="Remediation",
                content="Check PAYMENTS_API_KEY in deploy manifest",
                chunk_index=0,
                version=1,
                service_name="demo-service",
                embedding=vector,
                tags=[],
            )
        ]
    )
    hits = await store.search_runbooks("missing env variable", service="demo-service", top_k=3)
    assert hits
    assert hits[0].runbook_id == "rb-1"


def test_embedding_dimension_error_message() -> None:
    with pytest.raises(EmbeddingDimensionError):
        raise EmbeddingDimensionError("bad dim")


@pytest.mark.asyncio
async def test_embed_texts_batched() -> None:
    from opspilot.agent.retrieval.embeddings import embed_texts_batched

    async def _embed(texts: list[str]) -> list[list[float]]:
        return [[0.1] * 16 for _ in texts]

    vectors = await embed_texts_batched(_embed, ["a", "b"], batch_size=1, concurrency=1)
    assert len(vectors) == 2
    assert len(vectors[0]) == EMBEDDING_DIM


def test_hybrid_search_filter_threshold() -> None:
    from opspilot.agent.retrieval.hybrid_search import SearchResult, filter_by_threshold

    results = [
        SearchResult(
            score=0.5,
            source="vector",
            runbook_id="rb",
            title="t",
            heading_path="h",
            content="c",
            chunk_index=0,
            version=1,
        ),
        SearchResult(
            score=0.01,
            source="lexical",
            runbook_id="rb2",
            title="t2",
            heading_path="h2",
            content="c2",
            chunk_index=0,
            version=1,
        ),
    ]
    filtered = filter_by_threshold(results, min_score=0.1)
    assert len(filtered) == 1
