"use client";

import { KeyRound, Plus, UserPlus } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import * as React from "react";

import { usePageMeta } from "@/components/layout/page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogFooter } from "@/components/ui/dialog";
import { Alert, EmptyState, ErrorState, LoadingState } from "@/components/ui/feedback";
import { Field, Input, Select } from "@/components/ui/input";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { api, getStoredUser } from "@/lib/api";
import {
  keys,
  useCandidates,
  useFaculty,
  useProvisionAccounts,
  useUsers,
} from "@/lib/queries";
import type { ProvisionedAccount, User, UserRole } from "@/lib/types";
import { formatDate } from "@/lib/utils";

const ROLES: UserRole[] = ["ADMIN", "COORDINATOR", "FACULTY", "STUDENT", "VIEWER"];

type FormState = {
  email: string;
  full_name: string;
  password: string;
  role: UserRole;
  faculty_id: string;
  candidate_id: string;
};

const EMPTY: FormState = {
  email: "",
  full_name: "",
  password: "",
  role: "COORDINATOR",
  faculty_id: "",
  candidate_id: "",
};

/**
 * Account administration. Two ways in, as agreed: bulk-provision logins from the
 * people already imported, or add one by hand. Generated passwords are shown
 * once - they are hashed on save and cannot be read back.
 */
export default function UsersPage() {
  const { notify } = useToast();
  const client = useQueryClient();
  const { data: users, isLoading, error } = useUsers();
  const { data: faculty } = useFaculty({});
  const { data: candidates } = useCandidates({});
  const provision = useProvisionAccounts();
  const currentUserId = getStoredUser<User>()?.id;

  const [open, setOpen] = React.useState(false);
  const [form, setForm] = React.useState<FormState>(EMPTY);
  const [formError, setFormError] = React.useState<string | null>(null);
  const [issued, setIssued] = React.useState<ProvisionedAccount[]>([]);

  const save = useMutation({
    mutationFn: (payload: FormState) =>
      api.post<User>("/auth/users", {
        email: payload.email,
        full_name: payload.full_name,
        password: payload.password,
        role: payload.role,
        faculty_id: payload.faculty_id ? Number(payload.faculty_id) : null,
        candidate_id: payload.candidate_id ? Number(payload.candidate_id) : null,
        must_change_password: true,
      }),
    onSuccess: () => {
      notify("Account created.");
      setOpen(false);
      setForm(EMPTY);
      client.invalidateQueries({ queryKey: keys.users });
    },
    onError: (err: Error) => setFormError(err.message),
  });

  const resetPassword = useMutation({
    mutationFn: (id: number) =>
      api.post<{ user: User; temporary_password: string }>(
        `/auth/users/${id}/reset-password`,
        {},
      ),
    onSuccess: (result) => {
      setIssued([
        {
          email: result.user.email,
          full_name: result.user.full_name,
          role: result.user.role,
          temporary_password: result.temporary_password,
        },
      ]);
      client.invalidateQueries({ queryKey: keys.users });
    },
    onError: (err: Error) => notify(err.message, "error"),
  });

  usePageMeta(
    "User accounts",
    "Logins and what each role may reach",
    <div className="flex gap-2">
      <Button
        size="sm"
        variant="secondary"
        onClick={() =>
          provision.mutate(
            { faculty: true, candidates: true },
            {
              onSuccess: (result) => {
                setIssued(result.accounts);
                notify(
                  `${result.created} account(s) created, ${result.skipped} skipped.`,
                );
              },
              onError: (err: Error) => notify(err.message, "error"),
            },
          )
        }
        disabled={provision.isPending}
      >
        <UserPlus className="h-3.5 w-3.5" />
        {provision.isPending ? "Provisioning..." : "Provision from imported data"}
      </Button>
      <Button
        size="sm"
        onClick={() => {
          setForm(EMPTY);
          setFormError(null);
          setOpen(true);
        }}
      >
        <Plus className="h-3.5 w-3.5" /> Add user
      </Button>
    </div>,
  );

  if (error) return <ErrorState error={error} />;

  return (
    <div className="grid gap-4">
      {issued.length ? (
        <Card>
          <CardHeader>
            <CardTitle>One-time passwords</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3">
            <Alert tone="warning">
              Copy these now - they are hashed on save and cannot be shown again.
              Everyone listed must change their password at first sign-in.
            </Alert>
            <Table>
              <THead>
                <TR>
                  <TH>Email</TH>
                  <TH>Name</TH>
                  <TH>Role</TH>
                  <TH>Temporary password</TH>
                </TR>
              </THead>
              <TBody>
                {issued.map((account) => (
                  <TR key={account.email}>
                    <TD className="font-medium text-slate-900">{account.email}</TD>
                    <TD>{account.full_name}</TD>
                    <TD>
                      <Badge tone="brand">{account.role}</Badge>
                    </TD>
                    <TD className="font-mono text-xs">{account.temporary_password}</TD>
                  </TR>
                ))}
              </TBody>
            </Table>
            <div>
              <Button size="sm" variant="ghost" onClick={() => setIssued([])}>
                Dismiss
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Accounts</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <LoadingState />
          ) : !users?.length ? (
            <EmptyState title="No accounts yet" description="Add one to get started." />
          ) : (
            <Table>
              <THead>
                <TR>
                  <TH>Email</TH>
                  <TH>Name</TH>
                  <TH>Role</TH>
                  <TH>Linked to</TH>
                  <TH>Status</TH>
                  <TH>Password</TH>
                  <TH className="text-right">Actions</TH>
                </TR>
              </THead>
              <TBody>
                {users.map((user) => (
                  <TR key={user.id}>
                    <TD className="font-medium text-slate-900">{user.email}</TD>
                    <TD>{user.full_name}</TD>
                    <TD>
                      <Badge tone={user.role === "ADMIN" ? "brand" : "neutral"}>
                        {user.role}
                      </Badge>
                    </TD>
                    <TD className="text-xs text-slate-500">
                      {user.faculty_id
                        ? `Faculty #${user.faculty_id}`
                        : user.candidate_id
                          ? `Candidate #${user.candidate_id}`
                          : "-"}
                    </TD>
                    <TD>
                      <Badge tone={user.is_active ? "success" : "neutral"}>
                        {user.is_active ? "Active" : "Disabled"}
                      </Badge>
                    </TD>
                    <TD>
                      <PasswordStatus user={user} />
                    </TD>
                    <TD className="text-right">
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => resetPassword.mutate(user.id)}
                        disabled={resetPassword.isPending || user.id === currentUserId}
                        title={
                          user.id === currentUserId
                            ? "Use change password for your own account"
                            : undefined
                        }
                      >
                        <KeyRound className="h-3.5 w-3.5" /> Reset password
                      </Button>
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent
          title="Add a user"
          description="Faculty and student accounts must be linked to a person."
        >
          <form
            onSubmit={(event) => {
              event.preventDefault();
              save.mutate(form);
            }}
          >
            {formError ? (
              <Alert tone="danger" className="mb-3">
                {formError}
              </Alert>
            ) : null}
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Email">
                <Input
                  type="email"
                  required
                  value={form.email}
                  onChange={(event) =>
                    setForm((state) => ({ ...state, email: event.target.value }))
                  }
                />
              </Field>
              <Field label="Full name">
                <Input
                  required
                  value={form.full_name}
                  onChange={(event) =>
                    setForm((state) => ({ ...state, full_name: event.target.value }))
                  }
                />
              </Field>
              <Field label="Temporary password">
                <Input
                  required
                  minLength={6}
                  value={form.password}
                  onChange={(event) =>
                    setForm((state) => ({ ...state, password: event.target.value }))
                  }
                />
              </Field>
              <Field label="Role">
                <Select
                  value={form.role}
                  onChange={(event) =>
                    setForm((state) => ({
                      ...state,
                      role: event.target.value as UserRole,
                      faculty_id: "",
                      candidate_id: "",
                    }))
                  }
                >
                  {ROLES.map((role) => (
                    <option key={role} value={role}>
                      {role}
                    </option>
                  ))}
                </Select>
              </Field>
              {form.role === "FACULTY" ? (
                <Field label="Faculty member" className="sm:col-span-2">
                  <Select
                    required
                    value={form.faculty_id}
                    onChange={(event) =>
                      setForm((state) => ({ ...state, faculty_id: event.target.value }))
                    }
                  >
                    <option value="">Select a faculty member</option>
                    {(faculty ?? []).map((member) => (
                      <option key={member.id} value={member.id}>
                        {member.faculty_code} - {member.faculty_name}
                      </option>
                    ))}
                  </Select>
                </Field>
              ) : null}
              {form.role === "STUDENT" ? (
                <Field label="Candidate" className="sm:col-span-2">
                  <Select
                    required
                    value={form.candidate_id}
                    onChange={(event) =>
                      setForm((state) => ({ ...state, candidate_id: event.target.value }))
                    }
                  >
                    <option value="">Select a candidate</option>
                    {(candidates ?? []).map((candidate) => (
                      <option key={candidate.id} value={candidate.id}>
                        {candidate.candidate_code} - {candidate.candidate_name}
                      </option>
                    ))}
                  </Select>
                </Field>
              ) : null}
            </div>
            <DialogFooter>
              <Button type="button" variant="secondary" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={save.isPending}>
                {save.isPending ? "Creating..." : "Create account"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

/**
 * What can honestly be said about a password.
 *
 * A password the user chose is a bcrypt hash - there is nothing to display and
 * that is the point. So this reports provenance instead: whether the account is
 * still holding the temporary password we issued (in which case re-issuing and
 * reading the new one is the way to help them), or the person has since set
 * their own, which nobody else can see.
 */
function PasswordStatus({ user }: { user: User }) {
  if (user.must_change_password) {
    return (
      <div className="leading-tight">
        <Badge tone="warning">Temporary</Badge>
        <p className="mt-0.5 text-[10px] text-slate-400">
          {user.password_issued_at
            ? `Issued ${formatDate(user.password_issued_at)}, not yet changed`
            : "Not yet changed"}
        </p>
      </div>
    );
  }
  return (
    <div className="leading-tight">
      <Badge tone="success">Set by user</Badge>
      <p className="mt-0.5 text-[10px] text-slate-400">
        {user.password_changed_at
          ? `Changed ${formatDate(user.password_changed_at)}`
          : "Never shown to anyone"}
      </p>
    </div>
  );
}
