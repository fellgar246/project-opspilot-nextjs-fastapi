from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class StartInvestigationResponse(BaseModel):
    agent_run_id: str
    status: str = "pending"


class AgentRunRead(BaseModel):
    id: str
    incident_id: str
    graph_thread_id: str
    status: str
    model: str
    prompt_version: str
    started_at: datetime | None
    completed_at: datetime | None
    token_usage: dict[str, Any]
    estimated_compute_usage: float | None
    error: str | None
    node_progress: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class AgentRunListResponse(BaseModel):
    items: list[AgentRunRead]
