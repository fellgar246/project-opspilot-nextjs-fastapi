import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import { AuthGuard } from "@/features/auth/AuthGuard";

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  usePathname: () => "/dashboard",
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/features/auth/AuthProvider", () => ({
  useAuth: () => ({
    user: null,
    loading: false,
    sessionExpired: true,
  }),
}));

describe("AuthGuard", () => {
  it("redirects unauthenticated users to login with next param", () => {
    render(
      <AuthGuard>
        <p>Protected</p>
      </AuthGuard>,
    );
    expect(replace).toHaveBeenCalledWith("/login?expired=1&next=%2Fdashboard");
    expect(screen.queryByText("Protected")).not.toBeInTheDocument();
  });
});
