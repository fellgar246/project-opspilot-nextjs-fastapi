"use client";

import { Suspense } from "react";

import { AuthGuard } from "@/features/auth/AuthGuard";
import { ApprovalCenter } from "@/features/approvals/ApprovalCenter";

export default function ApprovalsPage() {
  return (
    <Suspense fallback={<p>Loading…</p>}>
      <AuthGuard>
        <main className="container">
          <ApprovalCenter />
        </main>
      </AuthGuard>
    </Suspense>
  );
}
