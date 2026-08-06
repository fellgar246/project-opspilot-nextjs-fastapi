from __future__ import annotations

from pathlib import Path
from typing import cast

from opspilot.tools.record_replay import RecordingStore
from pydantic import BaseModel


class SampleOutput(BaseModel):
    value: str


def test_recording_store_roundtrip(tmp_path: Path) -> None:
    store = RecordingStore(tmp_path)
    output = SampleOutput(value="hello")
    payload = {"key": "value"}
    store.save("echo", payload, output)
    loaded = cast(SampleOutput | None, store.load("echo", payload, SampleOutput))
    assert loaded is not None
    assert loaded.value == "hello"


def test_recording_store_missing_fixture(tmp_path: Path) -> None:
    store = RecordingStore(tmp_path)
    assert store.load("missing", {}, SampleOutput) is None
