from __future__ import annotations

from pathlib import Path

import pytest
from opspilot.tools.bootstrap import build_default_registry
from opspilot.tools.config import ToolGatewaySettings

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_registry_lists_eleven_read_tools() -> None:
    settings = ToolGatewaySettings(repo_root=REPO_ROOT)
    registry = build_default_registry(settings)
    names = registry.names()
    assert len(names) == 11
    assert "get_service_health" in names
    assert "query_metrics" in names
    assert "search_logs" in names
    assert "search_runbooks" in names
    assert "search_similar_incidents" in names
    assert all(not registry.require(name).spec.is_write for name in names)


def test_registry_rejects_duplicate_registration() -> None:
    settings = ToolGatewaySettings(repo_root=REPO_ROOT)
    registry = build_default_registry(settings)
    tool = registry.require("list_services")
    with pytest.raises(ValueError, match="already registered"):
        registry.register(tool)
