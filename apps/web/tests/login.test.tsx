import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { LoginForm } from "@/features/auth/LoginForm";
import { AuthProvider } from "@/features/auth/AuthProvider";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams("next=/dashboard"),
}));

describe("LoginForm", () => {
  it("submits credentials and redirects on success", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo) => {
        const url = String(input);
        if (url.endsWith("/api/v1/auth/login")) {
          return new Response(JSON.stringify({ user: { id: "1", email: "a@b.com", display_name: "A", role: "viewer" } }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (url.endsWith("/api/v1/auth/me")) {
          return new Response(JSON.stringify({ id: "1", email: "a@b.com", display_name: "A", role: "viewer" }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response("not found", { status: 404 });
      }),
    );

    render(
      <AuthProvider apiBaseUrl="http://localhost:8000">
        <LoginForm />
      </AuthProvider>,
    );

    await user.type(screen.getByLabelText("Email"), "viewer@ops-pilot.local");
    await user.type(screen.getByLabelText("Password"), "password");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        "http://localhost:8000/api/v1/auth/login",
        expect.objectContaining({ method: "POST", credentials: "include" }),
      );
    });
  });
});
