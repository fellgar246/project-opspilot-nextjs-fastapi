from __future__ import annotations

import pytest
from opspilot.tools.read.retrieval_tools import SearchRunbooksTool, SearchSimilarIncidentsTool
from opspilot.tools.retrieval.memory import InMemoryRetrievalStore, _RunbookRecord


def _vector(seed: float) -> list[float]:
    return [seed] * 768


@pytest.mark.asyncio
async def test_search_runbooks_tool_contract() -> None:
    store = InMemoryRetrievalStore(
        runbooks=[
            _RunbookRecord(
                runbook_id="rb-1",
                title="DB pool exhaustion",
                heading_path="Mitigation",
                content="Increase pool size temporarily",
                chunk_index=0,
                version=1,
                service_name="demo-service",
                embedding=_vector(0.2),
                tags=[],
            )
        ]
    )
    tool = SearchRunbooksTool(store)
    output = await tool.run(
        tool.spec.input_schema(query="db pool exhausted", service="demo-service", top_k=3),
        ctx=None,  # type: ignore[arg-type]
    )
    assert output.total >= 1
    assert output.results[0].runbook_id == "rb-1"


@pytest.mark.asyncio
async def test_search_similar_incidents_tool_contract() -> None:
    from opspilot.tools.retrieval.memory import _IncidentRecord

    store = InMemoryRetrievalStore(
        incidents=[
            _IncidentRecord(
                incident_id="INC-H-001",
                title="Checkout 500s",
                service="demo-service",
                root_cause="Missing PAYMENTS_API_KEY",
                resolution="Re-injected secret",
                search_text="Checkout 500s Missing PAYMENTS_API_KEY",
                embedding=_vector(0.3),
                tags=["historical"],
            )
        ]
    )
    tool = SearchSimilarIncidentsTool(store)
    output = await tool.run(
        tool.spec.input_schema(query="checkout 500 missing key", top_k=3),
        ctx=None,  # type: ignore[arg-type]
    )
    assert output.total == 1
    assert output.results[0].root_cause
