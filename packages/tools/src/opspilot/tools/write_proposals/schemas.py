from __future__ import annotations

from pydantic import BaseModel, Field


class ProposeRollbackInput(BaseModel):
    service: str
    deployment_id: str
    hypothesis_ids: list[str] = Field(min_length=1)
    supporting_evidence: list[str] = Field(min_length=1)
    expected_result: str
    rollback_plan: str = Field(min_length=1)
    description: str = "Rollback deployment to previous stable version"


class ProposeRollbackOutput(BaseModel):
    action_type: str = "rollback_deployment"
    target: str
    parameters: dict
    description: str
    expected_result: str
    rollback_plan: str
    hypothesis_ids: list[str]
    supporting_evidence: list[str]


class ProposeFeatureFlagChangeInput(BaseModel):
    service: str
    flag_name: str
    desired_value: bool
    hypothesis_ids: list[str] = Field(min_length=1)
    supporting_evidence: list[str] = Field(min_length=1)
    expected_result: str
    rollback_plan: str = Field(min_length=1)
    description: str = "Toggle feature flag to mitigate incident"


class ProposeFeatureFlagChangeOutput(BaseModel):
    action_type: str = "toggle_feature_flag"
    target: str
    parameters: dict
    description: str
    expected_result: str
    rollback_plan: str
    hypothesis_ids: list[str]
    supporting_evidence: list[str]
