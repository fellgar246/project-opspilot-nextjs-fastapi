from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    git_sha: str
    checks: dict[str, Literal["ok", "fail"]]
