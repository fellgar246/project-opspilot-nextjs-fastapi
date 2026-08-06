from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from opspilot.agent.config import get_agent_settings
from opspilot.agent.nodes.base import as_uuid
from opspilot.agent.state.graph_state import IncidentInvestigationState
from opspilot.tools.config import get_tool_settings


def make_generate_postmortem_node(
    postmortem_store: Any | None = None,
) -> Callable[[IncidentInvestigationState], Awaitable[dict[str, Any]]]:
    async def generate_postmortem(state: IncidentInvestigationState) -> dict[str, Any]:
        tool_settings = get_tool_settings()
        verdict = state.get("recovery_verdict") or {}
        if verdict.get("status") == "recovered":
            await asyncio.sleep(min(tool_settings.recovery_observation_seconds, 1.0))

        content = _build_postmortem_content(state)
        postmortem_id: str | None = None
        postmortem_status = "draft"

        if postmortem_store is not None:
            saved = await postmortem_store.save_generated(
                incident_id=as_uuid(state["incident_id"]),
                content=content,
            )
            postmortem_id = saved.get("id")
            postmortem_status = saved.get("status", "draft")

        return {
            "current_node": "generate_postmortem",
            "completed_nodes": ["generate_postmortem"],
            "postmortem_id": postmortem_id,
            "postmortem_status": postmortem_status,
            "postmortem_content": content,
            "investigation_status": "resolved"
            if verdict.get("status") in {"recovered", "partially_recovered", "inconclusive"}
            else "running",
        }

    return generate_postmortem


def _build_postmortem_content(state: IncidentInvestigationState) -> str:
    incident_id = state["incident_id"]
    lines = [
        f"# Postmortem: {state.get('incident_title', 'Incident')}",
        "",
        "## Executive summary",
        state.get("incident_description", "No description recorded."),
        "",
        "## Impact",
        f"Severity: {state.get('incident_severity', 'unknown')}",
        (
            "Services: "
            f"{', '.join(state.get('affected_services') or state.get('service_names') or [])}"
        ),
        "",
        "## Timeline",
    ]

    for entry in state.get("timeline") or []:
        ref_id = entry.get("id") or entry.get("entry_id")
        if ref_id:
            lines.append(
                f"- {entry.get('timestamp', '')}: {entry.get('summary', '')} [[timeline:{ref_id}]]"
            )
        else:
            lines.append(f"- {entry.get('timestamp', '')}: {entry.get('summary', '')}")

    lines.extend(["", "## Root cause"])
    hypotheses = state.get("hypotheses") or []
    top = max(hypotheses, key=lambda item: item.get("confidence", 0), default=None)
    if top and top.get("confidence", 0) >= get_agent_settings().confidence_threshold:
        hid = top.get("id", "unknown")
        lines.append(f"{top.get('statement', '')} [[hypothesis:{hid}]]")
    else:
        lines.append("No conclusive root cause was established during investigation.")

    lines.extend(["", "## Detection", "Automated monitoring and investigation agent."])

    proposal = state.get("proposal") or {}
    if proposal:
        action_id = state.get("pending_action_id", "unknown")
        lines.extend(
            [
                "",
                "## Mitigation applied",
                f"{proposal.get('description', '')} [[action:{action_id}]]",
            ]
        )

    verdict = state.get("recovery_verdict") or {}
    if verdict:
        lines.extend(
            [
                "",
                "## Verification",
                f"Status: {verdict.get('status', 'unknown')}",
                verdict.get("rationale", ""),
            ]
        )

    lines.extend(
        [
            "",
            "## Learnings",
            "- Review deployment validation gates.",
            "",
            "## Preventive actions (recommendations)",
            "- Add canary deployment requirement [[recommendation:canary]]",
            f"- Incident reference [[incident:{incident_id}]]",
        ]
    )
    return "\n".join(lines)
