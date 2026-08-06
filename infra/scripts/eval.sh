#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TAGS="${EVAL_TAGS:-}"
SMOKE="${EVAL_SMOKE:-false}"
CONCURRENCY="${EVAL_CONCURRENCY:-4}"

exec uv run python - <<'PY'
import asyncio
import os
from pathlib import Path

from opspilot.agent.evaluations import RunConfig, run_evaluation

tags = [t for t in os.environ.get("EVAL_TAGS", "").split(",") if t]
smoke = os.environ.get("EVAL_SMOKE", "false").lower() == "true"
concurrency = int(os.environ.get("EVAL_CONCURRENCY", "4"))

async def main() -> None:
    report = await run_evaluation(
        RunConfig(
            tags=tags,
            smoke=smoke,
            concurrency=concurrency,
            reports_dir=Path("reports"),
        )
    )
    print(f"Evaluation run {report.run_id}: gate_passed={report.gate_passed}")
    print(f"Reports: {report.json_path} {report.html_path}")
    if not report.gate_passed:
        for failure in report.gate_failures:
            print(f"  GATE FAIL: {failure}")
        raise SystemExit(1)

asyncio.run(main())
PY
