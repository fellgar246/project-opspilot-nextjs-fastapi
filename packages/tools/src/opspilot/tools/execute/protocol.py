from __future__ import annotations

from typing import Any, Protocol, runtime_checkable
from uuid import UUID


@runtime_checkable
class ExecutionStore(Protocol):
    async def validate_and_prepare(
        self,
        *,
        approval_id: UUID,
        parameters: dict[str, Any],
    ) -> dict[str, Any]: ...

    async def begin_execution(
        self,
        *,
        validation: dict[str, Any],
        input_payload: dict[str, Any],
    ) -> dict[str, Any]: ...

    async def complete_execution(
        self,
        *,
        execution_id: UUID,
        status: str,
        output_payload: dict[str, Any] | None = None,
        error: str | None = None,
        consume_approval: bool = True,
    ) -> dict[str, Any]: ...
