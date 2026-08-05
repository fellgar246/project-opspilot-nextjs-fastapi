import { getApiBaseUrl } from "@/lib/api";
import {
  AuthError,
  LoginResponse,
  MeResponse,
  SessionExpiredError,
} from "@/features/auth/types";

type ApiFetchOptions = RequestInit & {
  retryOnUnauthorized?: boolean;
};

let refreshPromise: Promise<void> | null = null;

async function parseDetail(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string };
    return payload.detail ?? "Request failed";
  } catch {
    return "Request failed";
  }
}

async function refreshSession(apiBaseUrl: string): Promise<void> {
  const response = await fetch(`${apiBaseUrl}/api/v1/auth/refresh`, {
    method: "POST",
    credentials: "include",
  });
  if (!response.ok) {
    throw new SessionExpiredError(await parseDetail(response));
  }
}

async function fetchWithAuth(apiBaseUrl: string, path: string, options: ApiFetchOptions = {}) {
  const { retryOnUnauthorized = true, ...init } = options;
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
  });

  if (response.status === 401 && retryOnUnauthorized) {
    if (!refreshPromise) {
      refreshPromise = refreshSession(apiBaseUrl).finally(() => {
        refreshPromise = null;
      });
    }
    try {
      await refreshPromise;
    } catch (error) {
      throw error instanceof SessionExpiredError ? error : new SessionExpiredError();
    }
    return fetchWithAuth(apiBaseUrl, path, { ...options, retryOnUnauthorized: false });
  }

  if (!response.ok) {
    throw new AuthError(await parseDetail(response), response.status);
  }

  if (response.status === 204) {
    return null;
  }

  return response.json();
}

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
    throw new AuthError(await parseDetail(response), response.status);
  }
  return (await response.json()) as LoginResponse;
}

export async function fetchMe(apiBaseUrl: string): Promise<MeResponse> {
  return (await fetchWithAuth(apiBaseUrl, "/api/v1/auth/me")) as MeResponse;
}

export async function logout(apiBaseUrl: string): Promise<void> {
  await fetchWithAuth(apiBaseUrl, "/api/v1/auth/logout", { method: "POST" });
}

export function getDefaultApiBaseUrl(): string {
  return getApiBaseUrl();
}
