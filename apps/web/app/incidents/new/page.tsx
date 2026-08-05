import { AuthGuard } from "@/features/auth/AuthGuard";
import { CreateIncidentForm } from "@/features/incidents/create/CreateIncidentForm";

export default function NewIncidentPage() {
  return (
    <AuthGuard>
      <main className="container wide">
        <CreateIncidentForm />
      </main>
    </AuthGuard>
  );
}
