from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ExecuteSimulatedActionInput(BaseModel):
    approval_id: UUID
    proposed_action_id: UUID
    action_type: Literal["rollback_deployment", "toggle_feature_flag"]
    parameters: dict[str, Any] = Field(default_factory=dict)


class ExecuteSimulatedActionOutput(BaseModel):
    execution_id: UUID
    action_type: str
    status: str
    result: dict[str, Any] = Field(default_factory=dict)
    rolled_back: bool = False
