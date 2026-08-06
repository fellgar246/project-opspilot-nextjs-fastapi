from __future__ import annotations

from opspilot.agent.state.schema import (
    Claim,
    EvidenceRef,
    HypothesisDraft,
    NegativeFinding,
    NodeMetric,
    ParseError,
    TimelineEntry,
)


def merge_evidence_refs(
    left: list[EvidenceRef] | None,
    right: list[EvidenceRef] | None,
) -> list[EvidenceRef]:
    merged = list(left or [])
    seen = {item["evidence_id"] for item in merged}
    for item in right or []:
        if item["evidence_id"] not in seen:
            merged.append(item)
            seen.add(item["evidence_id"])
    return merged


def merge_negative_findings(
    left: list[NegativeFinding] | None,
    right: list[NegativeFinding] | None,
) -> list[NegativeFinding]:
    merged = list(left or [])
    keys = {(item["tool_name"], item["service"]) for item in merged}
    for item in right or []:
        key = (item["tool_name"], item["service"])
        if key not in keys:
            merged.append(item)
            keys.add(key)
    return merged


def merge_timeline(
    left: list[TimelineEntry] | None,
    right: list[TimelineEntry] | None,
) -> list[TimelineEntry]:
    merged = list(left or [])
    seen = {(item["occurred_at"], item["title"]) for item in merged}
    for item in right or []:
        key = (item["occurred_at"], item["title"])
        if key not in seen:
            merged.append(item)
            seen.add(key)
    merged.sort(key=lambda entry: entry["occurred_at"])
    return merged


def merge_missing_evidence(left: list[str] | None, right: list[str] | None) -> list[str]:
    merged = list(left or [])
    for item in right or []:
        if item not in merged:
            merged.append(item)
    return merged


def merge_hypotheses(
    left: list[HypothesisDraft] | None,
    right: list[HypothesisDraft] | None,
) -> list[HypothesisDraft]:
    merged = list(left or [])
    seen = {item["statement"] for item in merged}
    for item in right or []:
        if item["statement"] not in seen:
            merged.append(item)
            seen.add(item["statement"])
    return merged


def merge_claims(
    left: list[Claim] | None,
    right: list[Claim] | None,
) -> list[Claim]:
    merged = list(left or [])
    seen = {item["text"] for item in merged}
    for item in right or []:
        if item["text"] not in seen:
            merged.append(item)
            seen.add(item["text"])
    return merged


def merge_completed_nodes(left: list[str] | None, right: list[str] | None) -> list[str]:
    merged = list(left or [])
    for item in right or []:
        if item not in merged:
            merged.append(item)
    return merged


def merge_explored_tools(left: list[str] | None, right: list[str] | None) -> list[str]:
    merged = list(left or [])
    for item in right or []:
        if item not in merged:
            merged.append(item)
    return merged


def merge_errors(left: list[str] | None, right: list[str] | None) -> list[str]:
    return list(left or []) + list(right or [])


def merge_parse_errors(
    left: list[ParseError] | None,
    right: list[ParseError] | None,
) -> list[ParseError]:
    return list(left or []) + list(right or [])


def merge_node_metrics(
    left: list[NodeMetric] | None,
    right: list[NodeMetric] | None,
) -> list[NodeMetric]:
    return list(left or []) + list(right or [])
