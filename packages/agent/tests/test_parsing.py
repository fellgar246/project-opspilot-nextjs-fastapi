from __future__ import annotations

import pytest
from opspilot.agent.parsing import (
    get_parse_error_count,
    parse_structured_output,
    reset_parse_error_count,
)
from opspilot.agent.providers.base import LLMMessage, LLMResponse, LLMProvider
from opspilot.agent.providers.mock import MockProvider
from opspilot.agent.state.schema import TriageOutput


from pydantic import BaseModel


class _BrokenProvider(MockProvider):
    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        tools: list[dict[str, object]] | None = None,
        response_model: type[BaseModel] | None = None,
    ) -> LLMResponse:
        if response_model is TriageOutput:
            from opspilot.agent.providers.base import TokenUsage

            return LLMResponse(
                content="not-json", usage=TokenUsage(prompt_tokens=1, completion_tokens=1)
            )
        return await super().complete(messages, tools=tools, response_model=response_model)


class _RepairProvider(MockProvider):
    def __init__(self) -> None:
        super().__init__()
        self.attempts = 0

    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        tools: list[dict[str, object]] | None = None,
        response_model: type[BaseModel] | None = None,
    ) -> LLMResponse:
        if response_model is TriageOutput:
            self.attempts += 1
            if self.attempts == 1:
                from opspilot.agent.providers.base import TokenUsage

                return LLMResponse(
                    content="not-json", usage=TokenUsage(prompt_tokens=1, completion_tokens=1)
                )
        return await super().complete(messages, tools=tools, response_model=response_model)


@pytest.mark.asyncio
async def test_parse_structured_output_records_errors_on_failure() -> None:
    reset_parse_error_count()
    provider = _BrokenProvider()
    parsed, _, errors = await parse_structured_output(
        provider,
        messages=[LLMMessage(role="user", content="{}")],
        response_model=TriageOutput,
        node="triage_incident",
        max_repairs=0,
    )
    assert parsed is None
    assert errors
    assert get_parse_error_count() >= 1


@pytest.mark.asyncio
async def test_parse_structured_output_repairs_malformed_json() -> None:
    reset_parse_error_count()
    provider = _RepairProvider()
    parsed, _, errors = await parse_structured_output(
        provider,
        messages=[LLMMessage(role="user", content="{}")],
        response_model=TriageOutput,
        node="triage_incident",
    )
    assert parsed is not None
    assert not errors
