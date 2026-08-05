from __future__ import annotations

import enum


class Capability(enum.StrEnum):
    READ_INCIDENTS = "read_incidents"
    CREATE_INCIDENTS = "create_incidents"
    MANAGE_INVESTIGATION = "manage_investigation"
    EXECUTE_READONLY_TOOLS = "execute_readonly_tools"
    PROPOSE_MITIGATION = "propose_mitigation"
    APPROVE_ACTION = "approve_action"
    EXECUTE_APPROVED_ACTION = "execute_approved_action"
    READ_AUDIT = "read_audit"
    RUN_EVALUATIONS = "run_evaluations"
    MANAGE_USERS = "manage_users"


ROLE_CAPABILITIES: dict[str, set[Capability]] = {
    "viewer": {
        Capability.READ_INCIDENTS,
    },
    "operator": {
        Capability.READ_INCIDENTS,
        Capability.CREATE_INCIDENTS,
        Capability.MANAGE_INVESTIGATION,
        Capability.EXECUTE_READONLY_TOOLS,
        Capability.PROPOSE_MITIGATION,
    },
    "approver": {
        Capability.READ_INCIDENTS,
        Capability.CREATE_INCIDENTS,
        Capability.MANAGE_INVESTIGATION,
        Capability.EXECUTE_READONLY_TOOLS,
        Capability.PROPOSE_MITIGATION,
        Capability.APPROVE_ACTION,
        Capability.EXECUTE_APPROVED_ACTION,
        Capability.READ_AUDIT,
    },
    "admin": set(Capability),
}


def role_has_capability(role: str, capability: Capability) -> bool:
    return capability in ROLE_CAPABILITIES.get(role, set())
