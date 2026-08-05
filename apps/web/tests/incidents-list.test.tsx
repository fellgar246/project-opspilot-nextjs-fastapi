import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";

import { IncidentList } from "@/features/incidents/list/IncidentList";

vi.mock("@/features/auth/AuthProvider", () => ({
  useAuth: () => ({
    can: (capability: string) => capability === "read_incidents" || capability === "create_incidents",
  }),
}));

vi.mock("@/lib/auth-api", () => ({
  getDefaultApiBaseUrl: () => "http://localhost:8000",
}));

vi.mock("@/lib/incidents-api", () => ({
  fetchIncidents: vi.fn().mockResolvedValue({
    items: [
      {
        id: "inc-1",
        title: "Checkout errors",
        description: "5xx",
        severity: "sev2",
        status: "open",
        source: "manual",
        started_at: "2026-01-01T12:00:00Z",
        resolved_at: null,
        created_by: null,
        service_ids: [],
        created_at: "2026-01-01T12:00:00Z",
        updated_at: "2026-01-01T12:00:00Z",
      },
    ],
    next_cursor: null,
    total_estimate: 1,
  }),
  fetchServices: vi.fn().mockResolvedValue([]),
}));

function renderWithQuery(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe("IncidentList", () => {
  it("renders incidents from API", async () => {
    renderWithQuery(<IncidentList />);
    expect(await screen.findByText("Checkout errors")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /new incident/i })).toBeInTheDocument();
  });

  it("updates filters", async () => {
    const user = userEvent.setup();
    renderWithQuery(<IncidentList />);
    await screen.findByText("Checkout errors");
    await user.type(screen.getByPlaceholderText("Search title or description"), "checkout");
    await user.selectOptions(screen.getByDisplayValue("All statuses"), "open");
  });
});
