from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from opspilot.agent.state.reducers import merge_evidence_refs, merge_timeline
from opspilot.agent.state.schema import EvidenceRef


def test_merge_evidence_refs_is_lossless_under_concurrency() -> None:
    left = [
        EvidenceRef(
            evidence_id="a",
            source_type="metric",
            title="A",
            summary="s",
            tool_name="query_metrics",
        )
    ]
    right = [
        EvidenceRef(
            evidence_id="b",
            source_type="log",
            title="B",
            summary="s",
            tool_name="search_logs",
        )
    ]

    def merge_pair():
        return merge_evidence_refs(left, right)

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: merge_pair(), range(8)))
    for merged in results:
        assert {item["evidence_id"] for item in merged} == {"a", "b"}


def test_merge_timeline_sorts_entries() -> None:
    merged = merge_timeline(
        [{"occurred_at": "2026-01-02T00:00:00Z", "kind": "evidence", "title": "b", "summary": "", "evidence_id": None}],
        [{"occurred_at": "2026-01-01T00:00:00Z", "kind": "evidence", "title": "a", "summary": "", "evidence_id": None}],
    )
    assert merged[0]["title"] == "a"
