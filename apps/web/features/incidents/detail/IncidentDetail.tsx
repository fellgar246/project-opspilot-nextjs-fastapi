"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { HypothesesPanel } from "@/features/hypotheses/HypothesesPanel";
import { IncidentActionsPanel } from "@/features/approvals/IncidentActionsPanel";
import { InvestigationLivePanel } from "@/features/investigation-live/InvestigationLivePanel";
import { useAuth } from "@/features/auth/AuthProvider";
import { getDefaultApiBaseUrl } from "@/lib/auth-api";
import {
  addIncidentNote,
  fetchAuditForIncident,
  fetchEvidence,
  fetchHypotheses,
  fetchIncident,
  fetchTimeline,
  updateIncidentStatus,
  type IncidentStatus,
} from "@/lib/incidents-api";

const TABS = [
  "overview",
  "investigation",
  "timeline",
  "evidence",
  "hypotheses",
  "actions",
  "audit",
  "postmortem",
] as const;

type TabId = (typeof TABS)[number];

const TAB_LABELS: Record<TabId, string> = {
  overview: "Overview",
  investigation: "Investigation",
  timeline: "Timeline",
  evidence: "Evidence",
  hypotheses: "Hypotheses",
  actions: "Actions",
  audit: "Audit",
  postmortem: "Postmortem",
};

const NEXT_STATUS: Partial<Record<IncidentStatus, IncidentStatus>> = {
  open: "investigating",
  investigating: "mitigating",
  mitigating: "monitoring",
  monitoring: "resolved",
  resolved: "closed",
};

type IncidentDetailProps = {
  incidentId: string;
};

function Placeholder({ spec, title }: { spec: string; title: string }) {
  return (
    <div className="tab-placeholder" role="status">
      <h3>{title}</h3>
      <p>This section will be implemented in {spec}.</p>
    </div>
  );
}

export function IncidentDetail({ incidentId }: IncidentDetailProps) {
  const { can } = useAuth();
  const apiBaseUrl = getDefaultApiBaseUrl();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<TabId>("overview");
  const [note, setNote] = useState("");
  const [focusedEvidenceId, setFocusedEvidenceId] = useState<string | null>(null);

  const incidentQuery = useQuery({
    queryKey: ["incident", incidentId],
    queryFn: () => fetchIncident(apiBaseUrl, incidentId),
  });

  const timelineQuery = useQuery({
    queryKey: ["timeline", incidentId],
    queryFn: () => fetchTimeline(apiBaseUrl, incidentId),
    enabled: activeTab === "timeline" || activeTab === "overview",
  });

  const evidenceQuery = useQuery({
    queryKey: ["evidence", incidentId],
    queryFn: () => fetchEvidence(apiBaseUrl, incidentId),
    enabled: activeTab === "evidence",
  });

  const hypothesesQuery = useQuery({
    queryKey: ["hypotheses", incidentId],
    queryFn: () => fetchHypotheses(apiBaseUrl, incidentId),
    enabled: activeTab === "hypotheses",
  });

  const evidenceForHypothesesQuery = useQuery({
    queryKey: ["evidence", incidentId],
    queryFn: () => fetchEvidence(apiBaseUrl, incidentId),
    enabled: activeTab === "hypotheses",
  });

  const auditQuery = useQuery({
    queryKey: ["audit", incidentId],
    queryFn: () => fetchAuditForIncident(apiBaseUrl, incidentId),
    enabled: activeTab === "audit" && can("read_audit"),
  });

  const statusMutation = useMutation({
    mutationFn: (status: IncidentStatus) =>
      updateIncidentStatus(apiBaseUrl, incidentId, status, `Transition to ${status}`),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["incident", incidentId] });
      void queryClient.invalidateQueries({ queryKey: ["timeline", incidentId] });
      void queryClient.invalidateQueries({ queryKey: ["incidents"] });
    },
  });

  const noteMutation = useMutation({
    mutationFn: (content: string) => addIncidentNote(apiBaseUrl, incidentId, content),
    onSuccess: () => {
      setNote("");
      void queryClient.invalidateQueries({ queryKey: ["timeline", incidentId] });
    },
  });

  if (incidentQuery.isLoading) {
    return <p role="status">Loading incident…</p>;
  }

  if (incidentQuery.isError) {
    return <p role="alert">Unable to load incident: {incidentQuery.error.message}</p>;
  }

  const incident = incidentQuery.data!;
  const nextStatus = NEXT_STATUS[incident.status];

  return (
    <section className="incident-detail">
      <header className="page-header">
        <div>
          <Link href="/incidents">← Incidents</Link>
          <h1>{incident.title}</h1>
          <p className="meta">
            {incident.severity.toUpperCase()} · {incident.status} ·{" "}
            {new Date(incident.started_at).toLocaleString()}
          </p>
        </div>
        {can("manage_investigation") && nextStatus ? (
          <button
            type="button"
            disabled={statusMutation.isPending}
            onClick={() => statusMutation.mutate(nextStatus)}
          >
            Move to {nextStatus}
          </button>
        ) : null}
      </header>

      <nav className="tab-nav" aria-label="Incident sections">
        {TABS.map((tab) => (
          <button
            key={tab}
            type="button"
            className={activeTab === tab ? "active" : undefined}
            onClick={() => setActiveTab(tab)}
          >
            {TAB_LABELS[tab]}
          </button>
        ))}
      </nav>

      <div className="tab-panel">
        {activeTab === "overview" ? (
          <div>
            <h2>Description</h2>
            <p>{incident.description}</p>
            <h2>Recent timeline</h2>
            {timelineQuery.isLoading ? <p role="status">Loading timeline…</p> : null}
            {timelineQuery.data?.items.slice(-5).map((entry) => (
              <article key={entry.id} className="timeline-entry">
                <time dateTime={entry.occurred_at}>
                  {new Date(entry.occurred_at).toLocaleString()}
                </time>
                <strong>{entry.title}</strong>
                {entry.description ? <p>{entry.description}</p> : null}
              </article>
            )) ?? null}
          </div>
        ) : null}

        {activeTab === "investigation" ? <InvestigationLivePanel incidentId={incidentId} /> : null}

        {activeTab === "timeline" ? (
          <div>
            {can("manage_investigation") ? (
              <form
                className="note-form"
                onSubmit={(event) => {
                  event.preventDefault();
                  if (note.trim()) noteMutation.mutate(note.trim());
                }}
              >
                <textarea
                  rows={3}
                  placeholder="Add a manual note…"
                  value={note}
                  onChange={(event) => setNote(event.target.value)}
                />
                <button type="submit" disabled={noteMutation.isPending || !note.trim()}>
                  Add note
                </button>
              </form>
            ) : null}
            {timelineQuery.isLoading ? <p role="status">Loading timeline…</p> : null}
            {timelineQuery.isError ? (
              <p role="alert">Unable to load timeline.</p>
            ) : (
              (timelineQuery.data?.items ?? []).map((entry) => (
                <article key={entry.id} className="timeline-entry">
                  <time dateTime={entry.occurred_at}>
                    {new Date(entry.occurred_at).toLocaleString()}
                  </time>
                  <span className="kind">{entry.kind}</span>
                  <strong>{entry.title}</strong>
                  {entry.description ? <p>{entry.description}</p> : null}
                </article>
              ))
            )}
            {timelineQuery.data?.items.length === 0 ? (
              <p role="status">No timeline entries yet.</p>
            ) : null}
          </div>
        ) : null}

        {activeTab === "evidence" ? (
          <div>
            {evidenceQuery.isLoading ? <p role="status">Loading evidence…</p> : null}
            {evidenceQuery.isError ? <p role="alert">Unable to load evidence.</p> : null}
            {evidenceQuery.data?.items.length === 0 ? (
              <p role="status">No evidence collected yet. Evidence is added by the agent (SPEC-06).</p>
            ) : (
              evidenceQuery.data?.items.map((item) => (
                <article
                  key={item.id}
                  id={`evidence-${item.id}`}
                  className={`card ${focusedEvidenceId === item.id ? "focused-evidence" : ""}`}
                >
                  <h3>{item.title}</h3>
                  <p className="meta">
                    {item.source_type} · {item.source_reference}
                    {item.source_type === "runbook" || item.source_type === "similar_incident" ? (
                      <span className="knowledge-badge"> retrieved knowledge</span>
                    ) : (
                      <span className="observed-badge"> observed</span>
                    )}
                  </p>
                  <p>{item.content}</p>
                </article>
              ))
            )}
          </div>
        ) : null}

        {activeTab === "hypotheses" ? (
          <div>
            {hypothesesQuery.isLoading ? <p role="status">Loading hypotheses…</p> : null}
            {hypothesesQuery.data?.items.length === 0 ? (
              <p role="status">
                No hypotheses yet. Hypotheses are generated by the agent (SPEC-06/07).
              </p>
            ) : (
              <HypothesesPanel
                hypotheses={hypothesesQuery.data?.items ?? []}
                evidence={evidenceForHypothesesQuery.data?.items ?? []}
                onNavigateEvidence={(evidenceId) => {
                  setFocusedEvidenceId(evidenceId);
                  setActiveTab("evidence");
                }}
              />
            )}
          </div>
        ) : null}

        {activeTab === "actions" ? <IncidentActionsPanel incidentId={incidentId} /> : null}

        {activeTab === "audit" ? (
          <div>
            {!can("read_audit") ? (
              <p role="status">Audit log requires approver or admin role.</p>
            ) : auditQuery.isLoading ? (
              <p role="status">Loading audit events…</p>
            ) : auditQuery.data?.items.length === 0 ? (
              <p role="status">No audit events for this incident.</p>
            ) : (
              auditQuery.data?.items.map((event) => (
                <article key={event.id} className="timeline-entry">
                  <time dateTime={event.occurred_at}>
                    {new Date(event.occurred_at).toLocaleString()}
                  </time>
                  <strong>{event.event_type}</strong>
                </article>
              ))
            )}
          </div>
        ) : null}

        {activeTab === "postmortem" ? (
          <Placeholder spec="SPEC-09" title="Postmortem" />
        ) : null}
      </div>
    </section>
  );
}
