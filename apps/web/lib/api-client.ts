import { AuthError, SessionExpiredError } from "@/features/auth/types";

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

export async function fetchWithAuth<T = unknown>(
  apiBaseUrl: string,
  path: string,
  options: ApiFetchOptions = {},
): Promise<T> {
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
    return null as T;
  }

  return (await response.json()) as T;
}

export { AuthError, SessionExpiredError };
