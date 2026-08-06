"use client";

import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { fetchActionExecutions } from "@/lib/actions-api";
import { getDefaultApiBaseUrl } from "@/lib/auth-api";
import { fetchPendingApprovals, fetchProposedActions } from "@/lib/investigation-api";
import { InvestigationEventSource } from "@/lib/sse-client";

type ActionsPanelProps = {
  incidentId: string;
};

export function ActionsPanel({ incidentId }: ActionsPanelProps) {
  const apiBaseUrl = getDefaultApiBaseUrl();
  const queryClient = useQueryClient();

  const actionsQuery = useQuery({
    queryKey: ["proposed-actions", incidentId],
    queryFn: () => fetchProposedActions(apiBaseUrl, incidentId),
  });

  const executionsQuery = useQuery({
    queryKey: ["action-executions", incidentId],
    queryFn: () => fetchActionExecutions(apiBaseUrl, incidentId),
  });

  const approvalsQuery = useQuery({
    queryKey: ["approvals", "pending"],
    queryFn: () => fetchPendingApprovals(apiBaseUrl),
  });

  useEffect(() => {
    const source = new InvestigationEventSource(
      `${apiBaseUrl}/api/v1/incidents/${incidentId}/events`,
      (event) => {
        if (event.type === "action_executed" || event.type === "recovery_verified") {
          void queryClient.invalidateQueries({ queryKey: ["action-executions", incidentId] });
          void queryClient.invalidateQueries({ queryKey: ["proposed-actions", incidentId] });
        }
      },
      () => {},
    );
    source.connect();
    return () => source.close();
  }, [apiBaseUrl, incidentId, queryClient]);

  const incidentApprovals =
    approvalsQuery.data?.items.filter((item) => item.incident_id === incidentId) ?? [];

  const executionByAction = new Map(
    executionsQuery.data?.items.map((item) => [item.proposed_action_id, item]) ?? [],
  );

  return (
    <div>
      <p className="meta">
        <Link href="/approvals">Approval Center</Link> · live execution updates via SSE
      </p>

      <h3>Action lifecycle</h3>
      {actionsQuery.isLoading ? <p role="status">Loading actions…</p> : null}
      {actionsQuery.data?.items.length === 0 ? (
        <p role="status">No proposed actions yet.</p>
      ) : (
        actionsQuery.data?.items.map((action) => {
          const execution = executionByAction.get(action.id);
          return (
            <article key={action.id} className="card">
              <strong>{action.action_type}</strong>
              <p>{action.description}</p>
              <p className="meta">
                Risk: {action.risk_level} · Proposal: {action.status}
                {execution ? ` · Execution: ${execution.execution_status}` : ""}
              </p>
              <p className="meta">
                <Link href={`/incidents/${incidentId}?tab=evidence`}>Evidence</Link>
                {" · "}
                <Link href={`/incidents/${incidentId}?tab=hypotheses`}>Hypotheses</Link>
              </p>
              <details>
                <summary>Parameters executed</summary>
                <pre>{JSON.stringify(action.parameters, null, 2)}</pre>
              </details>
              {execution?.output_payload ? (
                <details>
                  <summary>Execution output</summary>
                  <pre>{JSON.stringify(execution.output_payload, null, 2)}</pre>
                </details>
              ) : null}
              {execution?.error ? <p className="error">{execution.error}</p> : null}
            </article>
          );
        })
      )}

      <h3>Pending approvals</h3>
      {incidentApprovals.length === 0 ? (
        <p role="status">No pending approvals for this incident.</p>
      ) : (
        incidentApprovals.map((approval) => (
          <article key={approval.id} className="card">
            <strong>{approval.action.action_type}</strong>
            <p>{approval.action.description}</p>
            <p className="meta">
              {approval.action.risk_level} · expires{" "}
              {new Date(approval.expires_at).toLocaleString()}
            </p>
          </article>
        ))
      )}
    </div>
  );
}
