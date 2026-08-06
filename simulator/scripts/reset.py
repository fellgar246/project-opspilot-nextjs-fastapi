#!/usr/bin/env python3
"""Reset simulator runtime state to a clean nominal baseline."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # simulator/
DATA = ROOT / "data"
SIM_URL = os.environ.get("SIM_URL", "http://127.0.0.1:8080")


def reset_via_http() -> bool:
    try:
        req = urllib.request.Request(f"{SIM_URL}/sim/reset", method="POST")
        with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310 — local sim only
            return resp.status == 200
    except (urllib.error.URLError, TimeoutError):
        return False


def reset_files() -> None:
    # Keep seeded history; clear only volatile overlays if present.
    volatile = DATA / "runtime_state.json"
    if volatile.exists():
        volatile.unlink()
    # Ensure feature flags return to nominal defaults if seed artifacts exist.
    flags_path = DATA / "feature_flags.json"
    if flags_path.exists():
        flags = json.loads(flags_path.read_text(encoding="utf-8"))
        for flag in flags:
            if flag["key"] == "new-checkout-flow":
                flag["enabled"] = False
                flag["rollout_percentage"] = 0.0
                flag["updated_by"] = "reset"
        flags_path.write_text(json.dumps(flags, indent=2), encoding="utf-8")


def main() -> None:
    http_ok = reset_via_http()
    reset_files()
    print(json.dumps({"status": "reset", "http": http_ok}, indent=2))
    if not http_ok:
        # File-level reset is still a success when the service is down.
        sys.exit(0)


if __name__ == "__main__":
    main()
