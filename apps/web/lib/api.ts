export type HealthCheckStatus = "ok" | "fail";

export type HealthResponse = {
  status: "ok" | "degraded";
  version: string;
  git_sha: string;
  checks: Record<string, HealthCheckStatus>;
};

export async function fetchHealth(apiBaseUrl: string): Promise<HealthResponse> {
  const response = await fetch(`${apiBaseUrl}/health`, { cache: "no-store" });
  if (!response.ok && response.status !== 503) {
    throw new Error(`Health request failed with status ${response.status}`);
  }
  return (await response.json()) as HealthResponse;
}

export function getApiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
}
