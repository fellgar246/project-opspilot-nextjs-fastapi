from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_SENSITIVE_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"BEGIN (RSA |EC )?PRIVATE KEY"),
    re.compile(r"(?i)(password|secret|token|api_key)\s*[:=]\s*\S+"),
)


class LangfuseClient:
    """Optional Langfuse integration with graceful degradation and redaction."""

    def __init__(
        self,
        *,
        public_key: str | None = None,
        secret_key: str | None = None,
        host: str | None = None,
        enabled: bool = True,
    ) -> None:
        self._enabled = enabled and bool(public_key and secret_key and host)
        self._client: Any = None
        self._degraded = False
        if self._enabled:
            try:
                from langfuse import Langfuse

                self._client = Langfuse(
                    public_key=public_key,
                    secret_key=secret_key,
                    host=host,
                )
            except Exception:
                logger.warning("langfuse_init_failed", exc_info=True)
                self._enabled = False
                self._degraded = True

    @property
    def degraded(self) -> bool:
        return self._degraded or not self._enabled

    def redact(self, text: str) -> str:
        redacted = text
        for pattern in _SENSITIVE_PATTERNS:
            redacted = pattern.sub("[REDACTED]", redacted)
        return redacted

    def trace_agent_run(
        self,
        *,
        agent_run_id: str,
        incident_id: str,
        model: str,
        prompt_version: str,
        metadata: dict[str, Any] | None = None,
    ) -> Any:
        if not self._enabled or self._client is None:
            return None
        try:
            return self._client.trace(
                name="agent_run",
                id=agent_run_id,
                metadata={
                    "incident_id": incident_id,
                    "model": model,
                    "prompt_version": prompt_version,
                    **(metadata or {}),
                },
            )
        except Exception:
            logger.warning("langfuse_trace_failed", exc_info=True)
            self._degraded = True
            return None

    def log_generation(
        self,
        trace: Any,
        *,
        name: str,
        model: str,
        input_text: str,
        output_text: str,
        tokens: dict[str, int] | None = None,
        latency_ms: int | None = None,
    ) -> None:
        if trace is None:
            return
        try:
            trace.generation(
                name=name,
                model=model,
                input=self.redact(input_text),
                output=self.redact(output_text),
                usage=tokens,
                metadata={"latency_ms": latency_ms},
            )
        except Exception:
            logger.warning("langfuse_generation_failed", exc_info=True)
            self._degraded = True

    def flush(self) -> None:
        if self._client is not None:
            try:
                self._client.flush()
            except Exception:
                logger.warning("langfuse_flush_failed", exc_info=True)
