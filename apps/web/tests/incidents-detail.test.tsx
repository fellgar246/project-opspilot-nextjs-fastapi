import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";

import { IncidentDetail } from "@/features/incidents/detail/IncidentDetail";

vi.mock("@/features/auth/AuthProvider", () => ({
  useAuth: () => ({
    can: () => true,
    user: { role: "operator" },
  }),
}));

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/lib/auth-api", () => ({
  getDefaultApiBaseUrl: () => "http://localhost:8000",
}));

vi.mock("@/lib/investigation-api", () => ({
  fetchAgentRuns: vi.fn().mockResolvedValue({ items: [] }),
  fetchProposedActions: vi.fn().mockResolvedValue({ items: [] }),
  fetchPendingApprovals: vi.fn().mockResolvedValue({ items: [] }),
  startInvestigation: vi.fn(),
  pauseInvestigation: vi.fn(),
  resumeInvestigation: vi.fn(),
  investigationEventsUrl: vi.fn().mockReturnValue("http://localhost:8000/api/v1/incidents/inc-1/events"),
}));

vi.mock("@/lib/actions-api", () => ({
  fetchActionExecutions: vi.fn().mockResolvedValue({ items: [] }),
}));

vi.mock("@/lib/postmortem-api", () => ({
  fetchPostmortem: vi.fn().mockRejectedValue(new Error("not found")),
  generatePostmortem: vi.fn(),
  savePostmortemEdit: vi.fn(),
  postmortemExportUrl: vi.fn().mockReturnValue("http://localhost:8000/api/v1/incidents/inc-1/postmortem/export?format=md"),
}));

vi.mock("@/lib/sse-client", () => ({
  InvestigationEventSource: class {
    connect() {}
    close() {}
    needsFullReload() {
      return false;
    }
    getLastEventId() {
      return 0;
    }
  },
}));

vi.mock("@/lib/incidents-api", () => ({
  fetchIncident: vi.fn().mockResolvedValue({
    id: "inc-1",
    title: "Checkout errors",
    description: "5xx on checkout",
    severity: "sev2",
    status: "open",
    source: "manual",
    started_at: "2026-01-01T12:00:00Z",
    resolved_at: null,
    created_by: null,
    service_ids: [],
    created_at: "2026-01-01T12:00:00Z",
    updated_at: "2026-01-01T12:00:00Z",
  }),
  fetchTimeline: vi.fn().mockResolvedValue({
    items: [
      {
        id: "tl-1",
        occurred_at: "2026-01-01T12:00:00Z",
        kind: "status_change",
        actor_type: "user",
        actor_id: null,
        title: "Incident created",
        description: "Created",
        reference: null,
      },
    ],
  }),
  fetchEvidence: vi.fn().mockResolvedValue({
    items: [
      {
        id: "ev-1",
        incident_id: "inc-1",
        source_type: "metric",
        source_reference: "prom/errors",
        title: "Errors",
        content: "42/min",
        structured_data: {},
        observed_at: "2026-01-01T12:00:00Z",
        collected_at: "2026-01-01T12:00:00Z",
        relevance_score: null,
      },
    ],
    next_cursor: null,
    total_estimate: 1,
  }),
  fetchHypotheses: vi.fn().mockResolvedValue({
    items: [
      {
        id: "hyp-1",
        incident_id: "inc-1",
        statement: "Pool exhausted",
        confidence: 0.8,
        status: "proposed",
        supporting_evidence: ["ev-1"],
        contradicting_evidence: [],
        confidence_breakdown: { final: 0.8 },
        grounding: "observed",
        critic_verdict: "weak",
        assumptions: [],
        missing_evidence: [],
        rejection_reason: null,
        hypothesis_type: "resource_exhaustion",
        created_at: "2026-01-01T12:00:00Z",
        updated_at: "2026-01-01T12:00:00Z",
      },
    ],
    next_cursor: null,
    total_estimate: 1,
  }),
  fetchAuditForIncident: vi.fn().mockResolvedValue({
    items: [
      {
        id: "audit-1",
        event_type: "incident.created",
        occurred_at: "2026-01-01T12:00:00Z",
        payload: {},
      },
    ],
  }),
  updateIncidentStatus: vi.fn().mockResolvedValue({ id: "inc-1", status: "investigating" }),
  addIncidentNote: vi.fn().mockResolvedValue({
    id: "note-1",
    occurred_at: "2026-01-01T12:00:00Z",
    kind: "note",
    actor_type: "user",
    actor_id: null,
    title: "Manual note",
    description: "hello",
    reference: null,
  }),
}));

function renderWithQuery(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe("IncidentDetail tabs", () => {
  it("renders overview and placeholder tabs", async () => {
    renderWithQuery(<IncidentDetail incidentId="inc-1" />);
    expect(await screen.findByText("Checkout errors")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Investigation" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Actions" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Postmortem" })).toBeInTheDocument();
  });

  it("shows investigation panel when investigation tab selected", async () => {
    const user = (await import("@testing-library/user-event")).default.setup();
    renderWithQuery(<IncidentDetail incidentId="inc-1" />);
    await screen.findByText("Checkout errors");
    await user.click(screen.getByRole("button", { name: "Investigation" }));
    expect(screen.getByText(/Connection:/)).toBeInTheDocument();
  });

  it("renders evidence tab content", async () => {
    const user = (await import("@testing-library/user-event")).default.setup();
    renderWithQuery(<IncidentDetail incidentId="inc-1" />);
    await screen.findByRole("heading", { name: "Checkout errors" });
    await user.click(screen.getByRole("button", { name: "Evidence" }));
    expect(await screen.findByText("Errors")).toBeInTheDocument();
  });

  it("supports timeline note form and status transition", async () => {
    const user = (await import("@testing-library/user-event")).default.setup();
    renderWithQuery(<IncidentDetail incidentId="inc-1" />);
    await screen.findByRole("heading", { name: "Checkout errors" });
    await user.click(screen.getByRole("button", { name: "Timeline" }));
    const textarea = await screen.findByPlaceholderText("Add a manual note…");
    await user.type(textarea, "Investigating now");
    await user.click(screen.getByRole("button", { name: "Add note" }));
    await user.click(screen.getByRole("button", { name: /Move to investigating/i }));
  });

  it("shows empty placeholders for actions and postmortem", async () => {
    const user = (await import("@testing-library/user-event")).default.setup();
    renderWithQuery(<IncidentDetail incidentId="inc-1" />);
    await screen.findByRole("heading", { name: "Checkout errors" });
    await user.click(screen.getByRole("button", { name: "Actions" }));
    expect(screen.getByText(/No proposed actions yet/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Postmortem" }));
    expect(screen.getByText(/No postmortem generated yet/)).toBeInTheDocument();
  });
});
