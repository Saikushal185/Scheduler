"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Search, Trash2 } from "lucide-react";
import * as React from "react";

import { usePageMeta } from "@/components/layout/page";
import { StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogContent, DialogFooter } from "@/components/ui/dialog";
import { Alert, ErrorState, LoadingState } from "@/components/ui/feedback";
import { Field, Input, Select } from "@/components/ui/input";
import { EmptyRow, TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { useCandidates, useDepartments, usePanels } from "@/lib/queries";
import type { Candidate } from "@/lib/types";
import { formatDate, formatTime } from "@/lib/utils";

const STATUSES = ["PENDING", "SCHEDULED", "UNSCHEDULED", "COMPLETED", "WITHDRAWN"];

type FormState = {
  candidate_code: string;
  candidate_name: string;
  email: string;
  phone: string;
  department: string;
  position: string;
  preferred_date: string;
  preferred_time: string;
  preferred_panel_code: string;
  priority: number;
  notes: string;
};

const EMPTY: FormState = {
  candidate_code: "",
  candidate_name: "",
  email: "",
  phone: "",
  department: "",
  position: "",
  preferred_date: "",
  preferred_time: "",
  preferred_panel_code: "",
  priority: 0,
  notes: "",
};

export default function CandidatesPage() {
  const [search, setSearch] = React.useState("");
  const [status, setStatus] = React.useState("");
  const [department, setDepartment] = React.useState("");
  const [editing, setEditing] = React.useState<Candidate | null>(null);
  const [open, setOpen] = React.useState(false);
  const [form, setForm] = React.useState<FormState>(EMPTY);
  const [error, setError] = React.useState<string | null>(null);

  const { notify } = useToast();
  const client = useQueryClient();
  const { data: departments } = useDepartments();
  const { data: panels } = usePanels();
  const { data, isLoading, error: loadError } = useCandidates({
    q: search || undefined,
    status: status || undefined,
    department: department || undefined,
  });

  usePageMeta(
    "Candidates",
    "Everyone waiting for an interview, with their preferences and constraints",
    <Button
      size="sm"
      onClick={() => {
        setEditing(null);
        setForm(EMPTY);
        setError(null);
        setOpen(true);
      }}
    >
      <Plus className="h-3.5 w-3.5" /> Add candidate
    </Button>,
  );

  const save = useMutation({
    mutationFn: async (payload: FormState) => {
      const body: Record<string, unknown> = {
        ...payload,
        email: payload.email || null,
        phone: payload.phone || null,
        department: payload.department || null,
        position: payload.position || null,
        preferred_date: payload.preferred_date || null,
        preferred_time: payload.preferred_time || null,
        preferred_panel_code: payload.preferred_panel_code || null,
        notes: payload.notes || null,
        priority: Number(payload.priority) || 0,
      };
      if (editing) {
        delete body.candidate_code;
        return api.put<Candidate>(`/candidates/${editing.id}`, body);
      }
      return api.post<Candidate>("/candidates", body);
    },
    onSuccess: () => {
      notify(editing ? "Candidate updated." : "Candidate created.");
      setOpen(false);
      client.invalidateQueries();
    },
    onError: (err: Error) => setError(err.message),
  });

  const remove = useMutation({
    mutationFn: (candidate: Candidate) => api.delete(`/candidates/${candidate.id}`),
    onSuccess: () => {
      notify("Candidate deleted.");
      client.invalidateQueries();
    },
    onError: (err: Error) => notify(err.message, "error"),
  });

  function edit(candidate: Candidate) {
    setEditing(candidate);
    setError(null);
    setForm({
      candidate_code: candidate.candidate_code,
      candidate_name: candidate.candidate_name,
      email: candidate.email ?? "",
      phone: candidate.phone ?? "",
      department: candidate.department ?? "",
      position: candidate.position ?? "",
      preferred_date: candidate.preferred_date ?? "",
      preferred_time: candidate.preferred_time?.slice(0, 5) ?? "",
      preferred_panel_code: candidate.preferred_panel_code ?? "",
      priority: candidate.priority,
      notes: candidate.notes ?? "",
    });
    setOpen(true);
  }

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
          <Field label="Status" className="w-40">
            <Select value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="">All statuses</option>
              {STATUSES.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Department" className="w-48">
            <Select
              value={department}
              onChange={(event) => setDepartment(event.target.value)}
            >
              <option value="">All departments</option>
              {(departments ?? []).map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </Select>
          </Field>
          <p className="ml-auto text-xs text-slate-500">{data?.length ?? 0} candidate(s)</p>
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
                  <TH>Candidate</TH>
                  <TH>Department</TH>
                  <TH>Preferred slot</TH>
                  <TH>Availability</TH>
                  <TH>Priority</TH>
                  <TH>Status</TH>
                  <TH className="text-right">Actions</TH>
                </TR>
              </THead>
              <TBody>
                {data?.length ? (
                  data.map((candidate) => (
                    <TR key={candidate.id}>
                      <TD>
                        <p className="font-medium text-slate-800">
                          {candidate.candidate_name}
                        </p>
                        <p className="text-[11px] text-slate-400">
                          {candidate.candidate_code}
                          {candidate.email ? ` · ${candidate.email}` : ""}
                        </p>
                      </TD>
                      <TD>{candidate.department ?? "-"}</TD>
                      <TD className="whitespace-nowrap">
                        {candidate.preferred_date
                          ? formatDate(candidate.preferred_date)
                          : "Any date"}
                        {candidate.preferred_time
                          ? ` · ${formatTime(candidate.preferred_time)}`
                          : ""}
                        {candidate.preferred_panel_code ? (
                          <p className="text-[11px] text-slate-400">
                            Panel {candidate.preferred_panel_code}
                          </p>
                        ) : null}
                      </TD>
                      <TD className="text-[11px] text-slate-500">
                        {candidate.availability.length
                          ? candidate.availability
                              .slice(0, 2)
                              .map(
                                (window) =>
                                  `${formatDate(window.date)} ${formatTime(window.start_time)}-${formatTime(window.end_time)}`,
                              )
                              .join(", ")
                          : "Flexible"}
                        {candidate.availability.length > 2
                          ? ` +${candidate.availability.length - 2}`
                          : ""}
                      </TD>
                      <TD>{candidate.priority}</TD>
                      <TD>
                        <StatusBadge status={candidate.status} />
                      </TD>
                      <TD className="text-right">
                        <div className="flex justify-end gap-1">
                          <Button variant="ghost" size="icon" onClick={() => edit(candidate)}>
                            <Pencil className="h-3.5 w-3.5" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => {
                              if (
                                window.confirm(
                                  `Delete ${candidate.candidate_name}? This also removes their interviews.`,
                                )
                              ) {
                                remove.mutate(candidate);
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
                  <EmptyRow
                    colSpan={7}
                    message="No candidates yet - upload a spreadsheet or add one manually."
                  />
                )}
              </TBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent
          title={editing ? `Edit ${editing.candidate_name}` : "Add candidate"}
          description="Preferences are treated as soft constraints by the scheduler."
        >
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
              <Field label="Candidate code">
                <Input
                  required
                  disabled={Boolean(editing)}
                  value={form.candidate_code}
                  onChange={(event) =>
                    setForm({ ...form, candidate_code: event.target.value })
                  }
                />
              </Field>
              <Field label="Name">
                <Input
                  required
                  value={form.candidate_name}
                  onChange={(event) =>
                    setForm({ ...form, candidate_name: event.target.value })
                  }
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
              <Field label="Position">
                <Input
                  value={form.position}
                  onChange={(event) => setForm({ ...form, position: event.target.value })}
                />
              </Field>
              <Field label="Preferred date" hint="High priority soft constraint">
                <Input
                  type="date"
                  value={form.preferred_date}
                  onChange={(event) =>
                    setForm({ ...form, preferred_date: event.target.value })
                  }
                />
              </Field>
              <Field label="Preferred time" hint="Medium priority soft constraint">
                <Input
                  type="time"
                  value={form.preferred_time}
                  onChange={(event) =>
                    setForm({ ...form, preferred_time: event.target.value })
                  }
                />
              </Field>
              <Field label="Preferred panel" hint="Low priority soft constraint">
                <Select
                  value={form.preferred_panel_code}
                  onChange={(event) =>
                    setForm({ ...form, preferred_panel_code: event.target.value })
                  }
                >
                  <option value="">No preference</option>
                  {(panels ?? []).map((panel) => (
                    <option key={panel.id} value={panel.panel_code}>
                      {panel.panel_code} · {panel.panel_name}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Priority" hint="Higher numbers are scheduled first">
                <Input
                  type="number"
                  min={0}
                  max={10}
                  value={form.priority}
                  onChange={(event) =>
                    setForm({ ...form, priority: Number(event.target.value) })
                  }
                />
              </Field>
            </div>
            <Field label="Notes" className="mt-3">
              <Input
                value={form.notes}
                onChange={(event) => setForm({ ...form, notes: event.target.value })}
              />
            </Field>
            <DialogFooter>
              <Button type="button" variant="secondary" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={save.isPending}>
                {save.isPending ? "Saving..." : "Save candidate"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
