import { fetchWithAuth } from "@/lib/api-client";
import type { InvestigationEvent } from "@/lib/sse-client";

export type { InvestigationEvent };

export type AgentRun = {
  id: string;
  incident_id: string;
  graph_thread_id: string;
  status: string;
  model: string;
  prompt_version: string;
  started_at: string | null;
  completed_at: string | null;
  token_usage: Record<string, number>;
  error: string | null;
  node_progress: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type ProposedAction = {
  id: string;
  incident_id: string;
  agent_run_id: string;
  action_type: string;
  description: string;
  target: string;
  parameters: Record<string, unknown>;
  risk_level: string;
  risk_rationale: string;
  expected_result: string;
  rollback_plan: string;
  supporting_evidence: string[];
  hypothesis_ids: string[];
  status: string;
  requested_by: string | null;
  created_at: string;
};

export type Approval = {
  id: string;
  proposed_action_id: string;
  incident_id: string;
  incident_title: string;
  incident_severity: string;
  action: ProposedAction;
  decision: string;
  reason: string | null;
  expires_at: string;
  requested_at: string;
  reviewed_at: string | null;
  reviewed_by: string | null;
};

export async function startInvestigation(
  apiBaseUrl: string,
  incidentId: string,
): Promise<{ agent_run_id: string; status: string }> {
  return fetchWithAuth(apiBaseUrl, `/api/v1/incidents/${incidentId}/start-investigation`, {
    method: "POST",
  });
}

export async function pauseInvestigation(apiBaseUrl: string, incidentId: string): Promise<AgentRun> {
  return fetchWithAuth(apiBaseUrl, `/api/v1/incidents/${incidentId}/pause`, { method: "POST" });
}

export async function resumeInvestigation(
  apiBaseUrl: string,
  incidentId: string,
): Promise<AgentRun> {
  return fetchWithAuth(apiBaseUrl, `/api/v1/incidents/${incidentId}/resume`, { method: "POST" });
}

export async function fetchAgentRuns(
  apiBaseUrl: string,
  incidentId: string,
): Promise<{ items: AgentRun[] }> {
  return fetchWithAuth(apiBaseUrl, `/api/v1/incidents/${incidentId}/agent-runs`);
}

export async function fetchProposedActions(
  apiBaseUrl: string,
  incidentId: string,
): Promise<{ items: ProposedAction[] }> {
  return fetchWithAuth(apiBaseUrl, `/api/v1/incidents/${incidentId}/proposed-actions`);
}

export async function fetchPendingApprovals(apiBaseUrl: string): Promise<{ items: Approval[] }> {
  return fetchWithAuth(apiBaseUrl, "/api/v1/approvals/pending");
}

export async function approveAction(apiBaseUrl: string, approvalId: string): Promise<Approval> {
  return fetchWithAuth(apiBaseUrl, `/api/v1/approvals/${approvalId}/approve`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export async function rejectAction(
  apiBaseUrl: string,
  approvalId: string,
  reason: string,
): Promise<Approval> {
  return fetchWithAuth(apiBaseUrl, `/api/v1/approvals/${approvalId}/reject`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
}

export function investigationEventsUrl(apiBaseUrl: string, incidentId: string): string {
  return `${apiBaseUrl}/api/v1/incidents/${incidentId}/events`;
}

export function approvalEventsUrl(apiBaseUrl: string): string {
  return `${apiBaseUrl}/api/v1/approvals/events`;
}

export async function fetchEventHistory(
  apiBaseUrl: string,
  incidentId: string,
  afterSeq = 0,
): Promise<{ items: InvestigationEvent[]; latest_seq: number }> {
  const params = afterSeq > 0 ? `?after_seq=${afterSeq}` : "";
  return fetchWithAuth(
    apiBaseUrl,
    `/api/v1/incidents/${incidentId}/events/history${params}`,
  );
}
