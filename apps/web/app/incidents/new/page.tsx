import { Suspense } from "react";

import { AuthGuard } from "@/features/auth/AuthGuard";
import { CreateIncidentForm } from "@/features/incidents/create/CreateIncidentForm";

export default function NewIncidentPage() {
  return (
    <Suspense fallback={<p>Loading…</p>}>
      <AuthGuard>
        <main className="container wide">
          <CreateIncidentForm />
        </main>
      </AuthGuard>
    </Suspense>
  );
}
