import { fetchWithAuth } from "@/lib/api-client";

export type IncidentSeverity = "sev1" | "sev2" | "sev3" | "sev4";
export type IncidentStatus =
  | "open"
  | "investigating"
  | "mitigating"
  | "monitoring"
  | "resolved"
  | "closed";
export type IncidentSource = "manual" | "alert" | "simulator";

export type Incident = {
  id: string;
  title: string;
  description: string;
  severity: IncidentSeverity;
  status: IncidentStatus;
  source: IncidentSource;
  started_at: string;
  resolved_at: string | null;
  created_by: string | null;
  service_ids: string[];
  created_at: string;
  updated_at: string;
};

export type IncidentListResponse = {
  items: Incident[];
  next_cursor: string | null;
  total_estimate: number;
};

export type Service = {
  id: string;
  name: string;
  description: string | null;
  repository: string | null;
  environment: "production" | "staging" | "demo";
  owner_team: string | null;
  is_active: boolean;
};

export type TimelineEntry = {
  id: string;
  occurred_at: string;
  kind: string;
  actor_type: string;
  actor_id: string | null;
  title: string;
  description: string | null;
  reference: Record<string, unknown> | null;
};

export type Evidence = {
  id: string;
  incident_id: string;
  source_type: string;
  source_reference: string;
  title: string;
  content: string;
  structured_data: Record<string, unknown>;
  observed_at: string;
  collected_at: string;
  relevance_score: number | null;
};

export type Hypothesis = {
  id: string;
  incident_id: string;
  statement: string;
  confidence: number;
  status: string;
  supporting_evidence: string[];
  contradicting_evidence: string[];
  created_at: string;
  updated_at: string;
};

export type CreateIncidentInput = {
  title: string;
  description: string;
  severity: IncidentSeverity;
  service_ids: string[];
  started_at: string;
  source?: IncidentSource;
};

export type IncidentFilters = {
  status?: IncidentStatus;
  severity?: IncidentSeverity;
  service_id?: string;
  search?: string;
  cursor?: string;
  limit?: number;
};

export async function fetchIncidents(
  apiBaseUrl: string,
  filters: IncidentFilters = {},
): Promise<IncidentListResponse> {
  const params = new URLSearchParams();
  if (filters.status) params.set("status", filters.status);
  if (filters.severity) params.set("severity", filters.severity);
  if (filters.service_id) params.set("service_id", filters.service_id);
  if (filters.search) params.set("search", filters.search);
  if (filters.cursor) params.set("cursor", filters.cursor);
  if (filters.limit) params.set("limit", String(filters.limit));
  const query = params.toString();
  return fetchWithAuth<IncidentListResponse>(
    apiBaseUrl,
    `/api/v1/incidents${query ? `?${query}` : ""}`,
  );
}

export async function fetchIncident(apiBaseUrl: string, id: string): Promise<Incident> {
  return fetchWithAuth<Incident>(apiBaseUrl, `/api/v1/incidents/${id}`);
}

export async function createIncident(
  apiBaseUrl: string,
  input: CreateIncidentInput,
): Promise<Incident> {
  return fetchWithAuth<Incident>(apiBaseUrl, "/api/v1/incidents", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function updateIncidentStatus(
  apiBaseUrl: string,
  id: string,
  status: IncidentStatus,
  reason?: string,
): Promise<Incident> {
  return fetchWithAuth<Incident>(apiBaseUrl, `/api/v1/incidents/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ status, reason }),
  });
}

export async function fetchServices(apiBaseUrl: string): Promise<Service[]> {
  return fetchWithAuth<Service[]>(apiBaseUrl, "/api/v1/services");
}

export async function fetchTimeline(
  apiBaseUrl: string,
  incidentId: string,
): Promise<{ items: TimelineEntry[] }> {
  return fetchWithAuth<{ items: TimelineEntry[] }>(
    apiBaseUrl,
    `/api/v1/incidents/${incidentId}/timeline`,
  );
}

export async function fetchEvidence(
  apiBaseUrl: string,
  incidentId: string,
): Promise<{ items: Evidence[]; next_cursor: string | null; total_estimate: number }> {
  return fetchWithAuth(apiBaseUrl, `/api/v1/incidents/${incidentId}/evidence`);
}

export async function fetchHypotheses(
  apiBaseUrl: string,
  incidentId: string,
): Promise<{ items: Hypothesis[]; next_cursor: string | null; total_estimate: number }> {
  return fetchWithAuth(apiBaseUrl, `/api/v1/incidents/${incidentId}/hypotheses`);
}

export async function addIncidentNote(
  apiBaseUrl: string,
  incidentId: string,
  content: string,
): Promise<TimelineEntry> {
  return fetchWithAuth<TimelineEntry>(apiBaseUrl, `/api/v1/incidents/${incidentId}/notes`, {
    method: "POST",
    body: JSON.stringify({ content }),
  });
}

export async function fetchAuditForIncident(
  apiBaseUrl: string,
  incidentId: string,
): Promise<{
  items: Array<{
    id: string;
    event_type: string;
    occurred_at: string;
    payload: Record<string, unknown>;
  }>;
}> {
  return fetchWithAuth(
    apiBaseUrl,
    `/api/v1/audit?entity_type=incident&entity_id=${incidentId}&page_size=100`,
  );
}
