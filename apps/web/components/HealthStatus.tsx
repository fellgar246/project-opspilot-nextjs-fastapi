"use client";

import { useEffect, useState } from "react";

import { fetchHealth, getApiBaseUrl, type HealthResponse } from "@/lib/api";

type HealthStatusProps = {
  apiBaseUrl?: string;
};

export function HealthStatus({ apiBaseUrl = getApiBaseUrl() }: HealthStatusProps) {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    fetchHealth(apiBaseUrl)
      .then((payload) => {
        if (active) {
          setHealth(payload);
        }
      })
      .catch((err: unknown) => {
        if (active) {
          setError(err instanceof Error ? err.message : "Unknown error");
        }
      });

    return () => {
      active = false;
    };
  }, [apiBaseUrl]);

  if (error) {
    return <p role="alert">API unreachable: {error}</p>;
  }

  if (!health) {
    return <p>Checking API health…</p>;
  }

  return (
    <section aria-label="api-health">
      <p>
        Status: <strong>{health.status}</strong>
      </p>
      <p>Version: {health.version}</p>
      <p>Git SHA: {health.git_sha}</p>
      <ul>
        {Object.entries(health.checks).map(([name, status]) => (
          <li key={name}>
            {name}: {status}
          </li>
        ))}
      </ul>
    </section>
  );
}
