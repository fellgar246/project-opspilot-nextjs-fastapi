from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from opspilot.tools.base import ToolContext, ToolResult
from opspilot.tools.persistence import EvidenceRecord, compute_evidence_checksum
from opspilot.tools.sanitize import sanitize_value
from pydantic import BaseModel


def _source_reference(tool_name: str, payload: dict[str, Any], time_window: str | None) -> str:
    parts = [tool_name, json.dumps(payload, sort_keys=True, default=str)]
    if time_window:
        parts.append(time_window)
    return "|".join(parts)[:500]


def normalize_to_evidence(
    *,
    tool_name: str,
    payload: BaseModel,
    output: BaseModel,
    ctx: ToolContext,
    collected_at: datetime,
    existing_checksums: set[str] | None = None,
) -> tuple[list[EvidenceRecord], list[UUID]]:
    existing = existing_checksums or set()
    records: list[EvidenceRecord] = []
    evidence_ids: list[UUID] = []
    payload_dict = payload.model_dump(mode="json")
    output_dict = output.model_dump(mode="json")

    def _add(
        *,
        source_type: str,
        title: str,
        content: str,
        structured_data: dict[str, Any],
        observed_at: datetime,
        time_window: str | None = None,
    ) -> None:
        sanitized_content, _ = sanitize_value(content)
        content_str = (
            sanitized_content if isinstance(sanitized_content, str) else str(sanitized_content)
        )
        checksum = compute_evidence_checksum(content_str, structured_data)
        if checksum in existing:
            for record in records:
                if record.checksum == checksum:
                    evidence_ids.append(record.id)
                    return
            return
        record_id = uuid4()
        records.append(
            EvidenceRecord(
                id=record_id,
                incident_id=ctx.incident_id,
                source_type=source_type,
                source_reference=_source_reference(tool_name, payload_dict, time_window),
                title=title,
                content=content_str,
                structured_data=structured_data,
                observed_at=observed_at,
                collected_at=collected_at,
                checksum=checksum,
            )
        )
        existing.add(checksum)
        evidence_ids.append(record_id)

    if tool_name == "get_service_health":
        observed = collected_at
        _add(
            source_type="metric",
            title=f"Health: {output_dict.get('service', 'unknown')}",
            content=json.dumps(output_dict, indent=2),
            structured_data={
                "metric_name": "service_health",
                "value": 1.0 if output_dict.get("status") == "healthy" else 0.0,
                "labels": {"service": str(output_dict.get("service", ""))},
            },
            observed_at=observed,
        )
    elif tool_name == "query_metrics":
        series = output_dict.get("series", [])
        stats = output_dict.get("statistics", {})
        observed = _parse_ts(series[-1]["timestamp"]) if series else collected_at
        _add(
            source_type="metric",
            title=f"Metric {output_dict.get('metric')} ({output_dict.get('service')})",
            content=json.dumps({"statistics": stats, "points": len(series)}, indent=2),
            structured_data={
                "metric_name": str(output_dict.get("metric", "")),
                "value": float(stats.get("max", stats.get("avg", 0.0))),
                "unit": output_dict.get("unit"),
                "labels": {"service": str(output_dict.get("service", ""))},
            },
            observed_at=observed,
            time_window=output_dict.get("time_range_label"),
        )
    elif tool_name == "search_logs":
        entries = output_dict.get("entries", [])
        observed = _parse_ts(entries[0]["timestamp"]) if entries else collected_at
        _add(
            source_type="log",
            title=f"Logs: {output_dict.get('service')} ({output_dict.get('total_count', 0)} total)",
            content=json.dumps(entries[:5], indent=2),
            structured_data={
                "level": entries[0].get("level", "info") if entries else "info",
                "service": str(output_dict.get("service", "")),
            },
            observed_at=observed,
            time_window=output_dict.get("time_range_label"),
        )
    elif tool_name == "get_recent_deployments":
        deployments = output_dict.get("deployments", [])
        for dep in deployments[:3]:
            observed = _parse_ts(dep.get("deployed_at")) or collected_at
            _add(
                source_type="deployment",
                title=f"Deployment {dep.get('version')} ({dep.get('deployment_id')})",
                content=json.dumps(dep, indent=2),
                structured_data={
                    "deployment_id": str(dep.get("deployment_id", "")),
                    "service": str(dep.get("service", "")),
                    "version": str(dep.get("version", "")),
                    "commit_sha": str(dep.get("commit_sha", "")),
                    "deployed_by": str(dep.get("deployed_by", "")),
                    "status": str(dep.get("status", "")),
                },
                observed_at=observed,
                time_window=output_dict.get("time_range_label"),
            )
    elif tool_name == "get_deployment_details":
        dep = output_dict
        observed = _parse_ts(dep.get("deployed_at")) or collected_at
        _add(
            source_type="deployment",
            title=f"Deployment details {dep.get('deployment_id')}",
            content=json.dumps(dep, indent=2),
            structured_data={
                "deployment_id": str(dep.get("deployment_id", "")),
                "service": str(dep.get("service", "")),
                "version": str(dep.get("version", "")),
                "commit_sha": str(dep.get("commit_sha", "")),
                "deployed_by": str(dep.get("deployed_by", "")),
                "status": str(dep.get("status", "")),
            },
            observed_at=observed,
        )
    elif tool_name == "get_recent_commits":
        commits = output_dict.get("commits", [])
        for commit in commits[:5]:
            observed = _parse_ts(commit.get("committed_at")) or collected_at
            _add(
                source_type="commit",
                title=f"Commit {commit.get('sha', '')[:8]}: {commit.get('message', '')[:60]}",
                content=json.dumps(commit, indent=2),
                structured_data={
                    "sha": str(commit.get("sha", "")),
                    "author": str(commit.get("author", "")),
                    "message": str(commit.get("message", "")),
                    "files_changed": commit.get("files_changed", []),
                },
                observed_at=observed,
                time_window=output_dict.get("time_range_label"),
            )
    elif tool_name == "get_pull_request":
        pr = output_dict
        observed = _parse_ts(pr.get("merged_at")) or collected_at
        _add(
            source_type="pull_request",
            title=f"PR #{pr.get('number')}: {pr.get('title')}",
            content=json.dumps(pr, indent=2),
            structured_data={
                "number": int(pr.get("number", 0)),
                "title": str(pr.get("title", "")),
                "author": str(pr.get("author", "")),
                "merged_at": pr.get("merged_at"),
                "commits": pr.get("commits", []),
            },
            observed_at=observed,
        )
    elif tool_name == "get_feature_flags":
        flags = output_dict.get("flags", [])
        for flag in flags:
            observed = _parse_ts(flag.get("updated_at")) or collected_at
            _add(
                source_type="feature_flag",
                title=f"Flag {flag.get('key')} = {flag.get('enabled')}",
                content=json.dumps(flag, indent=2),
                structured_data={
                    "key": str(flag.get("key", "")),
                    "service": str(flag.get("service", "")),
                    "enabled": bool(flag.get("enabled", False)),
                    "rollout_percentage": flag.get("rollout_percentage"),
                },
                observed_at=observed,
            )
    elif tool_name == "list_services":
        services = output_dict.get("services", [])
        for svc in services:
            _add(
                source_type="note",
                title=f"Service catalog: {svc.get('name')}",
                content=json.dumps(svc, indent=2),
                structured_data={"tags": ["service_catalog", str(svc.get("name", ""))]},
                observed_at=collected_at,
            )
    elif tool_name == "search_runbooks":
        for hit in output_dict.get("results", []):
            _add(
                source_type="runbook",
                title=f"Runbook: {hit.get('title')} ({hit.get('heading_path')})",
                content=str(hit.get("content", "")),
                structured_data={
                    "runbook_id": str(hit.get("runbook_id", "")),
                    "title": str(hit.get("title", "")),
                    "section": str(hit.get("heading_path", "")),
                    "relevance": float(hit.get("score", 0.0)),
                },
                observed_at=collected_at,
            )
    elif tool_name == "search_similar_incidents":
        for hit in output_dict.get("results", []):
            _add(
                source_type="similar_incident",
                title=f"Similar incident: {hit.get('title')}",
                content=json.dumps(
                    {
                        "root_cause": hit.get("root_cause"),
                        "resolution": hit.get("resolution"),
                    },
                    indent=2,
                ),
                structured_data={
                    "incident_id": str(hit.get("incident_id", "")),
                    "title": str(hit.get("title", "")),
                    "root_cause": str(hit.get("root_cause", "")),
                    "resolution": str(hit.get("resolution", "")),
                    "similarity_score": float(hit.get("score", 0.0)),
                },
                observed_at=collected_at,
            )

    return records, evidence_ids


def _parse_ts(value: Any) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=UTC)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return datetime.now(UTC)
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    return datetime.now(UTC)


def apply_evidence_to_result(result: ToolResult, evidence_ids: list[UUID]) -> ToolResult:
    result.evidence_ids = evidence_ids
    return result
