"use client";

import { KeyRound } from "lucide-react";
import { useRouter } from "next/navigation";
import * as React from "react";

import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/feedback";
import { Field, Input } from "@/components/ui/input";
import { homeFor } from "@/lib/access";
import { ApiError, api, getStoredUser, getToken, setSession } from "@/lib/api";
import type { User } from "@/lib/types";

/**
 * Change your own password.
 *
 * Doubles as the first-login screen: an account created by an admin or by bulk
 * provisioning holds a temporary password that was shown to somebody else, so
 * the app layout sends those users here and keeps them here until they have set
 * their own. Reached voluntarily the rest of the time.
 */
export default function ChangePasswordPage() {
  const router = useRouter();
  const [user, setUser] = React.useState<User | null>(null);
  const [form, setForm] = React.useState({
    current_password: "",
    new_password: "",
    confirm_password: "",
  });
  const [error, setError] = React.useState<string | null>(null);
  const [pending, setPending] = React.useState(false);

  React.useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    setUser(getStoredUser<User>());
  }, [router]);

  const forced = Boolean(user?.must_change_password);
  const mismatch =
    form.confirm_password.length > 0 && form.new_password !== form.confirm_password;
  const sameAsOld =
    form.new_password.length > 0 && form.new_password === form.current_password;

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (mismatch || sameAsOld) return;
    setPending(true);
    setError(null);
    try {
      await api.post("/auth/change-password", {
        current_password: form.current_password,
        new_password: form.new_password,
      });
      // The stored user still carries the old flag; clear it so the layout
      // stops redirecting back here.
      if (user) {
        const updated = { ...user, must_change_password: false };
        setSession(getToken() as string, updated);
        setUser(updated);
      }
      router.replace(homeFor(user?.role));
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

  if (!user) return null;

  return (
    <main className="flex min-h-screen items-center justify-center bg-[var(--color-background)] px-4 py-10">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center gap-2 text-center">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-[var(--color-brand)] text-white">
            <KeyRound className="h-5 w-5" />
          </div>
          <h1 className="text-lg font-semibold text-slate-900">
            {forced ? "Choose your password" : "Change your password"}
          </h1>
          <p className="text-xs text-slate-500">Signed in as {user.email}</p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="rounded-xl border border-[var(--color-border)] bg-white p-6 shadow-sm"
        >
          {forced ? (
            <Alert tone="warning" className="mb-4">
              You are signed in with a temporary password that was issued to you.
              Please set your own before continuing.
            </Alert>
          ) : null}
          {error ? (
            <Alert tone="danger" className="mb-4">
              {error}
            </Alert>
          ) : null}

          <Field
            label={forced ? "Temporary password" : "Current password"}
            className="mb-3"
          >
            <Input
              type="password"
              required
              autoFocus
              autoComplete="current-password"
              value={form.current_password}
              onChange={(event) =>
                setForm((state) => ({ ...state, current_password: event.target.value }))
              }
            />
          </Field>

          <Field label="New password" hint="At least 6 characters" className="mb-3">
            <Input
              type="password"
              required
              minLength={6}
              autoComplete="new-password"
              value={form.new_password}
              aria-invalid={sameAsOld}
              onChange={(event) =>
                setForm((state) => ({ ...state, new_password: event.target.value }))
              }
            />
            {sameAsOld ? (
              <p className="mt-1 text-[11px] text-[var(--color-danger)]">
                Choose something different from your current password.
              </p>
            ) : null}
          </Field>

          <Field label="Confirm new password" className="mb-4">
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

          <Button
            type="submit"
            className="w-full"
            disabled={pending || mismatch || sameAsOld}
          >
            {pending ? "Saving..." : "Save password"}
          </Button>

          {!forced ? (
            <Button
              type="button"
              variant="ghost"
              className="mt-2 w-full"
              onClick={() => router.back()}
            >
              Cancel
            </Button>
          ) : null}
        </form>
      </div>
    </main>
  );
}
