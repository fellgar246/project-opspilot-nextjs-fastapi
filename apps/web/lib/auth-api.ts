import { getApiBaseUrl } from "@/lib/api";
import { fetchWithAuth } from "@/lib/api-client";
import { formatApiDetail } from "@/lib/api-error";
import {
  AuthError,
  LoginResponse,
  MeResponse,
  SessionExpiredError,
} from "@/features/auth/types";

export { AuthError, SessionExpiredError };

export async function login(
  apiBaseUrl: string,
  email: string,
  password: string,
): Promise<LoginResponse> {
  const response = await fetch(`${apiBaseUrl}/api/v1/auth/login`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => ({ detail: "Request failed" }))) as {
      detail?: unknown;
    };
    throw new AuthError(formatApiDetail(payload.detail), response.status);
  }
  return (await response.json()) as LoginResponse;
}

export async function fetchMe(apiBaseUrl: string): Promise<MeResponse> {
  return fetchWithAuth<MeResponse>(apiBaseUrl, "/api/v1/auth/me");
}

export async function logout(apiBaseUrl: string): Promise<void> {
  await fetchWithAuth(apiBaseUrl, "/api/v1/auth/logout", { method: "POST" });
}

export function getDefaultApiBaseUrl(): string {
  return getApiBaseUrl();
}

export { fetchWithAuth };
