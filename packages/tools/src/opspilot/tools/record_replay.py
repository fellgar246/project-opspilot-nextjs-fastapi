from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel


def _fixture_key(tool_name: str, payload: dict[str, Any]) -> str:
    normalized = json.dumps(payload, sort_keys=True, default=str)
    digest = hashlib.sha256(normalized.encode()).hexdigest()[:16]
    return f"{tool_name}__{digest}.json"


class RecordingStore:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    def save(self, tool_name: str, payload: dict[str, Any], output: BaseModel) -> None:
        path = self.directory / _fixture_key(tool_name, payload)
        path.write_text(
            json.dumps(
                {
                    "tool_name": tool_name,
                    "payload": payload,
                    "output": output.model_dump(mode="json"),
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def load(
        self, tool_name: str, payload: dict[str, Any], output_schema: type[BaseModel]
    ) -> BaseModel | None:
        path = self.directory / _fixture_key(tool_name, payload)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return output_schema.model_validate(data["output"])


class ReplayBackend:
    """Wraps a backend to record or replay responses."""

    def __init__(
        self,
        *,
        mode: str,
        store: RecordingStore,
        live_backend: Any,
    ) -> None:
        self.mode = mode
        self.store = store
        self.live = live_backend

    async def call(
        self,
        tool_name: str,
        payload: dict[str, Any],
        output_schema: type[BaseModel],
        method: str,
        *args: Any,
        **kwargs: Any,
    ) -> BaseModel:
        if self.mode == "replay":
            cached = self.store.load(tool_name, payload, output_schema)
            if cached is not None:
                return cached
            raise RuntimeError(f"No replay fixture for {tool_name}")

        fn = getattr(self.live, method)
        result = await fn(*args, **kwargs)
        if self.mode == "record":
            self.store.save(tool_name, payload, result)
        return cast(BaseModel, result)
