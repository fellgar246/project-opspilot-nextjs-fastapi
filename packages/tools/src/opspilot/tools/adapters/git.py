from __future__ import annotations

import asyncio
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from opspilot.tools.adapters.base import GitBackend


class GitAdapter(GitBackend):
    def __init__(self, *, data_dir: Path, repo_root: Path | None = None) -> None:
        self.data_dir = data_dir
        self.repo_root = repo_root or data_dir.parents[1]
        self.pr_dir = data_dir / "pull_requests"
        if not self.pr_dir.exists():
            fallback = self.repo_root / "data" / "pull_requests"
            if fallback.exists():
                self.pr_dir = fallback

    def _repo_path(self, repository: str) -> Path:
        if repository.endswith(".git"):
            candidate = Path(repository)
            if candidate.exists():
                return candidate
        return self.data_dir / "repos" / "demo-service.git"

    async def list_commits(
        self,
        *,
        repository: str,
        from_ts: float,
        to_ts: float,
        path: str | None,
    ) -> list[dict[str, Any]]:
        repo = self._repo_path(repository)
        if not repo.exists():
            return []

        cmd = [
            "git",
            "--git-dir",
            str(repo),
            "log",
            f"--since={int(from_ts)}",
            f"--until={int(to_ts)}",
            "--pretty=format:%H|%an|%ae|%at|%s",
        ]
        if path:
            cmd.extend(["--", path])

        def _run() -> list[dict[str, Any]]:
            completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if completed.returncode != 0:
                return []
            commits: list[dict[str, Any]] = []
            for line in completed.stdout.splitlines():
                parts = line.split("|", 4)
                if len(parts) != 5:
                    continue
                sha, author_name, author_email, ts, message = parts
                files = self._changed_files(repo, sha)
                commits.append(
                    {
                        "sha": sha,
                        "author": f"{author_name} <{author_email}>",
                        "message": message,
                        "committed_at": datetime.fromtimestamp(int(ts), tz=UTC).isoformat(),
                        "files_changed": files,
                        "diff_summary": self._diff_summary(repo, sha),
                    }
                )
            return commits

        return await asyncio.to_thread(_run)

    def _changed_files(self, repo: Path, sha: str) -> list[str]:
        completed = subprocess.run(
            [
                "git",
                "--git-dir",
                str(repo),
                "diff-tree",
                "--no-commit-id",
                "--name-only",
                "-r",
                sha,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            return []
        return [line for line in completed.stdout.splitlines() if line.strip()]

    def _diff_summary(self, repo: Path, sha: str) -> str:
        completed = subprocess.run(
            ["git", "--git-dir", str(repo), "show", "--stat", "--oneline", sha],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            return ""
        lines = completed.stdout.strip().splitlines()
        return "\n".join(lines[:5])

    async def get_pull_request(self, *, repository: str, number: int) -> dict[str, Any] | None:
        path = self.pr_dir / f"pr-{number}.json"
        if not path.exists():
            return None
        pr = json.loads(path.read_text(encoding="utf-8"))
        pr["repository"] = repository
        pr["diff_summary"] = f"Files: {', '.join(pr.get('files_changed', []))}"
        return pr
