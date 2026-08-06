from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class EvaluationCaseRead(BaseModel):
    id: str
    scenario_id: str
    input_payload: dict[str, Any]
    expected_root_cause: str | None
    acceptable_root_causes: list[str]
    expected_tools: list[str]
    forbidden_tools: list[str]
    unsafe_actions: list[str]
    required_evidence_types: list[str]
    tags: list[str]
    seed: int


class EvaluationRunRequest(BaseModel):
    tags: list[str] = Field(default_factory=list)
    smoke: bool = False
    concurrency: int = 4


class EvaluatorResultRead(BaseModel):
    name: str
    passed: bool
    score: float | None = None
    details: str = ""
    deterministic: bool = True


class EvaluationCaseResultRead(BaseModel):
    case_id: str
    status: str
    trace_reference: str | None = None
    duration_seconds: float
    error: str | None = None
    evaluator_results: list[EvaluatorResultRead] = Field(default_factory=list)


class EvaluationRunRead(BaseModel):
    id: str
    status: str
    model_provider: str
    prompt_version: str
    git_sha: str
    tags_filter: list[str]
    metrics: dict[str, Any]
    gate_passed: bool
    gate_failures: list[str]
    report_json_path: str | None = None
    report_html_path: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
    case_results: list[EvaluationCaseResultRead] = Field(default_factory=list)


class EvaluationRunListResponse(BaseModel):
    items: list[EvaluationRunRead]
    total: int


class EvaluationCompareRequest(BaseModel):
    baseline_run_id: UUID
    candidate_run_id: UUID
