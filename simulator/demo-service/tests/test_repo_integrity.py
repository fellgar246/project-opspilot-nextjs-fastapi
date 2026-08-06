from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
REPO = DATA / "repos" / "demo-service.git"
COMMIT_MAP = DATA / "commit_map.json"
PR_DIR = DATA / "pull_requests"
SCENARIOS = ROOT / "scenarios"


def _ensure_seeded() -> None:
    if REPO.exists() and (REPO / "HEAD").exists() and COMMIT_MAP.exists():
        return
    subprocess.run(
        ["uv", "run", "python", str(ROOT / "scripts" / "seed.py")],
        check=True,
        cwd=ROOT / "demo-service",
    )


def test_repo_has_enough_commits() -> None:
    _ensure_seeded()
    count = subprocess.check_output(
        ["git", "--git-dir", str(REPO), "rev-list", "--count", "HEAD"],
        text=True,
    ).strip()
    assert int(count) >= 50


def test_deployment_commit_shas_exist() -> None:
    _ensure_seeded()
    deployments = json.loads((DATA / "deployments.json").read_text(encoding="utf-8"))
    for dep in deployments:
        sha = dep["commit_sha"]
        subprocess.check_call(
            ["git", "--git-dir", str(REPO), "cat-file", "-e", f"{sha}^{{commit}}"]
        )


def test_scenario_commit_shas_exist() -> None:
    _ensure_seeded()
    commit_map = json.loads(COMMIT_MAP.read_text(encoding="utf-8"))
    for scenario_id, sha in commit_map.items():
        subprocess.check_call(
            ["git", "--git-dir", str(REPO), "cat-file", "-e", f"{sha}^{{commit}}"]
        )
        yaml_text = (SCENARIOS / f"{scenario_id}.yaml").read_text(encoding="utf-8")
        assert "PLACEHOLDER_" not in yaml_text
        assert sha in yaml_text


def test_pull_request_commits_exist() -> None:
    _ensure_seeded()
    for path in PR_DIR.glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for sha in payload.get("commits", []):
            subprocess.check_call(
                ["git", "--git-dir", str(REPO), "cat-file", "-e", f"{sha}^{{commit}}"]
            )


def test_inventory_counts() -> None:
    _ensure_seeded()
    runbooks = list((DATA / "runbooks").glob("*.md"))
    incidents = list((ROOT.parent / "datasets" / "incidents").glob("*.json"))
    assert len(runbooks) >= 15
    assert len(incidents) >= 10
    injection = [
        p for p in runbooks if "IGNORE PREVIOUS INSTRUCTIONS" in p.read_text(encoding="utf-8")
    ]
    assert injection, "expected prompt-injection runbook"
