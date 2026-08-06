from __future__ import annotations

from opspilot.tools.adapters.git import GitAdapter
from opspilot.tools.adapters.loki import LokiAdapter
from opspilot.tools.adapters.prometheus import PrometheusAdapter
from opspilot.tools.adapters.simulator_api import SimulatorApiAdapter
from opspilot.tools.config import ToolGatewaySettings, get_tool_settings
from opspilot.tools.read.deployments_code import (
    GetDeploymentDetailsTool,
    GetFeatureFlagsTool,
    GetPullRequestTool,
    GetRecentCommitsTool,
    GetRecentDeploymentsTool,
    ListServicesTool,
    SearchLogsTool,
)
from opspilot.tools.read.metrics_health import GetServiceHealthTool, QueryMetricsTool
from opspilot.tools.read.retrieval_tools import SearchRunbooksTool, SearchSimilarIncidentsTool
from opspilot.tools.registry import ToolRegistry
from opspilot.tools.retrieval.memory import InMemoryRetrievalStore
from opspilot.tools.retrieval.protocol import RetrievalStore


def build_default_registry(
    settings: ToolGatewaySettings | None = None,
    *,
    retrieval_store: RetrievalStore | None = None,
) -> ToolRegistry:
    settings = settings or get_tool_settings()
    registry = ToolRegistry()
    store = retrieval_store or InMemoryRetrievalStore()

    simulator = SimulatorApiAdapter(
        base_url=settings.sim_url,
        data_dir=settings.repo_root / settings.git_data_dir,
    )
    metrics = PrometheusAdapter(
        prometheus_url=settings.prometheus_url,
        sim_url=settings.sim_url,
    )
    logs = LokiAdapter(loki_url=settings.loki_url)
    git = GitAdapter(
        data_dir=settings.repo_root / settings.git_data_dir, repo_root=settings.repo_root
    )

    for tool in (
        GetServiceHealthTool(simulator),
        QueryMetricsTool(metrics, settings),
        SearchLogsTool(logs, settings),
        GetRecentDeploymentsTool(simulator, settings),
        GetDeploymentDetailsTool(simulator),
        GetRecentCommitsTool(git, settings),
        GetPullRequestTool(git),
        GetFeatureFlagsTool(simulator),
        ListServicesTool(simulator),
        SearchRunbooksTool(store),
        SearchSimilarIncidentsTool(store),
    ):
        registry.register(tool)

    return registry
