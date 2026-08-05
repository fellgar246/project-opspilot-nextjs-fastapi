import { describe, expect, it } from "vitest";

import { roleHasCapability } from "@/features/auth/permissions";

describe("roleHasCapability", () => {
  it("hides audit for operators and shows for approvers", () => {
    expect(roleHasCapability("operator", "read_audit")).toBe(false);
    expect(roleHasCapability("approver", "read_audit")).toBe(true);
  });
});
