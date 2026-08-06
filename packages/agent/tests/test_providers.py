from __future__ import annotations

import json

import pytest
from opspilot.agent.providers.base import LLMMessage, LLMProvider, LLMResponse
from opspilot.agent.providers.mock import MockProvider
from opspilot.agent.providers.resilient import ResilientLLMProvider
from opspilot.agent.state.schema import HypothesesOutput, InvestigationPlanOutput, TriageOutput
from pydantic import BaseModel


class _TimeoutProvider(LLMProvider):
    model = "timeout-test"

    def __init__(self) -> None:
        self.calls = 0

    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        tools: list[dict[str, object]] | None = None,
        response_model: type[BaseModel] | None = None,
    ) -> LLMResponse:
        self.calls += 1
        if self.calls < 3:
            raise TimeoutError("timeout")
        return await MockProvider().complete(messages, tools=tools, response_model=response_model)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return await MockProvider().embed(texts)


@pytest.mark.asyncio
async def test_mock_provider_triage_is_deterministic() -> None:
    provider = MockProvider()
    messages = [LLMMessage(role="user", content=json.dumps({"service_names": ["billing"]}))]
    first = await provider.complete(messages, response_model=TriageOutput)
    second = await provider.complete(messages, response_model=TriageOutput)
    assert first.content == second.content
    parsed = TriageOutput.model_validate_json(first.content or "{}")
    assert parsed.affected_services == ["billing"]


@pytest.mark.asyncio
async def test_mock_provider_plan_and_hypotheses() -> None:
    provider = MockProvider()
    messages = [LLMMessage(role="user", content="{}")]
    plan = await provider.complete(messages, response_model=InvestigationPlanOutput)
    assert InvestigationPlanOutput.model_validate_json(plan.content or "{}").steps
    hyp = await provider.complete(
        [LLMMessage(role="user", content=json.dumps({"evidence_ids": ["ev-1"]}))],
        response_model=HypothesesOutput,
    )
    output = HypothesesOutput.model_validate_json(hyp.content or "{}")
    assert output.hypotheses[0].supporting_evidence == ["ev-1"]


@pytest.mark.asyncio
async def test_resilient_provider_degrades_after_timeout() -> None:
    inner = _TimeoutProvider()
    provider = ResilientLLMProvider(inner)
    response = await provider.complete(
        [LLMMessage(role="user", content="{}")],
        response_model=TriageOutput,
    )
    assert response.content is None
    assert response.finish_reason == "timeout"
    assert inner.calls == 2
