"use client";

import { useRouter, usePathname, useSearchParams } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/features/auth/AuthProvider";

type AuthGuardProps = {
  children: React.ReactNode;
};

export function AuthGuard({ children }: AuthGuardProps) {
  const { user, loading, sessionExpired } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  useEffect(() => {
    if (loading || user) {
      return;
    }
    const query = searchParams.toString();
    const next = query ? `${pathname}?${query}` : pathname;
    const loginUrl = sessionExpired
      ? `/login?expired=1&next=${encodeURIComponent(next)}`
      : `/login?next=${encodeURIComponent(next)}`;
    router.replace(loginUrl);
  }, [loading, user, router, pathname, searchParams, sessionExpired]);

  if (loading) {
    return <p>Loading session…</p>;
  }

  if (!user) {
    return <p>Redirecting to sign in…</p>;
  }

  return <>{children}</>;
}
