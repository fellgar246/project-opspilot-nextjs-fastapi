import { AuthGuard } from "@/features/auth/AuthGuard";
import { IncidentDetail } from "@/features/incidents/detail/IncidentDetail";

type IncidentDetailPageProps = {
  params: Promise<{ id: string }>;
};

export default async function IncidentDetailPage({ params }: IncidentDetailPageProps) {
  const { id } = await params;
  return (
    <AuthGuard>
      <main className="container wide">
        <IncidentDetail incidentId={id} />
      </main>
    </AuthGuard>
  );
}
