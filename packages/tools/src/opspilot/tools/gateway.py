from __future__ import annotations

import time
from datetime import datetime
from typing import Any
from uuid import UUID

from opspilot.tools.base import ROLE_ORDER, ToolContext, ToolError, ToolResult, ToolSpec, ToolStatus
from opspilot.tools.config import ToolGatewaySettings, get_tool_settings
from opspilot.tools.normalize import apply_evidence_to_result, normalize_to_evidence
from opspilot.tools.persistence import (
    EvidenceRecord,
    ToolPersistence,
    build_audit_event,
    build_tool_call_record,
)
from opspilot.tools.policies import CircuitBreaker, ConcurrencyLimiter, run_with_retries
from opspilot.tools.registry import ToolRegistry
from opspilot.tools.sanitize import sanitize_value
from pydantic import BaseModel, ValidationError


class ToolGateway:
    def __init__(
        self,
        registry: ToolRegistry,
        persistence: ToolPersistence,
        *,
        settings: ToolGatewaySettings | None = None,
        suspicious_callback: Any | None = None,
        event_publisher: Any | None = None,
    ) -> None:
        self.registry = registry
        self.persistence = persistence
        self.settings = settings or get_tool_settings()
        self.suspicious_callback = suspicious_callback
        self.event_publisher = event_publisher
        self._breakers: dict[str, CircuitBreaker] = {}
        self._limiter = ConcurrencyLimiter(
            global_limit=self.settings.global_concurrency_limit,
            per_tool_limit=self.settings.per_tool_concurrency_limit,
        )
        self._existing_checksums: set[str] = set()

    def _breaker(self, tool_name: str) -> CircuitBreaker:
        if tool_name not in self._breakers:
            self._breakers[tool_name] = CircuitBreaker(
                threshold=self.settings.circuit_breaker_threshold,
                cooldown_seconds=self.settings.circuit_breaker_cooldown_seconds,
            )
        return self._breakers[tool_name]

    async def invoke(
        self,
        tool_name: str,
        payload: dict[str, Any],
        ctx: ToolContext,
        *,
        collect_evidence: bool = True,
    ) -> ToolResult:
        started = time.perf_counter()
        retry_count = 0

        try:
            tool = self.registry.require(tool_name)
        except KeyError:
            return self._result(
                tool_name=tool_name,
                tool_version="unknown",
                status="backend_error",
                started=started,
                error=ToolError(code="unknown_tool", message=f"Unknown tool: {tool_name}"),
            )

        spec = tool.spec
        breaker = self._breaker(tool_name)
        if breaker.is_open():
            return self._result(
                tool_name=spec.name,
                tool_version=spec.version,
                status="circuit_open",
                started=started,
                error=ToolError(code="circuit_open", message="Circuit breaker is open"),
            )

        if ROLE_ORDER[ctx.role] < ROLE_ORDER[spec.required_role]:
            result = self._result(
                tool_name=spec.name,
                tool_version=spec.version,
                status="forbidden",
                started=started,
                error=ToolError(code="forbidden", message="Insufficient role for tool"),
            )
            return await self._finalize(ctx, spec, payload, result, retry_count, None, started)

        if spec.is_write and ctx.approval_id is None:
            result = self._result(
                tool_name=spec.name,
                tool_version=spec.version,
                status="forbidden",
                started=started,
                error=ToolError(
                    code="approval_required",
                    message="Write tools require a valid approval_id",
                ),
            )
            return await self._finalize(ctx, spec, payload, result, retry_count, None, started)

        try:
            validated = spec.input_schema.model_validate(payload)
        except ValidationError as exc:
            return self._result(
                tool_name=spec.name,
                tool_version=spec.version,
                status="invalid_input",
                started=started,
                error=ToolError(
                    code="invalid_input",
                    message="Input validation failed",
                    details={"errors": exc.errors(include_url=False)},
                ),
            )

        if not await self._limiter.try_acquire(tool_name):
            return self._result(
                tool_name=spec.name,
                tool_version=spec.version,
                status="rate_limited",
                started=started,
                error=ToolError(code="rate_limited", message="Concurrency limit reached"),
            )

        evidence_records = None
        if self.event_publisher is not None:
            await self.event_publisher.publish(
                "tool_called",
                {
                    "tool": tool_name,
                    "params_summary": _summarize_params(payload),
                },
            )
        try:
            try:
                output, retry_count = await run_with_retries(
                    lambda: tool.run(validated, ctx),
                    policy=spec.retry_policy,
                    timeout_seconds=spec.timeout_seconds,
                )
                validated_output = spec.output_schema.model_validate(output.model_dump())
                sanitized_output, suspicious_reasons = sanitize_value(
                    validated_output.model_dump(mode="json")
                )
                if suspicious_reasons and self.suspicious_callback:
                    await self.suspicious_callback(ctx, suspicious_reasons)
                validated_output = spec.output_schema.model_validate(sanitized_output)
                breaker.record_success()
                notes = list(getattr(tool, "last_notes", []))
                truncated = bool(getattr(validated_output, "truncated", False))
                result = self._result(
                    tool_name=spec.name,
                    tool_version=spec.version,
                    status="ok",
                    started=started,
                    data=validated_output,
                    truncated=truncated,
                    notes=notes,
                )
                if collect_evidence:
                    evidence_records, evidence_ids = normalize_to_evidence(
                        tool_name=spec.name,
                        payload=validated,
                        output=validated_output,
                        ctx=ctx,
                        collected_at=result_collected_at(started),
                        existing_checksums=self._existing_checksums,
                    )
                    for record in evidence_records:
                        self._existing_checksums.add(record.checksum)
                    result = apply_evidence_to_result(result, evidence_ids)
            except TimeoutError:
                breaker.record_failure()
                result = self._result(
                    tool_name=spec.name,
                    tool_version=spec.version,
                    status="timeout",
                    started=started,
                    error=ToolError(code="timeout", message="Tool execution timed out"),
                )
            except Exception as exc:
                breaker.record_failure()
                result = self._result(
                    tool_name=spec.name,
                    tool_version=spec.version,
                    status="backend_error",
                    started=started,
                    error=ToolError(code="backend_error", message=str(exc)),
                )
        finally:
            await self._limiter.release(tool_name)

        finalized = await self._finalize(
            ctx, spec, payload, result, retry_count, evidence_records, started
        )
        if self.event_publisher is not None:
            await self.event_publisher.publish(
                "tool_result",
                {
                    "tool": tool_name,
                    "status": finalized.status,
                    "latency_ms": finalized.latency_ms,
                    "evidence_count": len(finalized.evidence_ids or []),
                },
            )
        return finalized

    async def _finalize(
        self,
        ctx: ToolContext,
        spec: ToolSpec,
        payload: dict[str, Any],
        result: ToolResult,
        retry_count: int,
        evidence_records: list[EvidenceRecord] | None,
        started: float,
    ) -> ToolResult:
        if result.status == "invalid_input":
            return result
        try:
            stored_ids = await self._persist(
                ctx,
                spec,
                payload,
                result,
                retry_count,
                evidence_records or [],
            )
            if stored_ids:
                result.evidence_ids = stored_ids
        except Exception as exc:
            return self._result(
                tool_name=spec.name,
                tool_version=spec.version,
                status="audit_failed",
                started=started,
                error=ToolError(code="audit_failed", message=str(exc)),
            )
        return result

    async def _persist(
        self,
        ctx: ToolContext,
        spec: ToolSpec,
        payload: dict[str, Any],
        result: ToolResult,
        retry_count: int,
        evidence: list[EvidenceRecord],
    ) -> list[UUID]:
        record = build_tool_call_record(
            ctx=ctx,
            tool_name=spec.name,
            tool_version=spec.version,
            input_payload=payload,
            result=result,
            retry_count=retry_count,
            risk_level=spec.risk_level.value,
            summary_max_chars=self.settings.output_summary_max_chars,
        )
        audit = build_audit_event(
            ctx=ctx,
            tool_call_id=record.id,
            tool_name=spec.name,
            status=result.status,
            latency_ms=result.latency_ms,
        )
        return await self.persistence.persist_invocation(
            tool_call=record,
            audit_event=audit,
            evidence=evidence,
        )

    def _result(
        self,
        *,
        tool_name: str,
        tool_version: str,
        status: ToolStatus,
        started: float,
        data: BaseModel | None = None,
        error: ToolError | None = None,
        truncated: bool = False,
        notes: list[str] | None = None,
    ) -> ToolResult:
        latency_ms = int((time.perf_counter() - started) * 1000)
        return ToolResult(
            status=status,
            tool_name=tool_name,
            tool_version=tool_version,
            data=data,
            error=error,
            latency_ms=latency_ms,
            truncated=truncated,
            notes=notes or [],
        )


def _summarize_params(payload: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, str) and len(value) > 120:
            summary[key] = value[:120] + "…"
        else:
            summary[key] = value
    return summary


def result_collected_at(started: float) -> datetime:
    from datetime import UTC

    return datetime.fromtimestamp(started, tz=UTC)
