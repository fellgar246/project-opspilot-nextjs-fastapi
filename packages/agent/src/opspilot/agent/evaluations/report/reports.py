from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from opspilot.agent.evaluations.metrics import EvaluationMetrics


def write_json_report(
    output_dir: Path,
    *,
    run_id: str,
    metrics: EvaluationMetrics,
    case_results: list[dict[str, Any]],
    versions: dict[str, str],
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": run_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "versions": versions,
        "metrics": metrics.to_dict(),
        "cases": case_results,
    }
    path = output_dir / f"eval-{run_id}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def write_html_report(
    output_dir: Path,
    *,
    run_id: str,
    metrics: EvaluationMetrics,
    case_results: list[dict[str, Any]],
    versions: dict[str, str],
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = "".join(
        f"<tr><td>{c['case_id']}</td><td>{c['status']}</td>"
        f"<td>{', '.join(c.get('failed_evaluators', []))}</td></tr>"
        for c in case_results
    )
    metric_rows = "".join(
        f"<tr><td>{name}</td><td>{value:.4f}</td></tr>"
        for name, value in metrics.to_dict().items()
        if isinstance(value, int | float)
    )
    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>Evaluation {run_id}</title>
<style>body{{font-family:system-ui;margin:2rem}}table{{border-collapse:collapse;width:100%}}
td,th{{border:1px solid #ccc;padding:.5rem;text-align:left}}</style></head>
<body><h1>Evaluation Run {run_id}</h1>
<p>Generated: {datetime.now(UTC).isoformat()}</p>
<h2>Versions</h2><pre>{json.dumps(versions, indent=2)}</pre>
<h2>Metrics</h2><table><tr><th>Metric</th><th>Value</th></tr>{metric_rows}</table>
<h2>Cases</h2><table><tr><th>Case</th><th>Status</th><th>Failed Evaluators</th></tr>{rows}</table>
</body></html>"""
    path = output_dir / f"eval-{run_id}.html"
    path.write_text(html, encoding="utf-8")
    return path
