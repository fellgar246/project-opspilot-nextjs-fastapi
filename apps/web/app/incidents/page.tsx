import { AuthGuard } from "@/features/auth/AuthGuard";
import { IncidentList } from "@/features/incidents/list/IncidentList";

export default function IncidentsPage() {
  return (
    <AuthGuard>
      <main className="container wide">
        <IncidentList />
      </main>
    </AuthGuard>
  );
}
