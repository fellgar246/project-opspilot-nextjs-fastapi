import { fetchWithAuth } from "@/lib/api-client";

export type Postmortem = {
  id: string;
  incident_id: string;
  version: number;
  status: string;
  content: string;
  invalid_references: string[];
  created_by: string;
  created_at: string;
};

export async function fetchPostmortem(
  apiBaseUrl: string,
  incidentId: string,
): Promise<Postmortem> {
  return fetchWithAuth(apiBaseUrl, `/api/v1/incidents/${incidentId}/postmortem`);
}

export async function generatePostmortem(
  apiBaseUrl: string,
  incidentId: string,
): Promise<Postmortem> {
  return fetchWithAuth(apiBaseUrl, `/api/v1/incidents/${incidentId}/postmortem/generate`, {
    method: "POST",
  });
}

export async function savePostmortemEdit(
  apiBaseUrl: string,
  incidentId: string,
  content: string,
): Promise<Postmortem> {
  return fetchWithAuth(apiBaseUrl, `/api/v1/incidents/${incidentId}/postmortem`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
}

export function postmortemExportUrl(apiBaseUrl: string, incidentId: string, format: "md" | "pdf") {
  return `${apiBaseUrl}/api/v1/incidents/${incidentId}/export?format=${format}`;
}
