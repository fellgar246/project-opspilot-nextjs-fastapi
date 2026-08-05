import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { HealthStatus } from "@/components/HealthStatus";

describe("HealthStatus", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders health payload from the API", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          status: "ok",
          version: "0.1.0",
          git_sha: "abc123",
          checks: { db: "ok", redis: "ok" },
        }),
      }),
    );

    render(<HealthStatus apiBaseUrl="http://localhost:8000" />);

    await waitFor(() => {
      expect(screen.getByText(/Status:/)).toBeInTheDocument();
    });

    expect(screen.getByText("ok", { selector: "strong" })).toBeInTheDocument();
    expect(screen.getByText(/db: ok/)).toBeInTheDocument();
    expect(screen.getByText(/redis: ok/)).toBeInTheDocument();
  });

  it("shows an error when the API is unreachable", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("network down")),
    );

    render(<HealthStatus apiBaseUrl="http://localhost:8000" />);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("network down");
    });
  });
});
