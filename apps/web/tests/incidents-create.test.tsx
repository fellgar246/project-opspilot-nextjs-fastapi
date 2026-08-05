import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";

import { CreateIncidentForm } from "@/features/incidents/create/CreateIncidentForm";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@/features/auth/AuthProvider", () => ({
  useAuth: () => ({
    can: (capability: string) => capability === "create_incidents",
  }),
}));

vi.mock("@/lib/auth-api", () => ({
  getDefaultApiBaseUrl: () => "http://localhost:8000",
}));

vi.mock("@/lib/incidents-api", () => ({
  fetchServices: vi.fn().mockResolvedValue([
    { id: "svc-1", name: "demo-service", environment: "demo", is_active: true },
  ]),
  createIncident: vi.fn(),
}));

function renderWithQuery(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe("CreateIncidentForm", () => {
  it("renders form fields", async () => {
    renderWithQuery(<CreateIncidentForm />);
    expect(screen.getByRole("heading", { name: "Create incident" })).toBeInTheDocument();
    expect(await screen.findByText("demo-service (demo)")).toBeInTheDocument();
  });

  it("submits the form", async () => {
    const user = (await import("@testing-library/user-event")).default.setup();
    const { createIncident } = await import("@/lib/incidents-api");
    renderWithQuery(<CreateIncidentForm />);
    await screen.findByText("demo-service (demo)");
    await user.click(screen.getByLabelText(/demo-service/));
    await user.type(screen.getByLabelText(/^Title/i), "New incident");
    await user.type(screen.getByLabelText(/^Description/i), "Something broke");
    await user.click(screen.getByRole("button", { name: "Create incident" }));
    expect(createIncident).toHaveBeenCalled();
  });
});
