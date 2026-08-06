from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, Info

APP_INFO = Info("opspilot_app", "Application build metadata")

HTTP_REQUESTS = Counter(
    "opspilot_http_requests_total",
    "HTTP requests",
    ["method", "endpoint", "status"],
)

HTTP_LATENCY = Histogram(
    "opspilot_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

QUEUE_DEPTH = Gauge("opspilot_queue_depth", "Pending ARQ jobs")

AGENT_NODE_DURATION = Histogram(
    "opspilot_agent_node_duration_seconds",
    "Agent node execution duration",
    ["node"],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 15.0, 30.0, 60.0),
)

AGENT_TOOL_CALLS = Counter(
    "opspilot_agent_tool_calls_total",
    "Tool invocations by the agent",
    ["tool", "status"],
)

AGENT_TOKENS = Counter(
    "opspilot_agent_tokens_total",
    "Tokens consumed by agent stage",
    ["stage", "direction"],
)

AGENT_RETRIES = Counter(
    "opspilot_agent_retries_total",
    "LLM/tool retry attempts",
    ["component"],
)

AGENT_APPROVALS = Counter(
    "opspilot_agent_approvals_total",
    "Approval requests",
    ["outcome"],
)

BUSINESS_TIME_TO_HYPOTHESIS = Histogram(
    "opspilot_time_to_hypothesis_seconds",
    "Seconds from investigation start to first hypothesis",
    buckets=(5, 15, 30, 60, 120, 300, 600),
)

BUSINESS_TIME_TO_MITIGATION = Histogram(
    "opspilot_time_to_mitigation_seconds",
    "Seconds from investigation start to mitigation proposal",
    buckets=(10, 30, 60, 120, 300, 600, 900),
)

BUSINESS_RESOLVED = Counter(
    "opspilot_incidents_resolved_total",
    "Incidents resolved",
    ["outcome"],
)
