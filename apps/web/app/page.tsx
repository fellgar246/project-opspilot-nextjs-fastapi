import Link from "next/link";

import { HealthStatus } from "@/components/HealthStatus";

export default function HomePage() {
  return (
    <main className="container">
      <h1>OpsPilot AI</h1>
      <p>Foundation stack — API health</p>
      <p>
        <Link href="/login">Sign in</Link> · <Link href="/dashboard">Dashboard</Link>
      </p>
      <HealthStatus />
    </main>
  );
}
