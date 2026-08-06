"use client";

import { Suspense } from "react";

import { AuthGuard } from "@/features/auth/AuthGuard";
import { EvaluationLab } from "@/features/evaluations/EvaluationLab";

export default function EvaluationsPage() {
  return (
    <Suspense fallback={<p>Loading…</p>}>
      <AuthGuard>
        <main className="container">
          <EvaluationLab />
        </main>
      </AuthGuard>
    </Suspense>
  );
}
