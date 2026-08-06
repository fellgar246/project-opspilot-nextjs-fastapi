from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class EvaluationCaseSpec(BaseModel):
    id: str
    scenario_id: str
    input_payload: dict[str, Any]
    expected_root_cause: str | None = None
    acceptable_root_causes: list[str] = Field(default_factory=list)
    expected_tools: list[str] = Field(default_factory=list)
    forbidden_tools: list[str] = Field(default_factory=list)
    unsafe_actions: list[str] = Field(default_factory=list)
    required_evidence_types: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    seed: int = 42


def normalize_root_cause(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.lower())
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def root_cause_similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, normalize_root_cause(left), normalize_root_cause(right)).ratio()


def matches_acceptable_root_cause(
    hypothesis: str,
    *,
    expected: str | None,
    acceptable: list[str],
    threshold: float = 0.72,
) -> bool:
    candidates = [item for item in [expected, *acceptable] if item]
    if not candidates:
        return expected is None
    return any(
        root_cause_similarity(hypothesis, candidate) >= threshold for candidate in candidates
    )


def load_cases(dataset_dir: Path | None = None) -> list[EvaluationCaseSpec]:
    root = dataset_dir or Path(__file__).resolve().parents[6] / "datasets" / "evaluations"
    cases: list[EvaluationCaseSpec] = []
    for path in sorted(root.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            cases.extend(EvaluationCaseSpec.model_validate(item) for item in data)
        else:
            cases.append(EvaluationCaseSpec.model_validate(data))
    return cases


@dataclass
class EvaluatorResult:
    name: str
    passed: bool
    score: float | None = None
    details: str = ""
    deterministic: bool = True


@dataclass
class CaseRunResult:
    case_id: str
    status: str  # passed | failed | errored
    trace_reference: str | None = None
    agent_run_id: str | None = None
    evaluator_results: list[EvaluatorResult] = field(default_factory=list)
    duration_seconds: float = 0.0
    error: str | None = None
    actual_tools: list[str] = field(default_factory=list)
    actual_hypotheses: list[str] = field(default_factory=list)
    token_usage: dict[str, int] = field(default_factory=dict)
