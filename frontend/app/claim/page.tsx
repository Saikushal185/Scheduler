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

/**
 * Sign-up, restricted to people the institute already has on file.
 *
 * Open registration would create accounts with nothing behind them: every
 * permission scope is derived from a candidate or faculty record, so an
 * unlinked account could not be shown anything anyway. Matching a code against
 * the email already imported for that person ties the new login to a real
 * record and settles the role at the same time.
 */
export default function ClaimAccountPage() {
  const router = useRouter();
  const [form, setForm] = React.useState({
    code: "",
    email: "",
    password: "",
    confirm_password: "",
  });
  const [error, setError] = React.useState<string | null>(null);
  const [pending, setPending] = React.useState(false);

  const mismatch =
    form.confirm_password.length > 0 && form.password !== form.confirm_password;

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (mismatch) {
      setError("The two passwords do not match.");
      return;
    }
    setPending(true);
    setError(null);
    try {
      const result = await api.post<LoginResponse>("/auth/claim", form);
      // Claiming signs you straight in - there is nothing else to confirm.
      setSession(result.access_token, result.user);
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
    <main className="flex min-h-screen items-center justify-center bg-[var(--color-background)] px-4 py-10">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center gap-2 text-center">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-[var(--color-brand)] text-white">
            <CalendarClock className="h-5 w-5" />
          </div>
          <h1 className="text-lg font-semibold text-slate-900">Set up your account</h1>
          <p className="text-xs text-slate-500">
            Use the code and email your institute already holds for you.
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

          <Field
            label="Your code"
            hint="Candidate or faculty code, e.g. CAND009 or FAC003"
            className="mb-3"
          >
            <Input
              required
              autoFocus
              value={form.code}
              placeholder="CAND009"
              onChange={(event) =>
                setForm((state) => ({ ...state, code: event.target.value }))
              }
            />
          </Field>

          <Field label="Email" hint="Must match the email on your record" className="mb-3">
            <Input
              type="email"
              required
              autoComplete="username"
              value={form.email}
              onChange={(event) =>
                setForm((state) => ({ ...state, email: event.target.value }))
              }
            />
          </Field>

          <Field label="New password" hint="At least 6 characters" className="mb-3">
            <Input
              type="password"
              required
              minLength={6}
              autoComplete="new-password"
              value={form.password}
              onChange={(event) =>
                setForm((state) => ({ ...state, password: event.target.value }))
              }
            />
          </Field>

          <Field label="Confirm password" className="mb-4">
            <Input
              type="password"
              required
              minLength={6}
              autoComplete="new-password"
              value={form.confirm_password}
              aria-invalid={mismatch}
              onChange={(event) =>
                setForm((state) => ({ ...state, confirm_password: event.target.value }))
              }
            />
            {mismatch ? (
              <p className="mt-1 text-[11px] text-[var(--color-danger)]">
                The two passwords do not match.
              </p>
            ) : null}
          </Field>

          <Button type="submit" className="w-full" disabled={pending || mismatch}>
            {pending ? "Creating your account..." : "Create my account"}
          </Button>

          <p className="mt-4 text-center text-[11px] text-slate-500">
            Already have an account?{" "}
            <Link href="/login" className="font-medium text-[var(--color-brand)]">
              Sign in
            </Link>
          </p>
        </form>

        <p className="mt-4 text-center text-[11px] text-slate-400">
          Not on file yet? Ask your scheduling administrator to add you first.
        </p>
      </div>
    </main>
  );
}
