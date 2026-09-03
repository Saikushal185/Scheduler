"use client";

import { CalendarClock } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import * as React from "react";

import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/feedback";
import { Field, Input } from "@/components/ui/input";
import { homeFor } from "@/lib/access";
import { ApiError, api, setSession } from "@/lib/api";
import type { LoginResponse } from "@/lib/types";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = React.useState("admin@example.com");
  const [password, setPassword] = React.useState("admin123");
  const [error, setError] = React.useState<string | null>(null);
  const [pending, setPending] = React.useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      const result = await api.post<LoginResponse>("/auth/login", { email, password });
      setSession(result.access_token, result.user);
      if (result.user.must_change_password) {
        // Signed in with a password somebody else chose and could still read.
        router.push("/change-password");
        return;
      }
      // Each role has a different landing page - a student has no dashboard.
      router.push(homeFor(result.user.role));
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Could not reach the API. Is the backend running on port 8000?",
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-[var(--color-background)] px-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center gap-2 text-center">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-[var(--color-brand)] text-white">
            <CalendarClock className="h-5 w-5" />
          </div>
          <h1 className="text-lg font-semibold text-slate-900">
            Interview Scheduling &amp; Evaluation
          </h1>
          <p className="text-xs text-slate-500">
            Sign in to manage schedules, panels and evaluations.
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="rounded-xl border border-[var(--color-border)] bg-white p-6 shadow-sm"
        >
          {error ? (
            <Alert tone="danger" className="mb-4">
              {error}
            </Alert>
          ) : null}

          <Field label="Email" className="mb-3">
            <Input
              type="email"
              value={email}
              autoComplete="username"
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </Field>
          <Field label="Password" className="mb-5">
            <Input
              type="password"
              value={password}
              autoComplete="current-password"
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </Field>

          <Button type="submit" className="w-full" disabled={pending}>
            {pending ? "Signing in..." : "Sign in"}
          </Button>

          <p className="mt-4 text-center text-[11px] text-slate-500">
            First time here?{" "}
            <Link href="/claim" className="font-medium text-[var(--color-brand)]">
              Set up your account
            </Link>
          </p>

          <p className="mt-3 text-center text-[11px] text-slate-400">
            Seeded administrator: admin@example.com / admin123
          </p>
        </form>
      </div>
    </main>
  );
}
