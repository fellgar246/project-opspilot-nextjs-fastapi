import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  addIncidentNote,
  createIncident,
  fetchAuditForIncident,
  fetchEvidence,
  fetchHypotheses,
  fetchIncident,
  fetchIncidents,
  fetchServices,
  fetchTimeline,
  updateIncidentStatus,
} from "@/lib/incidents-api";

const fetchWithAuth = vi.fn();

vi.mock("@/lib/api-client", () => ({
  fetchWithAuth: (...args: unknown[]) => fetchWithAuth(...args),
}));

describe("incidents-api", () => {
  beforeEach(() => {
    fetchWithAuth.mockReset();
  });

  it("fetchIncidents builds query string", async () => {
    fetchWithAuth.mockResolvedValue({ items: [], next_cursor: null, total_estimate: 0 });
    await fetchIncidents("http://localhost:8000", {
      status: "open",
      severity: "sev2",
      service_id: "svc-1",
      search: "checkout",
      cursor: "abc",
      limit: 10,
    });
    expect(fetchWithAuth).toHaveBeenCalledWith(
      "http://localhost:8000",
      "/api/v1/incidents?status=open&severity=sev2&service_id=svc-1&search=checkout&cursor=abc&limit=10",
    );
  });

  it("fetchIncident loads by id", async () => {
    fetchWithAuth.mockResolvedValue({ id: "inc-1" });
    const incident = await fetchIncident("http://localhost:8000", "inc-1");
    expect(incident.id).toBe("inc-1");
  });

  it("createIncident posts payload", async () => {
    fetchWithAuth.mockResolvedValue({ id: "inc-2" });
    await createIncident("http://localhost:8000", {
      title: "Test",
      description: "Desc",
      severity: "sev3",
      service_ids: ["svc-1"],
      started_at: "2026-01-01T00:00:00Z",
    });
    expect(fetchWithAuth).toHaveBeenCalledWith(
      "http://localhost:8000",
      "/api/v1/incidents",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("updateIncidentStatus patches status", async () => {
    fetchWithAuth.mockResolvedValue({ id: "inc-1", status: "investigating" });
    await updateIncidentStatus("http://localhost:8000", "inc-1", "investigating", "reason");
    expect(fetchWithAuth).toHaveBeenCalledWith(
      "http://localhost:8000",
      "/api/v1/incidents/inc-1",
      expect.objectContaining({ method: "PATCH" }),
    );
  });

  it("fetchServices loads catalog", async () => {
    fetchWithAuth.mockResolvedValue([]);
    await fetchServices("http://localhost:8000");
    expect(fetchWithAuth).toHaveBeenCalledWith("http://localhost:8000", "/api/v1/services");
  });

  it("fetchTimeline loads entries", async () => {
    fetchWithAuth.mockResolvedValue({ items: [] });
    await fetchTimeline("http://localhost:8000", "inc-1");
    expect(fetchWithAuth).toHaveBeenCalledWith(
      "http://localhost:8000",
      "/api/v1/incidents/inc-1/timeline",
    );
  });

  it("fetchEvidence and fetchHypotheses load collections", async () => {
    fetchWithAuth.mockResolvedValue({ items: [], next_cursor: null, total_estimate: 0 });
    await fetchEvidence("http://localhost:8000", "inc-1");
    await fetchHypotheses("http://localhost:8000", "inc-1");
    expect(fetchWithAuth).toHaveBeenCalledTimes(2);
  });

  it("addIncidentNote posts note", async () => {
    fetchWithAuth.mockResolvedValue({ id: "note-1", kind: "note" });
    await addIncidentNote("http://localhost:8000", "inc-1", "hello");
    expect(fetchWithAuth).toHaveBeenCalledWith(
      "http://localhost:8000",
      "/api/v1/incidents/inc-1/notes",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("fetchAuditForIncident queries audit endpoint", async () => {
    fetchWithAuth.mockResolvedValue({ items: [] });
    await fetchAuditForIncident("http://localhost:8000", "inc-1");
    expect(fetchWithAuth).toHaveBeenCalledWith(
      "http://localhost:8000",
      "/api/v1/audit?entity_type=incident&entity_id=inc-1&page_size=100",
    );
  });
});
