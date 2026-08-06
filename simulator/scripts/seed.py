#!/usr/bin/env python3
"""Seed simulator data: git repo, PRs, deployments, flags, replay templates, runbooks inventory."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # simulator/
SCRIPTS = Path(__file__).resolve().parent
DATA = ROOT / "data"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT / "demo-service"))

from build_repo import build  # noqa: E402


def write_pull_requests(commit_map: dict[str, str]) -> None:
    pr_dir = DATA / "pull_requests"
    pr_dir.mkdir(parents=True, exist_ok=True)
    fixtures = [
        {
            "number": 101,
            "title": "Reduce DB pool size",
            "description": "Cut costs by lowering db_pool_max_size.",
            "author": "cara.singh@example.com",
            "commits": [commit_map["SCN-003-db-pool-exhaustion"]],
            "files_changed": ["src/db.py"],
            "merged_at": "2024-01-15T10:00:00Z",
            "reviewers": ["ava.chen@example.com"],
            "scenario_id": "SCN-003-db-pool-exhaustion",
        },
        {
            "number": 102,
            "title": "Refactor catalog loader",
            "description": "Load item details individually for clarity.",
            "author": "ben.ortiz@example.com",
            "commits": [commit_map["SCN-002-n-plus-one"]],
            "files_changed": ["src/catalog.py"],
            "merged_at": "2024-01-14T09:00:00Z",
            "reviewers": ["diego.ruiz@example.com"],
            "scenario_id": "SCN-002-n-plus-one",
        },
        {
            "number": 103,
            "title": "Enable new checkout flow",
            "description": "Roll out new-checkout-flow flag.",
            "author": "cara.singh@example.com",
            "commits": [commit_map["SCN-006-bad-feature-flag"]],
            "files_changed": ["src/flags.py", "src/checkout.py"],
            "merged_at": "2024-01-18T12:00:00Z",
            "reviewers": ["elena.novak@example.com"],
            "scenario_id": "SCN-006-bad-feature-flag",
        },
        {
            "number": 104,
            "title": "Harden order_id validation",
            "description": "Reject short order ids more aggressively.",
            "author": "diego.ruiz@example.com",
            "commits": [commit_map["SCN-007-post-deploy-regression"]],
            "files_changed": ["src/orders.py"],
            "merged_at": "2024-01-19T08:30:00Z",
            "reviewers": ["ava.chen@example.com", "ben.ortiz@example.com"],
            "scenario_id": "SCN-007-post-deploy-regression",
        },
        {
            "number": 105,
            "title": "Add in-process order cache",
            "description": "Cache order responses to reduce DB load.",
            "author": "elena.novak@example.com",
            "commits": [commit_map["SCN-005-memory-leak"]],
            "files_changed": ["src/cache.py"],
            "merged_at": "2024-01-17T16:00:00Z",
            "reviewers": ["cara.singh@example.com"],
            "scenario_id": "SCN-005-memory-leak",
        },
        {
            "number": 106,
            "title": "Docs: README ops section",
            "description": "Innocent documentation PR.",
            "author": "cara.singh@example.com",
            "commits": [],
            "files_changed": ["README.md"],
            "merged_at": "2024-01-12T11:00:00Z",
            "reviewers": ["ben.ortiz@example.com"],
            "scenario_id": None,
        },
    ]
    # Attach an innocent neighboring commit SHA when available from git log.
    for fixture in fixtures:
        path = pr_dir / f"pr-{fixture['number']}.json"
        path.write_text(json.dumps(fixture, indent=2), encoding="utf-8")


def write_baseline_deployments(commit_map: dict[str, str]) -> None:
    now = time.time()
    deployments = []
    versions = [
        ("SCN-001-missing-env", "v2.12.0", now - 86400 * 7),
        ("SCN-002-n-plus-one", "v2.13.1", now - 86400 * 6),
        ("SCN-003-db-pool-exhaustion", "v2.14.0", now - 86400 * 5),
        ("SCN-004-external-dependency", "v2.14.2", now - 86400 * 4),
        ("SCN-005-memory-leak", "v2.15.0", now - 86400 * 3),
        ("SCN-006-bad-feature-flag", "v2.15.1", now - 86400 * 2),
        ("SCN-007-post-deploy-regression", "v2.16.0", now - 86400),
    ]
    for idx, (scenario_id, version, deployed_at) in enumerate(versions, start=1):
        deployments.append(
            {
                "deployment_id": f"dep-seed-{idx:03d}",
                "service": "demo-service",
                "version": version,
                "commit_sha": commit_map[scenario_id],
                "deployed_at": deployed_at,
                "deployed_by": "ci-bot",
                "status": "success",
                "changelog": f"Seed deployment for {scenario_id}",
            }
        )
    path = DATA / "deployments.json"
    path.write_text(json.dumps(deployments, indent=2), encoding="utf-8")


def write_feature_flags() -> None:
    flags = [
        {
            "key": "new-checkout-flow",
            "service": "demo-service",
            "enabled": False,
            "rollout_percentage": 0.0,
            "updated_at": time.time(),
            "updated_by": "seed",
        },
        {
            "key": "catalog-v2",
            "service": "demo-service",
            "enabled": True,
            "rollout_percentage": 100.0,
            "updated_at": time.time(),
            "updated_by": "seed",
        },
        {
            "key": "orders-cache",
            "service": "demo-service",
            "enabled": True,
            "rollout_percentage": 50.0,
            "updated_at": time.time(),
            "updated_by": "seed",
        },
    ]
    (DATA / "feature_flags.json").write_text(json.dumps(flags, indent=2), encoding="utf-8")


def write_replay_templates() -> None:
    from demo_service.config import get_settings
    from demo_service.scenarios.engine import ScenarioEngine

    settings = get_settings()
    engine = ScenarioEngine(settings)
    for scenario in engine.list_scenarios():
        engine.write_replay_template(scenario.id)


def write_inventory() -> None:
    runbooks = sorted((DATA / "runbooks").glob("*.md"))
    incidents = sorted((ROOT.parent / "datasets" / "incidents").glob("*.json"))
    inventory = {
        "runbooks": [p.name for p in runbooks],
        "runbook_count": len(runbooks),
        "incidents": [p.name for p in incidents],
        "incident_count": len(incidents),
    }
    (DATA / "inventory.json").write_text(json.dumps(inventory, indent=2), encoding="utf-8")


def main() -> None:
    commit_map = build()
    write_pull_requests(commit_map)
    write_baseline_deployments(commit_map)
    write_feature_flags()
    write_replay_templates()
    write_inventory()
    print(json.dumps({"status": "seeded", "culprit_commits": len(commit_map)}, indent=2))


if __name__ == "__main__":
    main()
