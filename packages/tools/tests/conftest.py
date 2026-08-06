from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from opspilot.tools.base import ToolContext, ToolRole
from opspilot.tools.bootstrap import build_default_registry
from opspilot.tools.config import ToolGatewaySettings
from opspilot.tools.gateway import ToolGateway
from opspilot.tools.persistence import InMemoryToolPersistence

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def settings() -> ToolGatewaySettings:
    return ToolGatewaySettings(
        sim_url="http://127.0.0.1:8080",
        repo_root=REPO_ROOT,
        git_data_dir=Path("simulator/data"),
        tool_mode="replay",
        global_concurrency_limit=20,
        per_tool_concurrency_limit=5,
    )


@pytest.fixture
def persistence() -> InMemoryToolPersistence:
    return InMemoryToolPersistence()


@pytest.fixture
def registry(settings: ToolGatewaySettings):
    return build_default_registry(settings)


@pytest.fixture
def gateway(registry, persistence, settings: ToolGatewaySettings) -> ToolGateway:
    return ToolGateway(registry, persistence, settings=settings)


@pytest.fixture
def ctx() -> ToolContext:
    return ToolContext(
        incident_id=uuid4(),
        agent_run_id=uuid4(),
        actor_type="agent",
        actor_id=uuid4(),
        role=ToolRole.OPERATOR,
        request_id="req-test",
    )
