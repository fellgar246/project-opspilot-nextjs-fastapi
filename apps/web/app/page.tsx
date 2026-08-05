import { HealthStatus } from "@/components/HealthStatus";

export default function HomePage() {
  return (
    <main className="container">
      <h1>OpsPilot AI</h1>
      <p>Foundation stack — API health</p>
      <HealthStatus />
    </main>
  );
}
