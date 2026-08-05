import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import { AuthError, SessionExpiredError } from "@/features/auth/types";
import { fetchMe, login, logout } from "@/lib/auth-api";

describe("auth-api", () => {
  it("login throws AuthError on invalid credentials", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ detail: "Invalid credentials" }), { status: 401 })),
    );
    await expect(login("http://localhost:8000", "a@example.com", "bad")).rejects.toBeInstanceOf(AuthError);
  });

  it("fetchMe refreshes once on 401", async () => {
    let meCalls = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/api/v1/auth/refresh")) {
          return new Response(JSON.stringify({ user: { id: "1", email: "a@example.com", display_name: "A", role: "viewer" } }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (url.endsWith("/api/v1/auth/me")) {
          meCalls += 1;
          if (meCalls === 1) {
            return new Response(JSON.stringify({ detail: "Authentication required" }), { status: 401 });
          }
          return new Response(JSON.stringify({ id: "1", email: "a@example.com", display_name: "A", role: "viewer" }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response("not found", { status: 404, headers: init?.headers as HeadersInit });
      }),
    );

    const me = await fetchMe("http://localhost:8000");
    expect(me.email).toBe("a@example.com");
    expect(meCalls).toBe(2);
  });

  it("fetchMe surfaces session expiry when refresh fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo) => {
        const url = String(input);
        if (url.endsWith("/api/v1/auth/me")) {
          return new Response(JSON.stringify({ detail: "Authentication required" }), { status: 401 });
        }
        if (url.endsWith("/api/v1/auth/refresh")) {
          return new Response(JSON.stringify({ detail: "Authentication required" }), { status: 401 });
        }
        return new Response("not found", { status: 404 });
      }),
    );

    await expect(fetchMe("http://localhost:8000")).rejects.toBeInstanceOf(SessionExpiredError);
  });

  it("logout calls auth endpoint", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/api/v1/auth/logout")) {
          return new Response(null, { status: 204 });
        }
        return new Response("not found", { status: 404, headers: init?.headers as HeadersInit });
      }),
    );
    await expect(logout("http://localhost:8000")).resolves.toBeUndefined();
  });
});
