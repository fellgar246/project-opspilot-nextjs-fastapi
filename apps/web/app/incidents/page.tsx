import { Suspense } from "react";

import { AuthGuard } from "@/features/auth/AuthGuard";
import { IncidentList } from "@/features/incidents/list/IncidentList";

export default function IncidentsPage() {
  return (
    <Suspense fallback={<p>Loading…</p>}>
      <AuthGuard>
        <main className="container wide">
          <IncidentList />
        </main>
      </AuthGuard>
    </Suspense>
  );
}
