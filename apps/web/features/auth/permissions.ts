export type UserRole = "viewer" | "operator" | "approver" | "admin";

export type Capability =
  | "read_incidents"
  | "create_incidents"
  | "manage_investigation"
  | "execute_readonly_tools"
  | "propose_mitigation"
  | "approve_action"
  | "execute_approved_action"
  | "read_audit"
  | "run_evaluations"
  | "manage_users";

const ROLE_CAPABILITIES: Record<UserRole, Capability[]> = {
  viewer: ["read_incidents"],
  operator: [
    "read_incidents",
    "create_incidents",
    "manage_investigation",
    "execute_readonly_tools",
    "propose_mitigation",
  ],
  approver: [
    "read_incidents",
    "create_incidents",
    "manage_investigation",
    "execute_readonly_tools",
    "propose_mitigation",
    "approve_action",
    "execute_approved_action",
    "read_audit",
  ],
  admin: [
    "read_incidents",
    "create_incidents",
    "manage_investigation",
    "execute_readonly_tools",
    "propose_mitigation",
    "approve_action",
    "execute_approved_action",
    "read_audit",
    "run_evaluations",
    "manage_users",
  ],
};

export function roleHasCapability(role: UserRole, capability: Capability): boolean {
  return ROLE_CAPABILITIES[role].includes(capability);
}
