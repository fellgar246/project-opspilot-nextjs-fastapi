from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from opspilot.agent.providers.base import LLMMessage, LLMProvider, LLMResponse, TokenUsage
from opspilot.agent.state.schema import (
    CritiqueOutput,
    HypothesesOutput,
    InvestigationPlanOutput,
    TriageOutput,
)
from pydantic import BaseModel


class MockProvider(LLMProvider):
    """Deterministic provider for offline tests and local development."""

    def __init__(self, *, model: str = "mock-v1", adversarial: bool = False) -> None:
        self.model = model
        self.adversarial = adversarial

    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        tools: list[dict[str, Any]] | None = None,
        response_model: type[BaseModel] | None = None,
    ) -> LLMResponse:
        started = time.perf_counter()
        context = _extract_context(messages)
        payload = _build_payload(response_model, context, adversarial=self.adversarial)
        content = json.dumps(payload)
        usage = TokenUsage(
            prompt_tokens=_estimate_tokens(messages),
            completion_tokens=max(1, len(content) // 4),
        )
        latency_ms = int((time.perf_counter() - started) * 1000)
        return LLMResponse(
            content=content,
            usage=usage,
            model=self.model,
            latency_ms=latency_ms,
            finish_reason="stop",
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        from opspilot.agent.retrieval.embeddings import EMBEDDING_DIM, pad_embedding

        vectors: list[list[float]] = []
        for text in texts:
            digest = hashlib.sha256(text.encode()).digest()
            base = [b / 255.0 for b in digest[:16]]
            vectors.append(pad_embedding(base, dim=EMBEDDING_DIM))
        return vectors


def _extract_context(messages: list[LLMMessage]) -> dict[str, Any]:
    context: dict[str, Any] = {}
    for message in messages:
        if not message.content:
            continue
        try:
            data = json.loads(message.content)
            if isinstance(data, dict):
                context.update(data)
        except json.JSONDecodeError:
            if "service" in message.content.lower():
                context.setdefault("service_names", ["demo-service"])
    return context


def _build_payload(
    response_model: type[BaseModel] | None,
    context: dict[str, Any],
    *,
    adversarial: bool,
) -> dict[str, Any]:
    services = context.get("service_names") or ["demo-service"]
    primary = services[0]
    evidence_ids = context.get("evidence_ids") or []

    if response_model is TriageOutput:
        return TriageOutput(
            perceived_severity="sev2",
            affected_services=services,
            time_window={"start": "2026-01-01T00:00:00Z", "end": "2026-01-01T01:00:00Z"},
            reasoning="Mock triage based on incident description and linked services.",
        ).model_dump(mode="json")

    if response_model is InvestigationPlanOutput:
        return InvestigationPlanOutput(
            steps=[
                {
                    "order": 1,
                    "tool": "get_service_health",
                    "question": f"What is the health of {primary}?",
                    "service": primary,
                },
                {
                    "order": 2,
                    "tool": "query_metrics",
                    "question": f"What metrics anomalies exist for {primary}?",
                    "service": primary,
                },
                {
                    "order": 3,
                    "tool": "search_logs",
                    "question": f"What errors appear in logs for {primary}?",
                    "service": primary,
                },
                {
                    "order": 4,
                    "tool": "get_recent_deployments",
                    "question": f"Were there recent deployments for {primary}?",
                    "service": primary,
                },
                {
                    "order": 5,
                    "tool": "get_recent_commits",
                    "question": f"What code changed recently for {primary}?",
                    "service": primary,
                },
            ]
        ).model_dump(mode="json")

    if response_model is HypothesesOutput:
        confidence = 0.4 if adversarial else 0.82
        supporting = evidence_ids[:1] if evidence_ids else []
        hypotheses = [
            {
                "statement": f"Recent deployment or code change degraded {primary}.",
                "confidence": confidence,
                "supporting_evidence": supporting,
                "reasoning": "Mock hypothesis correlating deployment timing with symptoms.",
            }
        ]
        if not adversarial and not supporting:
            hypotheses[0]["supporting_evidence"] = ["00000000-0000-4000-8000-000000000001"]
        return HypothesesOutput(hypotheses=hypotheses).model_dump(mode="json")

    if response_model is CritiqueOutput:
        critiques = []
        for hypothesis in context.get("hypotheses") or []:
            statement = hypothesis.get("statement", "unknown")
            critiques.append(
                {
                    "statement": statement,
                    "counter_evidence": [],
                    "assumptions": ["Timing correlation is unverified"],
                    "would_confirm": ["Deployment logs showing failed rollout"],
                    "would_refute": ["Stable metrics before deploy window"],
                    "verdict": "weak",
                    "suggested_tool": "get_recent_deployments",
                    "suggested_payload": {"service": primary},
                }
            )
        return CritiqueOutput(critiques=critiques).model_dump(mode="json")

    return {"message": "mock response"}


def _estimate_tokens(messages: list[LLMMessage]) -> int:
    total_chars = sum(len(msg.content or "") for msg in messages)
    return max(1, total_chars // 4)
