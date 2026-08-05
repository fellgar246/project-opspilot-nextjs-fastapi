import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

import { AuthProvider } from "@/features/auth/AuthProvider";

describe("AuthProvider", () => {
  it("loads current user on mount", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo) => {
        const url = String(input);
        if (url.endsWith("/api/v1/auth/me")) {
          return new Response(
            JSON.stringify({ id: "1", email: "a@example.com", display_name: "A", role: "operator" }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          );
        }
        return new Response("not found", { status: 404 });
      }),
    );

    render(
      <AuthProvider apiBaseUrl="http://localhost:8000">
        <p>child</p>
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        "http://localhost:8000/api/v1/auth/me",
        expect.objectContaining({ credentials: "include" }),
      );
    });
    expect(screen.getByText("child")).toBeInTheDocument();
  });
});
