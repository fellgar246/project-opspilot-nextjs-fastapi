from __future__ import annotations

from opspilot.tools.adapters.git import GitAdapter
from opspilot.tools.adapters.loki import LokiAdapter
from opspilot.tools.adapters.simulator_api import SimulatorApiAdapter
from opspilot.tools.base import RetryPolicy, RiskLevel, ToolContext, ToolRole, ToolSpec
from opspilot.tools.config import ToolGatewaySettings
from opspilot.tools.read.schemas import (
    CommitsInput,
    CommitsOutput,
    DeploymentDetailsInput,
    DeploymentDetailsOutput,
    DeploymentsInput,
    DeploymentsOutput,
    EmptyInput,
    FeatureFlagsInput,
    FeatureFlagsOutput,
    ListServicesOutput,
    PullRequestInput,
    PullRequestOutput,
    SearchLogsInput,
    SearchLogsOutput,
)
from opspilot.tools.time_range import resolve_time_range


class SearchLogsTool:
    spec = ToolSpec(
        name="search_logs",
        version="1.0.0",
        description="Search structured logs with pattern grouping.",
        input_schema=SearchLogsInput,
        output_schema=SearchLogsOutput,
        risk_level=RiskLevel.LOW,
        required_role=ToolRole.VIEWER,
        timeout_seconds=20.0,
        retry_policy=RetryPolicy(max_attempts=3, idempotent=True),
        is_write=False,
    )

    def __init__(self, logs: LokiAdapter, settings: ToolGatewaySettings) -> None:
        self.logs = logs
        self.settings = settings

    async def run(self, payload: SearchLogsInput, ctx: ToolContext) -> SearchLogsOutput:
        start, end, _ = resolve_time_range(
            payload.time_range,
            max_hours=self.settings.max_time_range_hours,
        )
        limit = min(payload.limit, self.settings.max_log_limit)
        raw = await self.logs.search(
            service=payload.service,
            query=payload.query,
            start=start.timestamp(),
            end=end.timestamp(),
            level=payload.level,
            limit=limit,
        )
        truncated = raw.get("truncated", False) or raw.get("total_count", 0) > limit
        return SearchLogsOutput(
            service=payload.service,
            entries=raw.get("entries", []),
            total_count=raw.get("total_count", 0),
            patterns=raw.get("patterns", []),
            truncated=truncated,
            time_range_label=f"{start.isoformat()}..{end.isoformat()}",
        )


class GetRecentDeploymentsTool:
    spec = ToolSpec(
        name="get_recent_deployments",
        version="1.0.0",
        description="List recent deployments for a service.",
        input_schema=DeploymentsInput,
        output_schema=DeploymentsOutput,
        risk_level=RiskLevel.LOW,
        required_role=ToolRole.VIEWER,
        timeout_seconds=10.0,
        retry_policy=RetryPolicy(max_attempts=3, idempotent=True),
        is_write=False,
    )

    def __init__(self, simulator: SimulatorApiAdapter, settings: ToolGatewaySettings) -> None:
        self.simulator = simulator
        self.settings = settings

    async def run(self, payload: DeploymentsInput, ctx: ToolContext) -> DeploymentsOutput:
        start, end, _ = resolve_time_range(
            payload.time_range,
            max_hours=self.settings.max_time_range_hours,
        )
        deps = await self.simulator.list_deployments(
            service=payload.service,
            from_ts=start.timestamp(),
            to_ts=end.timestamp(),
        )
        return DeploymentsOutput(
            deployments=deps,
            time_range_label=f"{start.isoformat()}..{end.isoformat()}",
        )


class GetDeploymentDetailsTool:
    spec = ToolSpec(
        name="get_deployment_details",
        version="1.0.0",
        description="Fetch deployment changelog, commits and diff summary.",
        input_schema=DeploymentDetailsInput,
        output_schema=DeploymentDetailsOutput,
        risk_level=RiskLevel.LOW,
        required_role=ToolRole.VIEWER,
        timeout_seconds=10.0,
        retry_policy=RetryPolicy(max_attempts=3, idempotent=True),
        is_write=False,
    )

    def __init__(self, simulator: SimulatorApiAdapter) -> None:
        self.simulator = simulator

    async def run(
        self, payload: DeploymentDetailsInput, ctx: ToolContext
    ) -> DeploymentDetailsOutput:
        dep = await self.simulator.get_deployment(payload.deployment_id)
        if dep is None:
            raise ValueError(f"Deployment not found: {payload.deployment_id}")
        return DeploymentDetailsOutput.model_validate(dep)


class GetRecentCommitsTool:
    spec = ToolSpec(
        name="get_recent_commits",
        version="1.0.0",
        description="List recent commits for a repository.",
        input_schema=CommitsInput,
        output_schema=CommitsOutput,
        risk_level=RiskLevel.LOW,
        required_role=ToolRole.VIEWER,
        timeout_seconds=15.0,
        retry_policy=RetryPolicy(max_attempts=3, idempotent=True),
        is_write=False,
    )

    def __init__(self, git: GitAdapter, settings: ToolGatewaySettings) -> None:
        self.git = git
        self.settings = settings

    async def run(self, payload: CommitsInput, ctx: ToolContext) -> CommitsOutput:
        start, end, _ = resolve_time_range(
            payload.time_range,
            max_hours=self.settings.max_time_range_hours,
        )
        commits = await self.git.list_commits(
            repository=payload.repository,
            from_ts=start.timestamp(),
            to_ts=end.timestamp(),
            path=payload.path,
        )
        return CommitsOutput(
            repository=payload.repository,
            commits=commits,
            time_range_label=f"{start.isoformat()}..{end.isoformat()}",
        )


class GetPullRequestTool:
    spec = ToolSpec(
        name="get_pull_request",
        version="1.0.0",
        description="Fetch pull request metadata, commits and files.",
        input_schema=PullRequestInput,
        output_schema=PullRequestOutput,
        risk_level=RiskLevel.LOW,
        required_role=ToolRole.VIEWER,
        timeout_seconds=10.0,
        retry_policy=RetryPolicy(max_attempts=3, idempotent=True),
        is_write=False,
    )

    def __init__(self, git: GitAdapter) -> None:
        self.git = git

    async def run(self, payload: PullRequestInput, ctx: ToolContext) -> PullRequestOutput:
        pr = await self.git.get_pull_request(repository=payload.repository, number=payload.number)
        if pr is None:
            raise ValueError(f"Pull request not found: #{payload.number}")
        return PullRequestOutput.model_validate(pr)


class GetFeatureFlagsTool:
    spec = ToolSpec(
        name="get_feature_flags",
        version="1.0.0",
        description="List feature flags for a service.",
        input_schema=FeatureFlagsInput,
        output_schema=FeatureFlagsOutput,
        risk_level=RiskLevel.LOW,
        required_role=ToolRole.VIEWER,
        timeout_seconds=10.0,
        retry_policy=RetryPolicy(max_attempts=3, idempotent=True),
        is_write=False,
    )

    def __init__(self, simulator: SimulatorApiAdapter) -> None:
        self.simulator = simulator

    async def run(self, payload: FeatureFlagsInput, ctx: ToolContext) -> FeatureFlagsOutput:
        flags = await self.simulator.list_flags(service=payload.service, key=payload.key)
        return FeatureFlagsOutput(flags=flags)


class ListServicesTool:
    spec = ToolSpec(
        name="list_services",
        version="1.0.0",
        description="Return monitored service catalog.",
        input_schema=EmptyInput,
        output_schema=ListServicesOutput,
        risk_level=RiskLevel.LOW,
        required_role=ToolRole.VIEWER,
        timeout_seconds=5.0,
        retry_policy=RetryPolicy(max_attempts=3, idempotent=True),
        is_write=False,
    )

    def __init__(self, simulator: SimulatorApiAdapter) -> None:
        self.simulator = simulator

    async def run(self, payload: EmptyInput, ctx: ToolContext) -> ListServicesOutput:
        services = await self.simulator.list_services()
        return ListServicesOutput(services=services)
