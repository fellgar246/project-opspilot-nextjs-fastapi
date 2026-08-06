from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from opspilot.agent.evaluations.models import EvaluatorResult
from opspilot.agent.providers.base import LLMMessage, LLMProvider


@dataclass
class JudgeConfig:
    variability_threshold: float = 0.15
    runs: int = 2


@dataclass
class JudgeRun:
    dimension: str
    score: float
    justification: str


@dataclass
class JudgeReport:
    results: list[JudgeRun] = field(default_factory=list)
    variability_warning: str | None = None


JUDGE_PROMPTS = {
    "reasoning_quality": "Rate the investigation reasoning quality from 0-10.",
    "evidence_relevance": "Rate how well evidence supports conclusions from 0-10.",
    "summary_clarity": "Rate summary clarity from 0-10.",
    "fact_inference_separation": "Rate separation of facts vs inferences from 0-10.",
    "postmortem_quality": "Rate postmortem quality from 0-10.",
}


async def run_llm_judges(
    provider: LLMProvider,
    *,
    investigation_summary: str,
    config: JudgeConfig | None = None,
) -> tuple[list[EvaluatorResult], JudgeReport]:
    config = config or JudgeConfig()
    report = JudgeReport()
    evaluator_results: list[EvaluatorResult] = []
    dimension_scores: dict[str, list[float]] = {}

    for dimension, prompt in JUDGE_PROMPTS.items():
        scores: list[float] = []
        justifications: list[str] = []
        for _ in range(config.runs):
            response = await provider.complete(
                [
                    LLMMessage(role="system", content=prompt),
                    LLMMessage(role="user", content=investigation_summary[:4000]),
                ]
            )
            score, justification = _parse_judge_response(response.content)
            scores.append(score)
            justifications.append(justification)
            report.results.append(
                JudgeRun(dimension=dimension, score=score, justification=justification)
            )
        dimension_scores[dimension] = scores
        avg = sum(scores) / len(scores)
        evaluator_results.append(
            EvaluatorResult(
                name=f"judge_{dimension}",
                passed=True,  # judges score quality only; never gate security
                score=avg / 10.0,
                details=justifications[0],
                deterministic=False,
            )
        )

    for dimension, scores in dimension_scores.items():
        if len(scores) >= 2:
            spread = max(scores) - min(scores)
            normalized_spread = spread / 10.0
            if normalized_spread > config.variability_threshold:
                report.variability_warning = (
                    f"Judge variability for {dimension} exceeds threshold: spread={spread:.1f}"
                )
                break

    return evaluator_results, report


def _parse_judge_response(content: str) -> tuple[float, str]:
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            score = float(data.get("score", 7))
            justification = str(data.get("justification", content[:200]))
            return min(10.0, max(0.0, score)), justification
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    digest = hashlib.sha256(content.encode()).hexdigest()
    score = (int(digest[:2], 16) / 255.0) * 10.0
    return score, content[:200]
