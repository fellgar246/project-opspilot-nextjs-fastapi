from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from openai import AsyncOpenAI
from opspilot.agent.providers.base import (
    LLMMessage,
    LLMProvider,
    LLMResponse,
    TokenUsage,
    ToolCallRequest,
)
from pydantic import BaseModel


class OpenAIProvider(LLMProvider):
    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gpt-4o-mini",
        timeout_seconds: float = 60.0,
    ) -> None:
        self.model = model
        self.timeout_seconds = timeout_seconds
        self._client = AsyncOpenAI(api_key=api_key, timeout=timeout_seconds)

    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        tools: list[dict[str, Any]] | None = None,
        response_model: type[BaseModel] | None = None,
    ) -> LLMResponse:
        started = time.perf_counter()
        payload_messages = [_to_openai_message(msg) for msg in messages]
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": payload_messages,
        }
        if tools:
            kwargs["tools"] = tools
        if response_model is not None:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            response = await asyncio.wait_for(
                self._client.chat.completions.create(**kwargs),
                timeout=self.timeout_seconds,
            )
        except TimeoutError:
            # Single retry per REQ-01
            response = await asyncio.wait_for(
                self._client.chat.completions.create(**kwargs),
                timeout=self.timeout_seconds,
            )

        choice = response.choices[0]
        tool_calls: list[ToolCallRequest] = []
        if choice.message.tool_calls:
            for call in choice.message.tool_calls:
                tool_calls.append(
                    ToolCallRequest(
                        id=call.id,
                        name=call.function.name,
                        arguments=json.loads(call.function.arguments or "{}"),
                    )
                )

        usage = TokenUsage(
            prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
            completion_tokens=response.usage.completion_tokens if response.usage else 0,
        )
        latency_ms = int((time.perf_counter() - started) * 1000)
        return LLMResponse(
            content=choice.message.content,
            tool_calls=tool_calls,
            usage=usage,
            model=response.model,
            latency_ms=latency_ms,
            finish_reason=choice.finish_reason or "stop",
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        response = await self._client.embeddings.create(
            model="text-embedding-3-small",
            input=texts,
        )
        return [item.embedding for item in response.data]


def _to_openai_message(message: LLMMessage) -> dict[str, Any]:
    payload: dict[str, Any] = {"role": message.role}
    if message.content is not None:
        payload["content"] = message.content
    if message.tool_call_id:
        payload["tool_call_id"] = message.tool_call_id
    if message.name:
        payload["name"] = message.name
    return payload
