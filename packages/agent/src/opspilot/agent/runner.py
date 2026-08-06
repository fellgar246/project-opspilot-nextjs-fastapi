from __future__ import annotations

from typing import Any
from uuid import UUID

from langgraph.checkpoint.base import BaseCheckpointSaver
from opspilot.agent.config import AgentSettings, get_agent_settings
from opspilot.agent.graph.builder import build_investigation_graph
from opspilot.agent.providers.base import LLMProvider
from opspilot.agent.providers.mock import MockProvider
from opspilot.agent.providers.openai import OpenAIProvider
from opspilot.agent.providers.resilient import ResilientLLMProvider
from opspilot.agent.state.graph_state import IncidentInvestigationState, initial_state
from opspilot.tools.gateway import ToolGateway


def create_provider(
    settings: AgentSettings | None = None, *, adversarial: bool = False
) -> LLMProvider:
    settings = settings or get_agent_settings()
    if settings.model_provider == "openai":
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY required for openai provider")
        inner = OpenAIProvider(
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
    checkpointer: BaseCheckpointSaver,
    incident: dict[str, Any],
    agent_run_id: UUID,
    graph_thread_id: str,
    settings: AgentSettings | None = None,
    pause_checker: Any | None = None,
) -> IncidentInvestigationState:
    settings = settings or get_agent_settings()
    app = build_investigation_graph(provider, gateway, checkpointer=checkpointer)
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
    config = {"configurable": {"thread_id": graph_thread_id}}

    if pause_checker and await pause_checker():
        state["paused"] = True
        state["investigation_status"] = "paused"
        return state

    final_state: IncidentInvestigationState = state
    async for event in app.astream(state, config=config, stream_mode="values"):
        final_state = event
        if pause_checker and await pause_checker():
            final_state = {**final_state, "paused": True, "investigation_status": "paused"}
            break
    return final_state
