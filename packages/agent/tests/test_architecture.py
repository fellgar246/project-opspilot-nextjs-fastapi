from __future__ import annotations

import ast
from pathlib import Path

AGENT_SRC = Path(__file__).resolve().parents[2] / "src" / "opspilot" / "agent"
FORBIDDEN_IMPORTS = {"openai"}


def _python_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*.py"):
        if "providers" in path.parts:
            continue
        files.append(path)
    return files


def test_no_provider_sdk_outside_providers_package() -> None:
    offenders: list[str] = []
    for path in _python_files(AGENT_SRC):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root in FORBIDDEN_IMPORTS:
                        offenders.append(f"{path.relative_to(AGENT_SRC)} imports {alias.name}")
            if isinstance(node, ast.ImportFrom) and node.module:
                root = node.module.split(".")[0]
                if root in FORBIDDEN_IMPORTS:
                    offenders.append(f"{path.relative_to(AGENT_SRC)} imports from {node.module}")
    assert not offenders, "\n".join(offenders)
