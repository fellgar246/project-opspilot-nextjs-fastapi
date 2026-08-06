from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_parameters_hash(parameters: dict[str, Any]) -> str:
    canonical = json.dumps(parameters, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def execution_idempotency_key(approval_id: str, parameters_hash: str) -> str:
    raw = f"{approval_id}:{parameters_hash}"
    return hashlib.sha256(raw.encode()).hexdigest()
