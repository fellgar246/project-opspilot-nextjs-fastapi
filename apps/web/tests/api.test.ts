import { describe, expect, it, vi } from "vitest";

import { fetchHealth, getApiBaseUrl } from "@/lib/api";

describe("api client", () => {
  it("uses NEXT_PUBLIC_API_URL when set", () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "http://example.com:9000");
    expect(getApiBaseUrl()).toBe("http://example.com:9000");
  });

  it("throws when health responds with unexpected status", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        json: async () => ({}),
      }),
    );

    await expect(fetchHealth("http://localhost:8000")).rejects.toThrow(
      "Health request failed with status 500",
    );
  });
});
