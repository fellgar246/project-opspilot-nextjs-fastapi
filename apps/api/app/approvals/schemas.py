from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ProposedActionRead(BaseModel):
    id: str
    incident_id: str
    agent_run_id: str
    action_type: str
    description: str
    target: str
    parameters: dict[str, Any]
    risk_level: str
    risk_rationale: str
    expected_result: str
    rollback_plan: str
    supporting_evidence: list[str]
    hypothesis_ids: list[str]
    status: str
    requested_by: str | None
    created_at: datetime


class ApprovalRead(BaseModel):
    id: str
    proposed_action_id: str
    incident_id: str
    incident_title: str
    incident_severity: str
    action: ProposedActionRead
    decision: str
    reason: str | None
    expires_at: datetime
    requested_at: datetime
    reviewed_at: datetime | None
    reviewed_by: str | None


class ApprovalListResponse(BaseModel):
    items: list[ApprovalRead]


class ApprovalDecisionRequest(BaseModel):
    reason: str | None = None


class RejectApprovalRequest(BaseModel):
    reason: str = Field(min_length=1)


class ProposedActionListResponse(BaseModel):
    items: list[ProposedActionRead]
