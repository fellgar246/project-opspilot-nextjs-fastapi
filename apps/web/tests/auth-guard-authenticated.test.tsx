import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/dashboard",
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/features/auth/AuthProvider", () => ({
  useAuth: () => ({
    user: { id: "1", email: "a@example.com", display_name: "A", role: "viewer" },
    loading: false,
    sessionExpired: false,
  }),
}));

import { AuthGuard } from "@/features/auth/AuthGuard";

describe("AuthGuard authenticated", () => {
  it("renders children when user is present", () => {
    render(
      <AuthGuard>
        <p>Protected content</p>
      </AuthGuard>,
    );
    expect(screen.getByText("Protected content")).toBeInTheDocument();
  });
});
