#!/usr/bin/env python3
"""Generate a realistic local git repository for demo-service."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # simulator/
DATA = ROOT / "data"
REPO_BARE = DATA / "repos" / "demo-service.git"
COMMIT_MAP = DATA / "commit_map.json"
SCENARIOS = ROOT / "scenarios"

AUTHORS = [
    ("Ava Chen", "ava.chen@example.com"),
    ("Ben Ortiz", "ben.ortiz@example.com"),
    ("Cara Singh", "cara.singh@example.com"),
    ("Diego Ruiz", "diego.ruiz@example.com"),
    ("Elena Novak", "elena.novak@example.com"),
]

PLACEHOLDERS = {
    "SCN-001-missing-env": "PLACEHOLDER_SCN001",
    "SCN-002-n-plus-one": "PLACEHOLDER_SCN002",
    "SCN-003-db-pool-exhaustion": "PLACEHOLDER_SCN003",
    "SCN-004-external-dependency": "PLACEHOLDER_SCN004",
    "SCN-005-memory-leak": "PLACEHOLDER_SCN005",
    "SCN-006-bad-feature-flag": "PLACEHOLDER_SCN006",
    "SCN-007-post-deploy-regression": "PLACEHOLDER_SCN007",
}

BASE_FILES = {
    "README.md": "# demo-service\n\nSimulated commerce API.\n",
    "src/main.py": "def main():\n    print('demo-service')\n",
    "src/db.py": "DB_POOL_MAX_SIZE = 50\n",
    "src/catalog.py": "def list_items(db):\n    return db.query('select * from items')\n",
    "src/checkout.py": "def checkout(order):\n    return {'ok': True}\n",
    "src/orders.py": "def get_order(order_id):\n    return {'id': order_id}\n",
    "src/config.py": "PAYMENTS_API_KEY = None\n",
    "src/flags.py": "FLAGS = {'new-checkout-flow': False}\n",
    "src/cache.py": "ORDER_CACHE = {}\n",
}


def run(cmd: list[str], cwd: Path, env: dict[str, str] | None = None) -> str:
    completed = subprocess.run(
        cmd,
        cwd=cwd,
        check=False,
        text=True,
        capture_output=True,
        env=env,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"Command failed ({completed.returncode}): {' '.join(cmd)}\n"
            f"stdout: {completed.stdout}\nstderr: {completed.stderr}"
        )
    return completed.stdout.strip()


def commit(cwd: Path, message: str, author: tuple[str, str], ts: int) -> str:
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": author[0],
            "GIT_AUTHOR_EMAIL": author[1],
            "GIT_COMMITTER_NAME": author[0],
            "GIT_COMMITTER_EMAIL": author[1],
            "GIT_AUTHOR_DATE": str(ts),
            "GIT_COMMITTER_DATE": str(ts),
        }
    )
    run(["git", "add", "-A"], cwd=cwd, env=env)
    run(["git", "commit", "-m", message], cwd=cwd, env=env)
    return run(["git", "rev-parse", "HEAD"], cwd=cwd, env=env)


def write(cwd: Path, relative: str, content: str) -> None:
    path = cwd / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def patch_scenarios(commit_map: dict[str, str]) -> None:
    for scenario_id, sha in commit_map.items():
        path = SCENARIOS / f"{scenario_id}.yaml"
        if not path.exists():
            continue
        token = PLACEHOLDERS[scenario_id]
        text = path.read_text(encoding="utf-8")
        # Allow re-seeding: replace previous sha or placeholder.
        if token in text:
            text = text.replace(token, sha)
        else:
            # Replace existing commit_sha line value.
            lines = []
            for line in text.splitlines():
                if line.strip().startswith("commit_sha:"):
                    lines.append(f"  commit_sha: {sha}")
                else:
                    lines.append(line)
            text = "\n".join(lines) + "\n"
        path.write_text(text, encoding="utf-8")


def build() -> dict[str, str]:
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "repos").mkdir(parents=True, exist_ok=True)
    if REPO_BARE.exists():
        shutil.rmtree(REPO_BARE)

    # Restore placeholders so re-seed is idempotent.
    for scenario_id, token in PLACEHOLDERS.items():
        path = SCENARIOS / f"{scenario_id}.yaml"
        if not path.exists():
            continue
        lines = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("commit_sha:"):
                lines.append(f"  commit_sha: {token}")
            else:
                lines.append(line)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    commit_map: dict[str, str] = {}
    # Keep the working tree inside the repo so sandboxed CI/agents can run git.
    build_root = DATA / ".build-tmp"
    if build_root.exists():
        shutil.rmtree(build_root)
    build_root.mkdir(parents=True)
    try:
        cwd = build_root / "demo-service"
        cwd.mkdir()
        # Empty template avoids installing hooks (blocked in some sandboxes).
        run(["git", "init", "--template=", "-b", "main"], cwd)
        run(["git", "config", "user.name", "OpsPilot Seed"], cwd)
        run(["git", "config", "user.email", "seed@ops-pilot.local"], cwd)

        for rel, content in BASE_FILES.items():
            write(cwd, rel, content)
        base_ts = 1_700_000_000
        commit(cwd, "chore: initial demo-service scaffold", AUTHORS[0], base_ts)

        for i in range(1, 41):
            author = AUTHORS[i % len(AUTHORS)]
            write(cwd, f"docs/notes/note_{i:02d}.md", f"# Note {i}\n\nRoutine change {i}.\n")
            if i % 5 == 0:
                write(cwd, "src/main.py", f"def main():\n    print('demo-service v{i}')\n")
            commit(cwd, f"chore: maintenance update #{i}", author, base_ts + i * 3600)

        write(
            cwd,
            "src/checkout.py",
            "def checkout(order):\n    return {'ok': True, 'tax': 0.16}\n",
        )
        commit(cwd, "feat: add tax calculation helper", AUTHORS[1], base_ts + 50 * 3600)
        write(cwd, "README.md", "# demo-service\n\nSimulated commerce API.\n\n## Ops\n")
        commit(cwd, "docs: expand README ops section", AUTHORS[2], base_ts + 51 * 3600)

        write(cwd, "src/config.py", "PAYMENTS_API_KEY = None  # intentionally unset in deploy\n")
        commit_map["SCN-001-missing-env"] = commit(
            cwd,
            "fix: rely on PAYMENTS_API_KEY from environment",
            AUTHORS[0],
            base_ts + 52 * 3600,
        )
        write(
            cwd,
            "src/checkout.py",
            "def checkout(order):\n    return {'ok': True, 'tax': 0.16, 'retry': 1}\n",
        )
        commit(cwd, "chore: add checkout retry counter", AUTHORS[3], base_ts + 53 * 3600)

        write(
            cwd,
            "src/catalog.py",
            "def list_items(db):\n"
            "    items = db.query('select id from items')\n"
            "    return [db.query('select * from items where id=%s', i) for i in items]\n",
        )
        commit_map["SCN-002-n-plus-one"] = commit(
            cwd,
            "refactor: load catalog details per item",
            AUTHORS[1],
            base_ts + 54 * 3600,
        )
        write(cwd, "docs/notes/note_catalog.md", "# Catalog notes\n")
        commit(cwd, "docs: catalog loader notes", AUTHORS[4], base_ts + 55 * 3600)

        write(cwd, "src/db.py", "DB_POOL_MAX_SIZE = 5\n")
        commit_map["SCN-003-db-pool-exhaustion"] = commit(
            cwd,
            "perf: reduce db_pool_max_size to cut costs",
            AUTHORS[2],
            base_ts + 56 * 3600,
        )
        write(cwd, "src/db.py", "DB_POOL_MAX_SIZE = 5\nDB_POOL_TIMEOUT = 2\n")
        commit(cwd, "chore: set pool timeout", AUTHORS[0], base_ts + 57 * 3600)

        write(cwd, "src/main.py", "def main():\n    print('demo-service patched')\n")
        commit_map["SCN-004-external-dependency"] = commit(
            cwd,
            "chore: routine patch unrelated to payments",
            AUTHORS[3],
            base_ts + 58 * 3600,
        )

        write(
            cwd,
            "src/cache.py",
            "ORDER_CACHE = {}\n\n"
            "def remember(order_id, payload):\n"
            "    ORDER_CACHE[order_id] = payload  # unbounded\n"
            "    return payload\n",
        )
        commit_map["SCN-005-memory-leak"] = commit(
            cwd,
            "feat: cache order responses in process memory",
            AUTHORS[4],
            base_ts + 59 * 3600,
        )
        write(cwd, "docs/notes/note_cache.md", "# Cache\n")
        commit(cwd, "docs: describe order cache", AUTHORS[1], base_ts + 60 * 3600)

        write(cwd, "src/flags.py", "FLAGS = {'new-checkout-flow': True}\n")
        write(
            cwd,
            "src/checkout.py",
            "def checkout(order):\n"
            "    if True:\n"
            "        return order['missing_key']  # NPE under flag\n"
            "    return {'ok': True}\n",
        )
        commit_map["SCN-006-bad-feature-flag"] = commit(
            cwd,
            "feat: enable new-checkout-flow by default",
            AUTHORS[2],
            base_ts + 61 * 3600,
        )
        write(cwd, "docs/notes/note_flags.md", "# Flags\n")
        commit(cwd, "docs: feature flag rollout notes", AUTHORS[0], base_ts + 62 * 3600)

        write(
            cwd,
            "src/orders.py",
            "def get_order(order_id):\n"
            "    if len(order_id) < 99:\n"
            "        raise ValueError('invalid order_id validation regression')\n"
            "    return {'id': order_id}\n",
        )
        commit_map["SCN-007-post-deploy-regression"] = commit(
            cwd,
            "fix: harden order_id validation",
            AUTHORS[3],
            base_ts + 63 * 3600,
        )
        write(
            cwd,
            "src/orders.py",
            "def get_order(order_id):\n    return {'id': order_id, 'v': 2}\n",
        )
        commit(cwd, "chore: bump orders payload version", AUTHORS[4], base_ts + 64 * 3600)

        for i in range(65, 75):
            write(cwd, f"docs/notes/extra_{i}.md", f"extra {i}\n")
            commit(cwd, f"chore: docs fluff #{i}", AUTHORS[i % len(AUTHORS)], base_ts + i * 3600)

        run(["git", "clone", "--bare", str(cwd), str(REPO_BARE)], cwd=build_root)
    finally:
        if build_root.exists():
            shutil.rmtree(build_root)

    COMMIT_MAP.write_text(json.dumps(commit_map, indent=2), encoding="utf-8")
    patch_scenarios(commit_map)
    return commit_map


def main() -> None:
    commit_map = build()
    count = run(["git", "rev-list", "--count", "HEAD"], REPO_BARE)
    print(
        json.dumps(
            {"repo": str(REPO_BARE), "commits": int(count), "culprits": commit_map},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
