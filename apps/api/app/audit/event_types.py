from __future__ import annotations

import enum


class AuditEventType(enum.StrEnum):
    AUTH_LOGIN_SUCCEEDED = "auth.login_succeeded"
    AUTH_LOGIN_FAILED = "auth.login_failed"
    AUTH_TOKEN_REUSE_DETECTED = "auth.token_reuse_detected"
    AUTH_RATE_LIMITED = "auth.rate_limited"
    INCIDENT_CREATED = "incident.created"
    INCIDENT_UPDATED = "incident.updated"
    INVESTIGATION_STARTED = "investigation.started"
    INVESTIGATION_PAUSED = "investigation.paused"
    INVESTIGATION_RESUMED = "investigation.resumed"
    TOOL_INVOKED = "tool.invoked"
    ACTION_PROPOSED = "action.proposed"
    APPROVAL_REQUESTED = "approval.requested"
    APPROVAL_GRANTED = "approval.granted"
    APPROVAL_REJECTED = "approval.rejected"
    ACTION_EXECUTED = "action.executed"
    POSTMORTEM_GENERATED = "postmortem.generated"
