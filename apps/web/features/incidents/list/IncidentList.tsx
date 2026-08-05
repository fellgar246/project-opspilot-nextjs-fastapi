"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { useAuth } from "@/features/auth/AuthProvider";
import { getDefaultApiBaseUrl } from "@/lib/auth-api";
import {
  fetchIncidents,
  fetchServices,
  type IncidentSeverity,
  type IncidentStatus,
} from "@/lib/incidents-api";

const STATUS_LABELS: Record<IncidentStatus, string> = {
  open: "Open",
  investigating: "Investigating",
  mitigating: "Mitigating",
  monitoring: "Monitoring",
  resolved: "Resolved",
  closed: "Closed",
};

export function IncidentList() {
  const { can } = useAuth();
  const apiBaseUrl = getDefaultApiBaseUrl();
  const [status, setStatus] = useState<IncidentStatus | "">("");
  const [severity, setSeverity] = useState<IncidentSeverity | "">("");
  const [serviceId, setServiceId] = useState("");
  const [search, setSearch] = useState("");
  const [cursor, setCursor] = useState<string | undefined>();

  const servicesQuery = useQuery({
    queryKey: ["services"],
    queryFn: () => fetchServices(apiBaseUrl),
  });

  const incidentsQuery = useQuery({
    queryKey: ["incidents", { status, severity, serviceId, search, cursor }],
    queryFn: () =>
      fetchIncidents(apiBaseUrl, {
        status: status || undefined,
        severity: severity || undefined,
        service_id: serviceId || undefined,
        search: search || undefined,
        cursor,
        limit: 25,
      }),
  });

  if (!can("read_incidents")) {
    return <p role="status">You do not have permission to view incidents.</p>;
  }

  return (
    <section className="incidents-page">
      <header className="page-header">
        <h1>Incidents</h1>
        {can("create_incidents") ? (
          <Link href="/incidents/new" className="button-link">
            New incident
          </Link>
        ) : null}
      </header>

      <div className="filters">
        <input
          type="search"
          placeholder="Search title or description"
          value={search}
          onChange={(event) => {
            setCursor(undefined);
            setSearch(event.target.value);
          }}
        />
        <select
          value={status}
          onChange={(event) => {
            setCursor(undefined);
            setStatus(event.target.value as IncidentStatus | "");
          }}
        >
          <option value="">All statuses</option>
          {Object.entries(STATUS_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        <select
          value={severity}
          onChange={(event) => {
            setCursor(undefined);
            setSeverity(event.target.value as IncidentSeverity | "");
          }}
        >
          <option value="">All severities</option>
          <option value="sev1">SEV1</option>
          <option value="sev2">SEV2</option>
          <option value="sev3">SEV3</option>
          <option value="sev4">SEV4</option>
        </select>
        <select
          value={serviceId}
          onChange={(event) => {
            setCursor(undefined);
            setServiceId(event.target.value);
          }}
        >
          <option value="">All services</option>
          {(servicesQuery.data ?? []).map((service) => (
            <option key={service.id} value={service.id}>
              {service.name}
            </option>
          ))}
        </select>
      </div>

      {incidentsQuery.isLoading ? <p role="status">Loading incidents…</p> : null}
      {incidentsQuery.isError ? (
        <p role="alert">Unable to load incidents: {incidentsQuery.error.message}</p>
      ) : null}

      {incidentsQuery.data && incidentsQuery.data.items.length === 0 ? (
        <p role="status">No incidents match your filters.</p>
      ) : null}

      {incidentsQuery.data && incidentsQuery.data.items.length > 0 ? (
        <>
          <p className="meta">
            Showing {incidentsQuery.data.items.length} of ~{incidentsQuery.data.total_estimate}
          </p>
          <ul className="incident-list">
            {incidentsQuery.data.items.map((incident) => (
              <li key={incident.id}>
                <Link href={`/incidents/${incident.id}`}>
                  <span className={`severity severity-${incident.severity}`}>
                    {incident.severity.toUpperCase()}
                  </span>
                  <span className="title">{incident.title}</span>
                  <span className="status">{STATUS_LABELS[incident.status]}</span>
                  <span className="date">
                    {new Date(incident.started_at).toLocaleString()}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
          <div className="pagination">
            {cursor ? (
              <button type="button" onClick={() => setCursor(undefined)}>
                First page
              </button>
            ) : null}
            {incidentsQuery.data.next_cursor ? (
              <button type="button" onClick={() => setCursor(incidentsQuery.data!.next_cursor!)}>
                Next page
              </button>
            ) : null}
          </div>
        </>
      ) : null}
    </section>
  );
}
