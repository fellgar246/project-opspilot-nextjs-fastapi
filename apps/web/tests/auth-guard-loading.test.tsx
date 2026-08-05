import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/dashboard",
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/features/auth/AuthProvider", () => ({
  useAuth: () => ({
    user: null,
    loading: true,
    sessionExpired: false,
  }),
}));

import { AuthGuard } from "@/features/auth/AuthGuard";

describe("AuthGuard loading", () => {
  it("shows loading message while session resolves", () => {
    render(
      <AuthGuard>
        <p>Protected content</p>
      </AuthGuard>,
    );
    expect(screen.getByText("Loading session…")).toBeInTheDocument();
  });
});
