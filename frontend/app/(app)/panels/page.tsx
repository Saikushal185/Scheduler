"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CalendarSearch, Pencil, Plus, Trash2, Users } from "lucide-react";
import * as React from "react";

import { usePageMeta } from "@/components/layout/page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogFooter } from "@/components/ui/dialog";
import { Alert, EmptyState, LoadingState } from "@/components/ui/feedback";
import { Field, Input, Select } from "@/components/ui/input";
import { EmptyRow, TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { useFaculty, usePanelAvailability, usePanels } from "@/lib/queries";
import type { AlternativePanel, Panel } from "@/lib/types";
import { addDaysISO, formatDate, formatTime, todayISO } from "@/lib/utils";

type FormState = {
  panel_code: string;
  panel_name: string;
  department: string;
  description: string;
  minimum_panel_size: number;
  maximum_panel_size: number;
  members: { faculty_id: number; is_mandatory: boolean }[];
};

const EMPTY: FormState = {
  panel_code: "",
  panel_name: "",
  department: "",
  description: "",
  minimum_panel_size: 2,
  maximum_panel_size: 3,
  members: [],
};

export default function PanelsPage() {
  const [open, setOpen] = React.useState(false);
  const [editing, setEditing] = React.useState<Panel | null>(null);
  const [form, setForm] = React.useState<FormState>(EMPTY);
  const [error, setError] = React.useState<string | null>(null);
  const [selectedPanel, setSelectedPanel] = React.useState<number | null>(null);
  const [alternatives, setAlternatives] = React.useState<AlternativePanel[] | null>(null);
  const [altForm, setAltForm] = React.useState({
    date: todayISO(),
    start_time: "10:00",
    end_time: "10:30",
  });

  const { notify } = useToast();
  const client = useQueryClient();
  const { data: panels, isLoading } = usePanels();
  const { data: faculty } = useFaculty();
  const { data: availability, isFetching: availabilityLoading } = usePanelAvailability(
    selectedPanel,
    { start_date: todayISO(), end_date: addDaysISO(todayISO(), 13) },
  );

  usePageMeta(
    "Panel Groups",
    "Interview panels, their members and the windows where they are available",
    <Button
      size="sm"
      onClick={() => {
        setEditing(null);
        setForm(EMPTY);
        setError(null);
        setOpen(true);
      }}
    >
      <Plus className="h-3.5 w-3.5" /> Create panel
    </Button>,
  );

  const save = useMutation({
    mutationFn: async (payload: FormState) => {
      const body = {
        panel_name: payload.panel_name,
        department: payload.department || null,
        description: payload.description || null,
        minimum_panel_size: Number(payload.minimum_panel_size),
        maximum_panel_size: Number(payload.maximum_panel_size),
        members: payload.members.map((member) => ({
          faculty_id: member.faculty_id,
          role: "MEMBER",
          is_mandatory: member.is_mandatory,
        })),
      };
      if (editing) return api.put<Panel>(`/panels/${editing.id}`, body);
      return api.post<Panel>("/panels", { ...body, panel_code: payload.panel_code });
    },
    onSuccess: () => {
      notify(editing ? "Panel updated." : "Panel created.");
      setOpen(false);
      client.invalidateQueries();
    },
    onError: (err: Error) => setError(err.message),
  });

  const remove = useMutation({
    mutationFn: (panel: Panel) => api.delete(`/panels/${panel.id}`),
    onSuccess: () => {
      notify("Panel deleted.");
      client.invalidateQueries();
    },
    onError: (err: Error) => notify(err.message, "error"),
  });

  const findAlternatives = useMutation({
    mutationFn: () =>
      api.post<AlternativePanel[]>("/panels/alternatives", {
        date: altForm.date,
        start_time: altForm.start_time,
        end_time: altForm.end_time,
        exclude_panel_ids: selectedPanel ? [selectedPanel] : [],
      }),
    onSuccess: (result) => {
      setAlternatives(result);
      notify(`${result.length} alternative panel(s) available for that slot.`);
    },
    onError: (err: Error) => notify(err.message, "error"),
  });

  function toggleMember(facultyId: number) {
    setForm((current) => {
      const exists = current.members.some((member) => member.faculty_id === facultyId);
      return {
        ...current,
        members: exists
          ? current.members.filter((member) => member.faculty_id !== facultyId)
          : [...current.members, { faculty_id: facultyId, is_mandatory: false }],
      };
    });
  }

  return (
    <div className="space-y-4">
      {isLoading ? (
        <LoadingState />
      ) : (
        <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
          {(panels ?? []).map((panel) => (
            <Card key={panel.id}>
              <CardHeader>
                <div>
                  <CardTitle>{panel.panel_name}</CardTitle>
                  <p className="mt-0.5 text-[11px] text-slate-400">
                    {panel.panel_code}
                    {panel.department ? ` · ${panel.department}` : ""}
                  </p>
                </div>
                <div className="flex gap-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    title="Check availability"
                    onClick={() => {
                      setSelectedPanel(panel.id);
                      setAlternatives(null);
                    }}
                  >
                    <CalendarSearch className="h-3.5 w-3.5" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => {
                      setEditing(panel);
                      setError(null);
                      setForm({
                        panel_code: panel.panel_code,
                        panel_name: panel.panel_name,
                        department: panel.department ?? "",
                        description: panel.description ?? "",
                        minimum_panel_size: panel.minimum_panel_size,
                        maximum_panel_size: panel.maximum_panel_size,
                        members: panel.members.map((member) => ({
                          faculty_id: member.faculty_id,
                          is_mandatory: member.is_mandatory,
                        })),
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
                      if (window.confirm(`Delete panel ${panel.panel_code}?`)) {
                        remove.mutate(panel);
                      }
                    }}
                  >
                    <Trash2 className="h-3.5 w-3.5 text-[var(--color-danger)]" />
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <div className="mb-3 flex flex-wrap gap-1.5">
                  <Badge tone="brand">
                    <Users className="h-3 w-3" /> {panel.members.length} members
                  </Badge>
                  <Badge tone="info">
                    min {panel.minimum_panel_size} · max {panel.maximum_panel_size}
                  </Badge>
                  {panel.is_active ? null : <Badge tone="danger">inactive</Badge>}
                </div>
                <ul className="space-y-1">
                  {panel.members.map((member) => (
                    <li
                      key={member.id}
                      className="flex items-center justify-between text-xs text-slate-600"
                    >
                      <span className="truncate">
                        {member.faculty?.faculty_name ?? `Faculty ${member.faculty_id}`}
                      </span>
                      {member.is_mandatory ? (
                        <Badge tone="warning">mandatory</Badge>
                      ) : (
                        <span className="text-[10px] text-slate-400">
                          {member.faculty?.department ?? ""}
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          ))}
          {!panels?.length ? (
            <Card className="lg:col-span-2 xl:col-span-3">
              <EmptyState
                title="No panels yet"
                description="Import the Panel Groups sheet or create a panel manually."
              />
            </Card>
          ) : null}
        </div>
      )}

      {selectedPanel ? (
        <Card>
          <CardHeader>
            <div>
              <CardTitle>
                Availability · {availability?.panel_name ?? "Loading..."}
              </CardTitle>
              <p className="text-[11px] text-slate-400">
                Windows where the complete panel is free, and where alternatives are needed
              </p>
            </div>
            <Button variant="ghost" size="sm" onClick={() => setSelectedPanel(null)}>
              Close
            </Button>
          </CardHeader>
          <CardContent className="space-y-4">
            {availabilityLoading ? (
              <LoadingState />
            ) : availability ? (
              <>
                <div className="flex flex-wrap gap-2 text-xs">
                  <Badge tone="success">
                    {availability.fully_available_windows.length} full-panel window(s)
                  </Badge>
                  <Badge tone="warning">
                    {availability.partially_available_windows.length} partial window(s)
                  </Badge>
                  <Badge tone="neutral">
                    minimum {availability.minimum_panel_size} of{" "}
                    {availability.total_members}
                  </Badge>
                </div>

                {availability.conflicts.length ? (
                  <Alert tone="warning" title="Faculty conflicts detected">
                    <ul className="list-disc pl-4">
                      {availability.conflicts.slice(0, 4).map((message, index) => (
                        <li key={index}>{message}</li>
                      ))}
                    </ul>
                  </Alert>
                ) : null}

                <Table>
                  <THead>
                    <TR>
                      <TH>Date</TH>
                      <TH>Window</TH>
                      <TH>Available</TH>
                      <TH>Complete panel</TH>
                    </TR>
                  </THead>
                  <TBody>
                    {availability.fully_available_windows.length ? (
                      availability.fully_available_windows.slice(0, 12).map((slot, index) => (
                        <TR key={index}>
                          <TD>{formatDate(slot.date)}</TD>
                          <TD className="whitespace-nowrap">
                            {formatTime(slot.start_time)} - {formatTime(slot.end_time)}
                          </TD>
                          <TD>{slot.available_count}</TD>
                          <TD>
                            <Badge tone="success">yes</Badge>
                          </TD>
                        </TR>
                      ))
                    ) : (
                      <EmptyRow
                        colSpan={4}
                        message="The complete panel is never free in this range."
                      />
                    )}
                  </TBody>
                </Table>

                <div className="rounded-lg border border-[var(--color-border)] p-3">
                  <p className="mb-2 text-xs font-medium text-slate-700">
                    Find an alternative panel for a specific slot
                  </p>
                  <div className="flex flex-wrap items-end gap-2">
                    <Field label="Date" className="w-40">
                      <Input
                        type="date"
                        value={altForm.date}
                        onChange={(event) =>
                          setAltForm({ ...altForm, date: event.target.value })
                        }
                      />
                    </Field>
                    <Field label="From" className="w-32">
                      <Input
                        type="time"
                        value={altForm.start_time}
                        onChange={(event) =>
                          setAltForm({ ...altForm, start_time: event.target.value })
                        }
                      />
                    </Field>
                    <Field label="To" className="w-32">
                      <Input
                        type="time"
                        value={altForm.end_time}
                        onChange={(event) =>
                          setAltForm({ ...altForm, end_time: event.target.value })
                        }
                      />
                    </Field>
                    <Button
                      size="sm"
                      disabled={findAlternatives.isPending}
                      onClick={() => findAlternatives.mutate()}
                    >
                      Find alternatives
                    </Button>
                  </div>

                  {alternatives ? (
                    alternatives.length ? (
                      <Table className="mt-3">
                        <THead>
                          <TR>
                            <TH>Panel</TH>
                            <TH>Available faculty</TH>
                            <TH>Minimum</TH>
                            <TH>Match score</TH>
                          </TR>
                        </THead>
                        <TBody>
                          {alternatives.map((item) => (
                            <TR key={item.panel_id}>
                              <TD>
                                {item.panel_code} · {item.panel_name}
                              </TD>
                              <TD>{item.available_count}</TD>
                              <TD>{item.minimum_panel_size}</TD>
                              <TD>{item.match_score}</TD>
                            </TR>
                          ))}
                        </TBody>
                      </Table>
                    ) : (
                      <Alert tone="warning" className="mt-3">
                        No other panel can cover that slot.
                      </Alert>
                    )
                  ) : null}
                </div>
              </>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent
          title={editing ? `Edit ${editing.panel_name}` : "Create panel"}
          description="The minimum size is enforced as a hard scheduling constraint."
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
              <Field label="Panel code">
                <Input
                  required
                  disabled={Boolean(editing)}
                  value={form.panel_code}
                  onChange={(event) => setForm({ ...form, panel_code: event.target.value })}
                />
              </Field>
              <Field label="Panel name">
                <Input
                  required
                  value={form.panel_name}
                  onChange={(event) => setForm({ ...form, panel_name: event.target.value })}
                />
              </Field>
              <Field label="Department">
                <Input
                  value={form.department}
                  onChange={(event) => setForm({ ...form, department: event.target.value })}
                />
              </Field>
              <Field label="Description">
                <Input
                  value={form.description}
                  onChange={(event) => setForm({ ...form, description: event.target.value })}
                />
              </Field>
              <Field label="Minimum panel size">
                <Input
                  type="number"
                  min={1}
                  max={20}
                  value={form.minimum_panel_size}
                  onChange={(event) =>
                    setForm({ ...form, minimum_panel_size: Number(event.target.value) })
                  }
                />
              </Field>
              <Field label="Maximum panel size">
                <Input
                  type="number"
                  min={1}
                  max={20}
                  value={form.maximum_panel_size}
                  onChange={(event) =>
                    setForm({ ...form, maximum_panel_size: Number(event.target.value) })
                  }
                />
              </Field>
            </div>

            <div className="mt-4">
              <p className="mb-1.5 text-xs font-medium text-slate-600">
                Members ({form.members.length} selected)
              </p>
              <div className="max-h-56 space-y-1 overflow-y-auto rounded-lg border border-[var(--color-border)] p-2">
                {(faculty ?? []).map((member) => {
                  const selected = form.members.find((m) => m.faculty_id === member.id);
                  return (
                    <div
                      key={member.id}
                      className="flex items-center justify-between gap-2 rounded px-2 py-1 hover:bg-slate-50"
                    >
                      <label className="flex flex-1 cursor-pointer items-center gap-2 text-xs text-slate-700">
                        <input
                          type="checkbox"
                          checked={Boolean(selected)}
                          onChange={() => toggleMember(member.id)}
                        />
                        <span className="truncate">
                          {member.faculty_name}
                          <span className="text-slate-400"> · {member.department ?? ""}</span>
                        </span>
                      </label>
                      {selected ? (
                        <label className="flex cursor-pointer items-center gap-1 text-[10px] text-slate-500">
                          <input
                            type="checkbox"
                            checked={selected.is_mandatory}
                            onChange={() =>
                              setForm((current) => ({
                                ...current,
                                members: current.members.map((m) =>
                                  m.faculty_id === member.id
                                    ? { ...m, is_mandatory: !m.is_mandatory }
                                    : m,
                                ),
                              }))
                            }
                          />
                          mandatory
                        </label>
                      ) : null}
                    </div>
                  );
                })}
              </div>
            </div>

            <DialogFooter>
              <Button type="button" variant="secondary" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={save.isPending}>
                {save.isPending ? "Saving..." : "Save panel"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
