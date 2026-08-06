from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, Field, model_validator

RELATIVE_PATTERN = re.compile(r"^last_(\d+)(m|h|d)$")


class TimeRangeInput(BaseModel):
    from_ts: datetime | None = Field(default=None, alias="from")
    to_ts: datetime | None = Field(default=None, alias="to")
    relative: str | None = None

    model_config = {"populate_by_name": True}

    @model_validator(mode="after")
    def _validate_range(self) -> TimeRangeInput:
        if self.relative and (self.from_ts or self.to_ts):
            raise ValueError("Provide either relative or absolute range, not both")
        if not self.relative and not self.from_ts and not self.to_ts:
            raise ValueError("Time range requires relative or absolute bounds")
        return self


def _parse_relative(relative: str, now: datetime) -> tuple[datetime, datetime]:
    match = RELATIVE_PATTERN.match(relative.strip())
    if not match:
        raise ValueError(f"Invalid relative time range: {relative}")
    amount = int(match.group(1))
    unit = match.group(2)
    if unit == "m":
        delta = timedelta(minutes=amount)
    elif unit == "h":
        delta = timedelta(hours=amount)
    else:
        delta = timedelta(days=amount)
    return now - delta, now


def resolve_time_range(
    time_range: TimeRangeInput,
    *,
    max_hours: float = 24.0,
    now: datetime | None = None,
) -> tuple[datetime, datetime, list[str]]:
    notes: list[str] = []
    current = now or datetime.now(UTC)
    if time_range.relative:
        start, end = _parse_relative(time_range.relative, current)
    else:
        end = time_range.to_ts or current
        if end.tzinfo is None:
            end = end.replace(tzinfo=UTC)
        start = time_range.from_ts or (end - timedelta(hours=1))
        if start.tzinfo is None:
            start = start.replace(tzinfo=UTC)

    max_span = timedelta(hours=max_hours)
    if end - start > max_span:
        start = end - max_span
        notes.append(f"range clipped to {max_hours:g}h maximum")

    if start > end:
        raise ValueError("Time range start must be before end")

    return start, end, notes
