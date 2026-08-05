"use client";

import { Suspense } from "react";

import { LoginForm } from "@/features/auth/LoginForm";

export default function LoginPage() {
  return (
    <main className="container">
      <Suspense fallback={<p>Loading…</p>}>
        <LoginForm />
      </Suspense>
    </main>
  );
}
