import { fetchWithAuth } from "@/lib/api-client";

export type ActionExecution = {
  id: string;
  incident_id: string;
  proposed_action_id: string;
  approval_id: string;
  execution_status: string;
  input_payload: Record<string, unknown>;
  output_payload: Record<string, unknown> | null;
  idempotency_key: string;
  error: string | null;
  started_at: string;
  completed_at: string | null;
};

export async function fetchActionExecutions(
  apiBaseUrl: string,
  incidentId: string,
): Promise<{ items: ActionExecution[] }> {
  return fetchWithAuth(apiBaseUrl, `/api/v1/incidents/${incidentId}/action-executions`);
}
