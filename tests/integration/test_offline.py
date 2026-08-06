"""Verify main flow works without external network after bootstrap."""

from __future__ import annotations

import pytest


@pytest.mark.integration
def test_offline_eval_smoke() -> None:
    """Evaluation smoke gate runs with mock provider — no network required."""
    import asyncio
    from pathlib import Path

    from opspilot.agent.evaluations import RunConfig, run_evaluation

    async def _run() -> None:
        report = await run_evaluation(
            RunConfig(smoke=True, model_provider="mock", reports_dir=Path("reports"))
        )
        assert report.metrics.case_count == 5
        assert report.gate_passed or report.gate_failures

    asyncio.run(_run())
