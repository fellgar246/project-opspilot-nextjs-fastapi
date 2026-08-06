"use client";

import Link from "next/link";
import { Suspense } from "react";

import { AuthGuard } from "@/features/auth/AuthGuard";
import { useAuth } from "@/features/auth/AuthProvider";
import { HealthStatus } from "@/components/HealthStatus";

function DashboardContent() {
  const { user, logout, can } = useAuth();

  return (
    <main className="container">
      <header className="dashboard-header">
        <div>
          <h1>Dashboard</h1>
          <p>
            Signed in as {user?.display_name} ({user?.role})
          </p>
        </div>
        <button type="button" onClick={() => void logout()}>
          Sign out
        </button>
      </header>

      <section aria-label="role-capabilities">
        <h2>Your capabilities</h2>
        <ul>
          <li>Read incidents: {can("read_incidents") ? "yes" : "hidden"}</li>
          <li>Propose mitigation: {can("propose_mitigation") ? "yes" : "hidden"}</li>
          <li>Approve actions: {can("approve_action") ? "yes" : "hidden"}</li>
          <li>Read audit log: {can("read_audit") ? "yes" : "hidden"}</li>
          <li>Run evaluations: {can("run_evaluations") ? "yes" : "hidden"}</li>
          <li>Manage users: {can("manage_users") ? "yes" : "hidden"}</li>
        </ul>
      </section>

      {can("read_incidents") ? (
        <p>
          <Link href="/incidents">View incidents</Link>
          {can("approve_action") ? (
            <>
              {" "}
              · <Link href="/approvals">Approval Center</Link>
            </>
          ) : null}
          {can("run_evaluations") ? (
            <>
              {" "}
              · <Link href="/evaluations">Evaluation Lab</Link>
            </>
          ) : null}
        </p>
      ) : null}

      <HealthStatus />
    </main>
  );
}

export default function DashboardPage() {
  return (
    <Suspense fallback={<p>Loading…</p>}>
      <AuthGuard>
        <DashboardContent />
      </AuthGuard>
    </Suspense>
  );
}
