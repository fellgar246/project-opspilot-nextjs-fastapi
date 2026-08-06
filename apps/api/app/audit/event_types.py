from __future__ import annotations

import enum


class AuditEventType(enum.StrEnum):
    AUTH_LOGIN_SUCCEEDED = "auth.login_succeeded"
    AUTH_LOGIN_FAILED = "auth.login_failed"
    AUTH_TOKEN_REUSE_DETECTED = "auth.token_reuse_detected"
    AUTH_RATE_LIMITED = "auth.rate_limited"
    INCIDENT_CREATED = "incident.created"
    INCIDENT_UPDATED = "incident.updated"
    SERVICE_CREATED = "service.created"
    SERVICE_UPDATED = "service.updated"
    SERVICE_DEACTIVATED = "service.deactivated"
    INVESTIGATION_STARTED = "investigation.started"
    INVESTIGATION_PAUSED = "investigation.paused"
    INVESTIGATION_RESUMED = "investigation.resumed"
    TOOL_INVOKED = "tool.invoked"
    ACTION_PROPOSED = "action.proposed"
    APPROVAL_REQUESTED = "approval.requested"
    APPROVAL_GRANTED = "approval.granted"
    APPROVAL_REJECTED = "approval.rejected"
    ACTION_PARAMETER_MISMATCH = "action.parameter_mismatch"
    ACTION_EXECUTED = "action.executed"
    ACTION_ROLLED_BACK = "action.rolled_back"
    RECOVERY_VERIFIED = "recovery.verified"
    POSTMORTEM_GENERATED = "postmortem.generated"
