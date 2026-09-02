"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Search, Trash2 } from "lucide-react";
import * as React from "react";

import { usePageMeta } from "@/components/layout/page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogContent, DialogFooter } from "@/components/ui/dialog";
import { Alert, ErrorState, LoadingState } from "@/components/ui/feedback";
import { Field, Input, Select } from "@/components/ui/input";
import { EmptyRow, TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { useDepartments, useFaculty, usePanels } from "@/lib/queries";
import type { Faculty } from "@/lib/types";

type FormState = {
  faculty_code: string;
  faculty_name: string;
  email: string;
  phone: string;
  department: string;
  designation: string;
  max_interviews_per_day: string;
};

const EMPTY: FormState = {
  faculty_code: "",
  faculty_name: "",
  email: "",
  phone: "",
  department: "",
  designation: "",
  max_interviews_per_day: "",
};

export default function FacultyPage() {
  const [search, setSearch] = React.useState("");
  const [department, setDepartment] = React.useState("");
  const [open, setOpen] = React.useState(false);
  const [editing, setEditing] = React.useState<Faculty | null>(null);
  const [form, setForm] = React.useState<FormState>(EMPTY);
  const [error, setError] = React.useState<string | null>(null);

  const { notify } = useToast();
  const client = useQueryClient();
  const { data: departments } = useDepartments();
  const { data: panels } = usePanels();
  const { data, isLoading, error: loadError } = useFaculty({
    q: search || undefined,
    department: department || undefined,
  });

  usePageMeta(
    "Faculty",
    "Interviewers, their departments and daily interview limits",
    <Button
      size="sm"
      onClick={() => {
        setEditing(null);
        setForm(EMPTY);
        setError(null);
        setOpen(true);
      }}
    >
      <Plus className="h-3.5 w-3.5" /> Add faculty
    </Button>,
  );

  const panelsByFaculty = React.useMemo(() => {
    const map = new Map<number, string[]>();
    (panels ?? []).forEach((panel) => {
      panel.members.forEach((member) => {
        map.set(member.faculty_id, [...(map.get(member.faculty_id) ?? []), panel.panel_code]);
      });
    });
    return map;
  }, [panels]);

  const save = useMutation({
    mutationFn: async (payload: FormState) => {
      const body: Record<string, unknown> = {
        faculty_name: payload.faculty_name,
        email: payload.email || null,
        phone: payload.phone || null,
        department: payload.department || null,
        designation: payload.designation || null,
        max_interviews_per_day: payload.max_interviews_per_day
          ? Number(payload.max_interviews_per_day)
          : null,
      };
      if (editing) return api.put<Faculty>(`/faculty/${editing.id}`, body);
      return api.post<Faculty>("/faculty", {
        ...body,
        faculty_code: payload.faculty_code,
      });
    },
    onSuccess: () => {
      notify(editing ? "Faculty updated." : "Faculty created.");
      setOpen(false);
      client.invalidateQueries();
    },
    onError: (err: Error) => setError(err.message),
  });

  const remove = useMutation({
    mutationFn: (member: Faculty) => api.delete(`/faculty/${member.id}`),
    onSuccess: () => {
      notify("Faculty deleted.");
      client.invalidateQueries();
    },
    onError: (err: Error) => notify(err.message, "error"),
  });

  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="flex flex-wrap items-end gap-3 pt-5">
          <div className="min-w-[220px] flex-1">
            <Field label="Search">
              <div className="relative">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-slate-400" />
                <Input
                  className="pl-8"
                  placeholder="Name, code or email"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                />
              </div>
            </Field>
          </div>
          <Field label="Department" className="w-52">
            <Select value={department} onChange={(event) => setDepartment(event.target.value)}>
              <option value="">All departments</option>
              {(departments ?? []).map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </Select>
          </Field>
          <p className="ml-auto text-xs text-slate-500">{data?.length ?? 0} faculty</p>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="px-0 pb-0 pt-2">
          {isLoading ? (
            <LoadingState />
          ) : loadError ? (
            <ErrorState error={loadError} />
          ) : (
            <Table>
              <THead>
                <TR>
                  <TH>Faculty</TH>
                  <TH>Department</TH>
                  <TH>Designation</TH>
                  <TH>Daily limit</TH>
                  <TH>Panels</TH>
                  <TH className="text-right">Actions</TH>
                </TR>
              </THead>
              <TBody>
                {data?.length ? (
                  data.map((member) => (
                    <TR key={member.id}>
                      <TD>
                        <p className="font-medium text-slate-800">{member.faculty_name}</p>
                        <p className="text-[11px] text-slate-400">
                          {member.faculty_code}
                          {member.email ? ` · ${member.email}` : ""}
                        </p>
                      </TD>
                      <TD>{member.department ?? "-"}</TD>
                      <TD>{member.designation ?? "-"}</TD>
                      <TD>{member.max_interviews_per_day ?? "Default"}</TD>
                      <TD>
                        <div className="flex flex-wrap gap-1">
                          {(panelsByFaculty.get(member.id) ?? []).map((code) => (
                            <Badge key={code} tone="brand">
                              {code}
                            </Badge>
                          ))}
                          {!panelsByFaculty.get(member.id)?.length ? (
                            <span className="text-[11px] text-slate-400">No panel</span>
                          ) : null}
                        </div>
                      </TD>
                      <TD className="text-right">
                        <div className="flex justify-end gap-1">
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => {
                              setEditing(member);
                              setError(null);
                              setForm({
                                faculty_code: member.faculty_code,
                                faculty_name: member.faculty_name,
                                email: member.email ?? "",
                                phone: member.phone ?? "",
                                department: member.department ?? "",
                                designation: member.designation ?? "",
                                max_interviews_per_day: member.max_interviews_per_day
                                  ? String(member.max_interviews_per_day)
                                  : "",
                              });
                              setOpen(true);
                            }}
                          >
                            <Pencil className="h-3.5 w-3.5" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => {
                              if (
                                window.confirm(
                                  `Delete ${member.faculty_name}? Their availability and panel memberships are removed too.`,
                                )
                              ) {
                                remove.mutate(member);
                              }
                            }}
                          >
                            <Trash2 className="h-3.5 w-3.5 text-[var(--color-danger)]" />
                          </Button>
                        </div>
                      </TD>
                    </TR>
                  ))
                ) : (
                  <EmptyRow colSpan={6} message="No faculty yet - import the Faculty sheet." />
                )}
              </TBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent title={editing ? `Edit ${editing.faculty_name}` : "Add faculty"}>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              save.mutate(form);
            }}
          >
            {error ? (
              <Alert tone="danger" className="mb-3">
                {error}
              </Alert>
            ) : null}
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Faculty code">
                <Input
                  required
                  disabled={Boolean(editing)}
                  value={form.faculty_code}
                  onChange={(event) => setForm({ ...form, faculty_code: event.target.value })}
                />
              </Field>
              <Field label="Name">
                <Input
                  required
                  value={form.faculty_name}
                  onChange={(event) => setForm({ ...form, faculty_name: event.target.value })}
                />
              </Field>
              <Field label="Email">
                <Input
                  type="email"
                  value={form.email}
                  onChange={(event) => setForm({ ...form, email: event.target.value })}
                />
              </Field>
              <Field label="Phone">
                <Input
                  value={form.phone}
                  onChange={(event) => setForm({ ...form, phone: event.target.value })}
                />
              </Field>
              <Field label="Department">
                <Input
                  value={form.department}
                  onChange={(event) => setForm({ ...form, department: event.target.value })}
                />
              </Field>
              <Field label="Designation">
                <Input
                  value={form.designation}
                  onChange={(event) => setForm({ ...form, designation: event.target.value })}
                />
              </Field>
              <Field
                label="Max interviews per day"
                hint="Leave blank to use the global limit"
              >
                <Input
                  type="number"
                  min={1}
                  max={50}
                  value={form.max_interviews_per_day}
                  onChange={(event) =>
                    setForm({ ...form, max_interviews_per_day: event.target.value })
                  }
                />
              </Field>
            </div>
            <DialogFooter>
              <Button type="button" variant="secondary" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={save.isPending}>
                {save.isPending ? "Saving..." : "Save faculty"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
