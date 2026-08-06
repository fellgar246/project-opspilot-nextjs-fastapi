from __future__ import annotations

import logging
from typing import Any, cast
from uuid import UUID

from langgraph.types import Command
from opspilot.agent.config import AgentSettings, get_agent_settings
from opspilot.agent.graph.builder import build_investigation_graph
from opspilot.agent.providers.base import LLMProvider
from opspilot.agent.providers.mock import MockProvider
from opspilot.agent.providers.openai import OpenAIProvider
from opspilot.agent.providers.resilient import ResilientLLMProvider
from opspilot.agent.state.graph_state import IncidentInvestigationState, initial_state
from opspilot.tools.gateway import ToolGateway

logger = logging.getLogger(__name__)

NODE_NAMES = {
    "triage_incident",
    "build_investigation_plan",
    "collect_service_health",
    "collect_metrics",
    "collect_logs",
    "collect_deployments",
    "collect_code_changes",
    "retrieve_runbooks",
    "generate_hypotheses",
    "critique_hypotheses",
    "request_more_evidence",
    "propose_mitigation",
    "risk_assessment",
    "request_human_approval",
    "execute_approved_action",
    "verify_recovery",
    "generate_postmortem",
    "close_investigation",
}


def create_provider(
    settings: AgentSettings | None = None, *, adversarial: bool = False
) -> LLMProvider:
    settings = settings or get_agent_settings()
    if settings.model_provider == "openai":
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY required for openai provider")
        inner: LLMProvider = OpenAIProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    else:
        inner = MockProvider(model="mock-v1", adversarial=adversarial)
    return ResilientLLMProvider(inner)


async def run_investigation(
    *,
    provider: LLMProvider,
    gateway: ToolGateway,
    checkpointer: Any,
    incident: dict[str, Any],
    agent_run_id: UUID,
    graph_thread_id: str,
    settings: AgentSettings | None = None,
    pause_checker: Any | None = None,
    approval_store: Any | None = None,
    event_publisher: Any | None = None,
    postmortem_store: Any | None = None,
    resume_value: dict[str, Any] | None = None,
) -> IncidentInvestigationState:
    settings = settings or get_agent_settings()
    app: Any = build_investigation_graph(
        provider,
        gateway,
        checkpointer=checkpointer,
        approval_store=approval_store,
        postmortem_store=postmortem_store,
    )
    config: Any = {"configurable": {"thread_id": graph_thread_id}}

    if resume_value is not None:
        final_state = cast(IncidentInvestigationState, {})
        async for event in app.astream(
            Command(resume=resume_value),
            config=config,
            stream_mode="values",
        ):
            final_state = event
            await _maybe_publish_state_events(event_publisher, previous=final_state, current=event)
        return final_state

    state = initial_state(
        incident_id=str(incident["id"]),
        agent_run_id=str(agent_run_id),
        graph_thread_id=graph_thread_id,
        incident_title=incident["title"],
        incident_description=incident["description"],
        incident_severity=incident["severity"],
        service_names=incident.get("service_names") or [],
        repository=incident.get("repository"),
        prompt_version=settings.prompt_version,
        model=getattr(provider, "model", settings.openai_model),
        started_at=incident["started_at"],
    )

    if pause_checker and await pause_checker():
        state["paused"] = True
        state["investigation_status"] = "paused"
        return state

    if event_publisher:
        await event_publisher.publish("run_started", {"graph_thread_id": graph_thread_id})

    previous: IncidentInvestigationState = state
    final_state = state

    async for event in app.astream(state, config=config, stream_mode="values"):
        await _maybe_publish_state_events(event_publisher, previous=previous, current=event)
        previous = event
        final_state = event
        if pause_checker and await pause_checker():
            final_state = cast(
                IncidentInvestigationState,
                {**final_state, "paused": True, "investigation_status": "paused"},
            )
            if event_publisher:
                await event_publisher.publish("run_paused", {})
            break

    snapshot = await app.aget_state(config)
    if snapshot.next:
        final_state = {**final_state, "investigation_status": "awaiting_approval"}
        return final_state

    terminal = (
        "run_completed"
        if final_state.get("investigation_status")
        in {
            "completed",
            "awaiting_execution",
        }
        else "run_failed"
    )
    if event_publisher and final_state.get("investigation_status") != "paused":
        await event_publisher.publish(terminal, {"status": final_state.get("investigation_status")})

    return final_state


async def _maybe_publish_state_events(
    publisher: Any | None,
    *,
    previous: IncidentInvestigationState,
    current: IncidentInvestigationState,
) -> None:
    if publisher is None:
        return
    await _maybe_publish_node_events(publisher, previous=previous, current=current)

    prev_errors = set(previous.get("errors") or [])
    curr_errors = current.get("errors") or []
    if len(curr_errors) > len(prev_errors):
        new_error = curr_errors[-1]
        await publisher.publish(
            "node_failed",
            {
                "node": current.get("current_node"),
                "message": new_error,
                "error_type": "node_error",
            },
        )

    prev_evidence = {ref.get("evidence_id") for ref in (previous.get("evidence_refs") or [])}
    for ref in current.get("evidence_refs") or []:
        evidence_id = ref.get("evidence_id")
        if evidence_id and evidence_id not in prev_evidence:
            await publisher.publish(
                "evidence_added",
                {
                    "evidence_id": evidence_id,
                    "source_type": ref.get("source_type"),
                    "title": ref.get("title"),
                    "summary": ref.get("summary"),
                    "tool_name": ref.get("tool_name"),
                },
            )

    prev_hypothesis_ids = {
        item.get("id") for item in (previous.get("hypotheses") or []) if item.get("id")
    }
    for hypothesis in current.get("hypotheses") or []:
        hypothesis_id = hypothesis.get("id")
        if not hypothesis_id:
            continue
        if hypothesis_id not in prev_hypothesis_ids:
            await publisher.publish(
                "hypothesis_added",
                {
                    "hypothesis_id": str(hypothesis_id),
                    "statement": hypothesis.get("statement", "")[:200],
                    "confidence": hypothesis.get("confidence"),
                    "status": hypothesis.get("status"),
                },
            )
        else:
            prev_hypotheses = previous.get("hypotheses") or []
            prev = next(
                (item for item in prev_hypotheses if item.get("id") == hypothesis_id),
                None,
            )
            if prev and (
                prev.get("confidence") != hypothesis.get("confidence")
                or prev.get("status") != hypothesis.get("status")
            ):
                await publisher.publish(
                    "hypothesis_updated",
                    {
                        "hypothesis_id": str(hypothesis_id),
                        "confidence": hypothesis.get("confidence"),
                        "status": hypothesis.get("status"),
                    },
                )


async def _maybe_publish_node_events(
    publisher: Any | None,
    *,
    previous: IncidentInvestigationState,
    current: IncidentInvestigationState,
) -> None:
    if publisher is None:
        return
    prev_node = previous.get("current_node")
    curr_node = current.get("current_node")
    if curr_node and curr_node != prev_node and curr_node in NODE_NAMES:
        await publisher.publish("node_started", {"node": curr_node})
    prev_completed = set(previous.get("completed_nodes") or [])
    curr_completed = set(current.get("completed_nodes") or [])
    for node in curr_completed - prev_completed:
        metrics = next(
            (item for item in (current.get("node_metrics") or []) if item.get("node") == node),
            None,
        )
        await publisher.publish(
            "node_completed",
            {"node": node, "duration_ms": metrics.get("duration_ms") if metrics else None},
        )
