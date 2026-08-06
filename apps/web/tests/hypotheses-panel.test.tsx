import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { HypothesesPanel } from "@/features/hypotheses/HypothesesPanel";

const hypotheses = [
  {
    id: "hyp-1",
    incident_id: "inc-1",
    statement: "Deployment regression caused checkout errors",
    confidence: 0.72,
    status: "proposed",
    supporting_evidence: ["ev-1"],
    contradicting_evidence: [],
    confidence_breakdown: { final: 0.72 },
    grounding: "mixed",
    critic_verdict: "weak",
    assumptions: ["Deploy preceded errors"],
    missing_evidence: ["recent_deployment"],
    rejection_reason: null,
    hypothesis_type: "deployment_regression",
    created_at: "2026-01-01T12:00:00Z",
    updated_at: "2026-01-01T12:00:00Z",
  },
  {
    id: "hyp-2",
    incident_id: "inc-1",
    statement: "Rejected hypothesis",
    confidence: 0.1,
    status: "rejected",
    supporting_evidence: ["ev-1"],
    contradicting_evidence: ["ev-2"],
    confidence_breakdown: { final: 0.1 },
    grounding: "knowledge_only",
    critic_verdict: "refuted",
    assumptions: [],
    missing_evidence: [],
    rejection_reason: "Refuted by critic",
    hypothesis_type: "config_error",
    created_at: "2026-01-01T12:00:00Z",
    updated_at: "2026-01-01T12:00:00Z",
  },
];

const evidence = [
  {
    id: "ev-1",
    incident_id: "inc-1",
    source_type: "deployment",
    source_reference: "dep-1",
    title: "Recent deployment",
    content: "v1.2.3",
    structured_data: {},
    observed_at: "2026-01-01T12:00:00Z",
    collected_at: "2026-01-01T12:00:00Z",
    relevance_score: null,
  },
  {
    id: "ev-2",
    incident_id: "inc-1",
    source_type: "metric",
    source_reference: "errors",
    title: "Stable errors",
    content: "flat",
    structured_data: {},
    observed_at: "2026-01-01T12:00:00Z",
    collected_at: "2026-01-01T12:00:00Z",
    relevance_score: null,
  },
];

describe("HypothesesPanel", () => {
  it("renders active hypothesis details and collapses rejected", () => {
    render(<HypothesesPanel hypotheses={hypotheses} evidence={evidence} />);
    const activeCard = document.querySelector(".hypothesis-card:not(.rejected)");
    expect(activeCard).not.toBeNull();
    expect(
      within(activeCard as HTMLElement).getByText(/Deployment regression caused checkout errors/),
    ).toBeInTheDocument();
    expect(screen.getByText(/Missing evidence/)).toBeInTheDocument();
    expect(screen.getByText(/1 rejected hypotheses/)).toBeInTheDocument();
    expect(screen.getByLabelText("Compare A")).toBeInTheDocument();
    expect(screen.getByLabelText("Compare B")).toBeInTheDocument();
  });
});
