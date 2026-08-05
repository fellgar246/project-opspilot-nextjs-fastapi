"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import type { Capability } from "@/features/auth/permissions";
import { roleHasCapability } from "@/features/auth/permissions";
import type { MeResponse } from "@/features/auth/types";
import { SessionExpiredError } from "@/features/auth/types";
import { fetchMe, getDefaultApiBaseUrl, login as loginRequest, logout as logoutRequest } from "@/lib/auth-api";

type AuthContextValue = {
  user: MeResponse | null;
  loading: boolean;
  sessionExpired: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
  can: (capability: Capability) => boolean;
};

const AuthContext = createContext<AuthContextValue | null>(null);

type AuthProviderProps = {
  children: React.ReactNode;
  apiBaseUrl?: string;
};

export function AuthProvider({ children, apiBaseUrl = getDefaultApiBaseUrl() }: AuthProviderProps) {
  const [user, setUser] = useState<MeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [sessionExpired, setSessionExpired] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const me = await fetchMe(apiBaseUrl);
      setUser(me);
      setSessionExpired(false);
    } catch (error) {
      setUser(null);
      if (error instanceof SessionExpiredError) {
        setSessionExpired(true);
      }
    } finally {
      setLoading(false);
    }
  }, [apiBaseUrl]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const login = useCallback(
    async (email: string, password: string) => {
      const response = await loginRequest(apiBaseUrl, email, password);
      setUser(response.user);
      setSessionExpired(false);
    },
    [apiBaseUrl],
  );

  const logout = useCallback(async () => {
    await logoutRequest(apiBaseUrl);
    setUser(null);
    setSessionExpired(false);
  }, [apiBaseUrl]);

  const can = useCallback(
    (capability: Capability) => {
      if (!user) {
        return false;
      }
      return roleHasCapability(user.role, capability);
    },
    [user],
  );

  const value = useMemo(
    () => ({ user, loading, sessionExpired, login, logout, refresh, can }),
    [user, loading, sessionExpired, login, logout, refresh, can],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
