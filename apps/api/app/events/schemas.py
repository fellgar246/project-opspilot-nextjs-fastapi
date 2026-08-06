from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class InvestigationEventRead(BaseModel):
    id: str
    incident_id: str
    agent_run_id: str | None
    seq: int
    type: str
    occurred_at: datetime
    payload: dict[str, Any]


class InvestigationEventListResponse(BaseModel):
    items: list[InvestigationEventRead]
    latest_seq: int
