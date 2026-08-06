"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

import { getDefaultApiBaseUrl } from "@/lib/auth-api";
import { fetchPendingApprovals, fetchProposedActions } from "@/lib/investigation-api";

type IncidentActionsPanelProps = {
  incidentId: string;
};

export function IncidentActionsPanel({ incidentId }: IncidentActionsPanelProps) {
  const apiBaseUrl = getDefaultApiBaseUrl();

  const actionsQuery = useQuery({
    queryKey: ["proposed-actions", incidentId],
    queryFn: () => fetchProposedActions(apiBaseUrl, incidentId),
  });

  const approvalsQuery = useQuery({
    queryKey: ["approvals", "pending"],
    queryFn: () => fetchPendingApprovals(apiBaseUrl),
  });

  const incidentApprovals =
    approvalsQuery.data?.items.filter((item) => item.incident_id === incidentId) ?? [];

  return (
    <div>
      <p className="meta">
        <Link href="/approvals">Approval Center</Link> · pending across all incidents
      </p>
      <h3>Pending approvals for this incident</h3>
      {incidentApprovals.length === 0 ? (
        <p role="status">No pending approvals for this incident.</p>
      ) : (
        incidentApprovals.map((approval) => (
          <article key={approval.id} className="card">
            <strong>{approval.action.action_type}</strong>
            <p>{approval.action.description}</p>
            <p className="meta">
              {approval.action.risk_level} · expires {new Date(approval.expires_at).toLocaleString()}
            </p>
          </article>
        ))
      )}

      <h3>Proposed actions</h3>
      {actionsQuery.isLoading ? <p role="status">Loading proposed actions…</p> : null}
      {actionsQuery.data?.items.length === 0 ? (
        <p role="status">No proposed actions yet.</p>
      ) : (
        actionsQuery.data?.items.map((action) => (
          <article key={action.id} className="card">
            <strong>{action.action_type}</strong>
            <p>{action.description}</p>
            <p className="meta">
              {action.risk_level} · {action.status}
            </p>
            <pre>{JSON.stringify(action.parameters, null, 2)}</pre>
          </article>
        ))
      )}
    </div>
  );
}
