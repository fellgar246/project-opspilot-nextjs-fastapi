from __future__ import annotations

import logging
import time
from typing import Any

from opspilot.agent.providers.base import LLMMessage, LLMProvider, LLMResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ResilientLLMProvider(LLMProvider):
    """Retries once on timeout and records degraded errors instead of aborting."""

    def __init__(self, inner: LLMProvider) -> None:
        self.inner = inner
        self.last_error: str | None = None

    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        tools: list[dict[str, Any]] | None = None,
        response_model: type[BaseModel] | None = None,
    ) -> LLMResponse:
        for attempt in range(2):
            try:
                return await self.inner.complete(
                    messages, tools=tools, response_model=response_model
                )
            except TimeoutError as exc:
                self.last_error = str(exc)
                logger.warning("llm_timeout attempt=%s", attempt + 1)
                if attempt == 1:
                    return LLMResponse(
                        content=None,
                        model=getattr(self.inner, "model", "unknown"),
                        latency_ms=0,
                        finish_reason="timeout",
                    )
            except Exception as exc:
                self.last_error = str(exc)
                logger.warning("llm_error attempt=%s error=%s", attempt + 1, exc)
                if attempt == 1:
                    return LLMResponse(
                        content=None,
                        model=getattr(self.inner, "model", "unknown"),
                        latency_ms=0,
                        finish_reason="error",
                    )
            time.sleep(0.01)
        return LLMResponse(content=None, finish_reason="error")

    async def embed(self, texts: list[str]) -> list[list[float]]:
        try:
            return await self.inner.embed(texts)
        except Exception:
            return [[0.0] * 16 for _ in texts]
