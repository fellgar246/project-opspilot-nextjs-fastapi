"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { useAuth } from "@/features/auth/AuthProvider";
import { AuthError } from "@/features/auth/types";

const loginSchema = z.object({
  email: z.string().email("Enter a valid email"),
  password: z.string().min(1, "Password is required"),
});

type LoginFormValues = z.infer<typeof loginSchema>;

export function LoginForm() {
  const { login } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      await login(values.email, values.password);
      const next = searchParams.get("next") ?? "/dashboard";
      router.replace(next);
    } catch (error) {
      if (error instanceof AuthError) {
        setFormError(error.message);
        return;
      }
      setFormError("Unable to sign in. Try again.");
    }
  });

  return (
    <form className="auth-form" onSubmit={onSubmit}>
      <h1>Sign in</h1>
      {searchParams.get("expired") === "1" ? (
        <p role="status">Your session expired. Please sign in again.</p>
      ) : null}
      {formError ? <p role="alert">{formError}</p> : null}
      <label>
        Email
        <input type="email" autoComplete="email" {...register("email")} />
        {errors.email ? <span role="alert">{errors.email.message}</span> : null}
      </label>
      <label>
        Password
        <input type="password" autoComplete="current-password" {...register("password")} />
        {errors.password ? <span role="alert">{errors.password.message}</span> : null}
      </label>
      <button type="submit" disabled={isSubmitting}>
        {isSubmitting ? "Signing in…" : "Sign in"}
      </button>
    </form>
  );
}
