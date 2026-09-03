"use client";

import { useQueryClient } from "@tanstack/react-query";
import {
  CalendarDays,
  Lock,
  LockOpen,
  CalendarPlus,
  Rows3,
  TriangleAlert,
  UserX,
  XCircle,
} from "lucide-react";
import * as React from "react";

import { usePageMeta } from "@/components/layout/page";
import { ScheduleCalendar } from "@/components/schedule-calendar";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogFooter } from "@/components/ui/dialog";
import { Alert, ErrorState, LoadingState } from "@/components/ui/feedback";
import { Field, Input, Select } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { EmptyRow, TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api";
import {
  useAvailableSlots,
  useCalendar,
  useCandidates,
  useChangeInterviewStatus,
  useCreateInterview,
  useConflicts,
  useDepartments,
  useFaculty,
  useInterviewHistory,
  useInterviews,
  useLockInterview,
  useMarkFacultyUnavailable,
  usePanels,
  useRescheduleInterview,
  useSettings,
} from "@/lib/queries";
import type { AvailableSlot, Interview } from "@/lib/types";
import { formatDate, formatDateTime, formatTime, todayISO } from "@/lib/utils";

const STATUSES = [
  "SCHEDULED", "RESCHEDULED", "PENDING", "CONFLICT", "COMPLETED", "CANCELLED",
];

export default function SchedulePage() {
  const { notify } = useToast();
  const client = useQueryClient();

  const [filters, setFilters] = React.useState({
    status: "",
    panel_id: "",
    faculty_id: "",
    department: "",
    start_date: "",
    end_date: "",
  });
  const [selected, setSelected] = React.useState<Interview | null>(null);
  const [unavailableOpen, setUnavailableOpen] = React.useState(false);
  const [rescheduleForm, setRescheduleForm] = React.useState({
    date: "",
    start_time: "",
    panel_id: "",
    faculty_ids: [] as number[],
    reason: "",
    force: false,
  });
  const [unavailableForm, setUnavailableForm] = React.useState({
    faculty_id: "",
    date: todayISO(),
    start_time: "09:00",
    end_time: "17:00",
    reason: "",
  });
  const [warnings, setWarnings] = React.useState<string[]>([]);

  // Manual booking. The slot is chosen from what the engine says is actually
  // bookable, so a clash cannot be created here by construction.
  const [bookOpen, setBookOpen] = React.useState(false);
  const [bookError, setBookError] = React.useState<string | null>(null);
  const [bookForm, setBookForm] = React.useState({
    candidate_id: "",
    panel_id: "",
    date: todayISO(),
    location: "",
    notes: "",
  });
  const [chosenSlot, setChosenSlot] = React.useState<AvailableSlot | null>(null);

  const query = React.useMemo(
    () =>
      Object.fromEntries(
        Object.entries(filters).filter(([, value]) => value !== ""),
      ) as Record<string, string>,
    [filters],
  );

  const { data: interviews, isLoading, error } = useInterviews(query);
  const { data: events } = useCalendar(query);
  const { data: conflicts } = useConflicts();
  const { data: panels } = usePanels();
  const { data: faculty } = useFaculty();
  const { data: departments } = useDepartments();
  const { data: history } = useInterviewHistory(selected?.id ?? null);
  const { data: candidates } = useCandidates({});
  const { data: settings } = useSettings();
  const {
    data: slots,
    isFetching: slotsLoading,
    error: slotsError,
  } = useAvailableSlots({
    candidate_id: bookForm.candidate_id ? Number(bookForm.candidate_id) : undefined,
    panel_id: bookForm.panel_id ? Number(bookForm.panel_id) : undefined,
    date: bookForm.date || undefined,
  });

  const reschedule = useRescheduleInterview();
  const changeStatus = useChangeInterviewStatus();
  const lock = useLockInterview();
  const markUnavailable = useMarkFacultyUnavailable();
  const createInterview = useCreateInterview();

  usePageMeta(
    "Interview Schedule",
    "Day, week and table views with manual overrides and conflict detection",
    <div className="flex gap-2">
      <Button size="sm" variant="secondary" onClick={() => setUnavailableOpen(true)}>
        <UserX className="h-3.5 w-3.5" /> Mark faculty unavailable
      </Button>
      <Button
        size="sm"
        onClick={() => {
          setBookError(null);
          setChosenSlot(null);
          setBookForm({
            candidate_id: "",
            panel_id: "",
            date: settings?.schedule_start_date || todayISO(),
            location: "",
            notes: "",
          });
          setBookOpen(true);
        }}
      >
        <CalendarPlus className="h-3.5 w-3.5" /> Book manually
      </Button>
    </div>,
    [settings?.schedule_start_date],
  );

  function openInterview(interview: Interview) {
    setSelected(interview);
    setWarnings([]);
    setRescheduleForm({
      date: interview.date ?? "",
      start_time: interview.start_time?.slice(0, 5) ?? "",
      panel_id: interview.panel_id ? String(interview.panel_id) : "",
      faculty_ids: interview.panel_members.map((member) => member.faculty_id),
      reason: "",
      force: false,
    });
  }

  const selectedPanel = panels?.find(
    (panel) => panel.id === Number(rescheduleForm.panel_id || selected?.panel_id),
  );

  function submitReschedule(force: boolean) {
    if (!selected) return;
    const body: Record<string, unknown> = {
      date: rescheduleForm.date,
      start_time: rescheduleForm.start_time,
      reason: rescheduleForm.reason || undefined,
      force,
    };
    if (rescheduleForm.panel_id) body.panel_id = Number(rescheduleForm.panel_id);
    if (rescheduleForm.faculty_ids.length) body.faculty_ids = rescheduleForm.faculty_ids;

    reschedule.mutate(
      { id: selected.id, body },
      {
        onSuccess: (result) => {
          setWarnings(result.warnings);
          notify(
            result.warnings.length
              ? "Saved with warnings - the interview is flagged as a conflict."
              : "Interview rescheduled and free slots recalculated.",
            result.warnings.length ? "error" : "success",
          );
          setSelected(result.interview);
          client.invalidateQueries();
        },
        onError: (err: Error) => {
          const lines = err instanceof ApiError ? err.detailLines : [];
          setWarnings(lines.length ? lines : [err.message]);
          notify(err.message, "error");
        },
      },
    );
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="flex flex-wrap items-end gap-3 pt-5">
          <Field label="Status" className="w-40">
            <Select
              value={filters.status}
              onChange={(event) => setFilters({ ...filters, status: event.target.value })}
            >
              <option value="">All statuses</option>
              {STATUSES.map((status) => (
                <option key={status} value={status}>
                  {status}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Panel" className="w-44">
            <Select
              value={filters.panel_id}
              onChange={(event) => setFilters({ ...filters, panel_id: event.target.value })}
            >
              <option value="">All panels</option>
              {(panels ?? []).map((panel) => (
                <option key={panel.id} value={panel.id}>
                  {panel.panel_code}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Faculty" className="w-52">
            <Select
              value={filters.faculty_id}
              onChange={(event) => setFilters({ ...filters, faculty_id: event.target.value })}
            >
              <option value="">All faculty</option>
              {(faculty ?? []).map((member) => (
                <option key={member.id} value={member.id}>
                  {member.faculty_name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Department" className="w-44">
            <Select
              value={filters.department}
              onChange={(event) => setFilters({ ...filters, department: event.target.value })}
            >
              <option value="">All departments</option>
              {(departments ?? []).map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="From" className="w-36">
            <Input
              type="date"
              value={filters.start_date}
              onChange={(event) => setFilters({ ...filters, start_date: event.target.value })}
            />
          </Field>
          <Field label="To" className="w-36">
            <Input
              type="date"
              value={filters.end_date}
              onChange={(event) => setFilters({ ...filters, end_date: event.target.value })}
            />
          </Field>
          <Button
            variant="ghost"
            size="sm"
            className="mb-0.5"
            onClick={() =>
              setFilters({
                status: "", panel_id: "", faculty_id: "", department: "",
                start_date: "", end_date: "",
              })
            }
          >
            Clear
          </Button>
        </CardContent>
      </Card>

      {conflicts?.length ? (
        <Alert tone="danger" title={`${conflicts.length} conflict(s) in the current schedule`}>
          <ul className="mt-1 list-disc space-y-0.5 pl-4">
            {conflicts.slice(0, 5).map((conflict, index) => (
              <li key={index}>{conflict.message}</li>
            ))}
          </ul>
        </Alert>
      ) : null}

      <Tabs defaultValue="calendar">
        <TabsList>
          <TabsTrigger value="calendar">
            <CalendarDays className="mr-1 inline h-3.5 w-3.5" /> Calendar
          </TabsTrigger>
          <TabsTrigger value="table">
            <Rows3 className="mr-1 inline h-3.5 w-3.5" /> Table
          </TabsTrigger>
        </TabsList>

        <TabsContent value="calendar">
          <Card>
            <CardContent className="pt-5">
              <div className="mb-3 flex flex-wrap gap-2 text-[11px] text-slate-500">
                {["SCHEDULED", "RESCHEDULED", "COMPLETED", "PENDING", "CONFLICT"].map(
                  (status) => (
                    <span key={status} className="flex items-center gap-1">
                      <StatusBadge status={status} />
                    </span>
                  ),
                )}
              </div>
              <ScheduleCalendar
                events={events ?? []}
                initialDate={events?.[0]?.start?.slice(0, 10)}
                onSelect={(id) => {
                  const interview = interviews?.find((item) => item.id === id);
                  if (interview) openInterview(interview);
                }}
              />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="table">
          <Card>
            <CardContent className="px-0 pb-0 pt-2">
              {isLoading ? (
                <LoadingState />
              ) : error ? (
                <ErrorState error={error} />
              ) : (
                <Table>
                  <THead>
                    <TR>
                      <TH>Code</TH>
                      <TH>Candidate</TH>
                      <TH>Date</TH>
                      <TH>Time</TH>
                      <TH>Panel</TH>
                      <TH>Faculty</TH>
                      <TH>Status</TH>
                      <TH className="text-right">Actions</TH>
                    </TR>
                  </THead>
                  <TBody>
                    {interviews?.length ? (
                      interviews.map((interview) => (
                        <TR key={interview.id}>
                          <TD className="whitespace-nowrap font-mono text-[11px] text-slate-500">
                            {interview.schedule_code}
                          </TD>
                          <TD>
                            <p className="font-medium text-slate-800">
                              {interview.candidate?.candidate_name}
                            </p>
                            <p className="text-[11px] text-slate-400">
                              {interview.candidate?.candidate_code}
                            </p>
                          </TD>
                          <TD>{formatDate(interview.date)}</TD>
                          <TD className="whitespace-nowrap">
                            {formatTime(interview.start_time)} -{" "}
                            {formatTime(interview.end_time)}
                          </TD>
                          <TD>{interview.panel?.panel_code ?? "-"}</TD>
                          <TD className="text-[11px] text-slate-500">
                            {interview.panel_members
                              .map((member) => member.faculty?.faculty_name)
                              .filter(Boolean)
                              .join(", ")}
                          </TD>
                          <TD>
                            <div className="flex items-center gap-1">
                              <StatusBadge status={interview.status} />
                              {interview.is_locked ? (
                                <Lock className="h-3 w-3 text-slate-400" />
                              ) : null}
                            </div>
                          </TD>
                          <TD className="text-right">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => openInterview(interview)}
                            >
                              Manage
                            </Button>
                          </TD>
                        </TR>
                      ))
                    ) : (
                      <EmptyRow
                        colSpan={8}
                        message="No interviews match these filters. Run the scheduler to create some."
                      />
                    )}
                  </TBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* ------------------------------------------------ manual override drawer */}
      <Dialog open={Boolean(selected)} onOpenChange={(open) => !open && setSelected(null)}>
        {selected ? (
          <DialogContent
            className="max-w-2xl"
            title={`${selected.candidate?.candidate_name ?? "Interview"} · ${selected.schedule_code}`}
            description="Manual changes re-check conflicts, recalculate free slots and are recorded in history."
          >
            <div className="mb-4 flex flex-wrap items-center gap-2">
              <StatusBadge status={selected.status} />
              {selected.is_locked ? <Badge tone="warning">locked</Badge> : null}
              {selected.is_manual ? <Badge tone="info">manually adjusted</Badge> : null}
              <Badge tone="neutral">score {Math.round(selected.scheduling_score)}</Badge>
            </div>

            {warnings.length ? (
              <Alert tone="danger" title="Conflicts detected" className="mb-3">
                <ul className="list-disc pl-4">
                  {warnings.map((warning, index) => (
                    <li key={index}>{warning}</li>
                  ))}
                </ul>
                <Button
                  size="sm"
                  variant="danger"
                  className="mt-2"
                  onClick={() => submitReschedule(true)}
                >
                  Apply anyway
                </Button>
              </Alert>
            ) : null}

            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Date">
                <Input
                  type="date"
                  value={rescheduleForm.date}
                  onChange={(event) =>
                    setRescheduleForm({ ...rescheduleForm, date: event.target.value })
                  }
                />
              </Field>
              <Field label="Start time">
                <Input
                  type="time"
                  value={rescheduleForm.start_time}
                  onChange={(event) =>
                    setRescheduleForm({ ...rescheduleForm, start_time: event.target.value })
                  }
                />
              </Field>
              <Field label="Panel">
                <Select
                  value={rescheduleForm.panel_id}
                  onChange={(event) =>
                    setRescheduleForm({
                      ...rescheduleForm,
                      panel_id: event.target.value,
                      faculty_ids: [],
                    })
                  }
                >
                  {(panels ?? []).map((panel) => (
                    <option key={panel.id} value={panel.id}>
                      {panel.panel_code} · {panel.panel_name}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Reason" hint="Stored in the interview history">
                <Input
                  value={rescheduleForm.reason}
                  placeholder="Candidate requested a later slot"
                  onChange={(event) =>
                    setRescheduleForm({ ...rescheduleForm, reason: event.target.value })
                  }
                />
              </Field>
            </div>

            <div className="mt-3">
              <p className="mb-1.5 text-xs font-medium text-slate-600">
                Faculty members
                {selectedPanel
                  ? ` (minimum ${selectedPanel.minimum_panel_size})`
                  : ""}
              </p>
              <div className="flex flex-wrap gap-2 rounded-lg border border-[var(--color-border)] p-2">
                {(selectedPanel?.members ?? []).map((member) => {
                  const checked = rescheduleForm.faculty_ids.includes(member.faculty_id);
                  return (
                    <label
                      key={member.id}
                      className="flex cursor-pointer items-center gap-1.5 rounded px-2 py-1 text-xs text-slate-700 hover:bg-slate-50"
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() =>
                          setRescheduleForm((current) => ({
                            ...current,
                            faculty_ids: checked
                              ? current.faculty_ids.filter((id) => id !== member.faculty_id)
                              : [...current.faculty_ids, member.faculty_id],
                          }))
                        }
                      />
                      {member.faculty?.faculty_name}
                      {member.is_mandatory ? (
                        <span className="text-[10px] text-[var(--color-warning)]">
                          (mandatory)
                        </span>
                      ) : null}
                    </label>
                  );
                })}
              </div>
            </div>

            {selected.priority_info?.length ? (
              <div className="mt-3">
                <p className="mb-1.5 text-xs font-medium text-slate-600">
                  How this slot scored
                </p>
                <div className="flex flex-wrap gap-1">
                  {selected.priority_info.map((info, index) => (
                    <span
                      key={index}
                      title={info.detail}
                      className={`rounded px-1.5 py-0.5 text-[10px] ${
                        info.satisfied
                          ? "bg-[var(--color-success-light)] text-[var(--color-success)]"
                          : "bg-[var(--color-danger-light)] text-[var(--color-danger)]"
                      }`}
                    >
                      {info.priority} · {info.type.replace(/_/g, " ").toLowerCase()}
                    </span>
                  ))}
                </div>
              </div>
            ) : null}

            {history?.length ? (
              <div className="mt-4">
                <p className="mb-1.5 text-xs font-medium text-slate-600">History</p>
                <ul className="max-h-40 space-y-1.5 overflow-y-auto rounded-lg border border-[var(--color-border)] p-2">
                  {history.map((entry) => (
                    <li key={entry.id} className="text-[11px] text-slate-600">
                      <span className="font-medium">
                        {entry.action.replace(/_/g, " ").toLowerCase()}
                      </span>{" "}
                      · {formatDateTime(entry.created_at)}
                      {entry.reason ? (
                        <span className="text-slate-400"> — {entry.reason}</span>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            <DialogFooter className="flex-wrap">
              <Button
                variant="secondary"
                size="sm"
                onClick={() =>
                  lock.mutate(
                    { id: selected.id, is_locked: !selected.is_locked },
                    {
                      onSuccess: (result) => {
                        setSelected(result.interview);
                        notify(
                          result.interview.is_locked
                            ? "Interview locked - the scheduler will keep it."
                            : "Interview unlocked.",
                        );
                      },
                    },
                  )
                }
              >
                {selected.is_locked ? (
                  <>
                    <LockOpen className="h-3.5 w-3.5" /> Unlock
                  </>
                ) : (
                  <>
                    <Lock className="h-3.5 w-3.5" /> Lock
                  </>
                )}
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={() =>
                  changeStatus.mutate(
                    { id: selected.id, status: "COMPLETED" },
                    {
                      onSuccess: (result) => {
                        setSelected(result.interview);
                        notify("Marked as completed - ready for evaluation.");
                      },
                    },
                  )
                }
              >
                Mark completed
              </Button>
              <Button
                variant="danger"
                size="sm"
                onClick={() =>
                  changeStatus.mutate(
                    { id: selected.id, status: "CANCELLED", reason: "Cancelled by admin" },
                    {
                      onSuccess: (result) => {
                        setSelected(result.interview);
                        notify("Interview cancelled - the faculty time is free again.");
                      },
                    },
                  )
                }
              >
                <XCircle className="h-3.5 w-3.5" /> Cancel
              </Button>
              <Button
                size="sm"
                disabled={reschedule.isPending}
                onClick={() => submitReschedule(false)}
              >
                {reschedule.isPending ? "Saving..." : "Save changes"}
              </Button>
            </DialogFooter>
          </DialogContent>
        ) : null}
      </Dialog>

      {/* -------------------------------------------------- manual booking */}
      <Dialog open={bookOpen} onOpenChange={setBookOpen}>
        <DialogContent
          title="Book an interview manually"
          description="Only slots that are genuinely free are offered, so this cannot clash."
          className="max-w-2xl"
        >
          <form
            onSubmit={(event) => {
              event.preventDefault();
              if (!chosenSlot) {
                setBookError("Pick a slot before booking.");
                return;
              }
              setBookError(null);
              createInterview.mutate(
                {
                  candidate_id: Number(bookForm.candidate_id),
                  panel_id: Number(bookForm.panel_id),
                  date: chosenSlot.date,
                  start_time: chosenSlot.start_time,
                  duration_minutes: chosenSlot.duration_minutes,
                  faculty_ids: chosenSlot.faculty_ids,
                  location: bookForm.location || null,
                  notes: bookForm.notes || null,
                },
                {
                  onSuccess: (result) => {
                    notify(`Booked ${result.interview.schedule_code}.`);
                    setBookOpen(false);
                    setChosenSlot(null);
                  },
                  onError: (err: Error) =>
                    setBookError(
                      err instanceof ApiError
                        ? [err.message, ...err.detailLines].join(" ")
                        : err.message,
                    ),
                },
              );
            }}
          >
            {bookError ? (
              <Alert tone="danger" className="mb-3">
                {bookError}
              </Alert>
            ) : null}

            <div className="grid gap-3 sm:grid-cols-3">
              <Field label="Candidate">
                <Select
                  required
                  value={bookForm.candidate_id}
                  onChange={(event) => {
                    setChosenSlot(null);
                    setBookForm((state) => ({
                      ...state,
                      candidate_id: event.target.value,
                    }));
                  }}
                >
                  <option value="">Select a candidate</option>
                  {(candidates ?? []).map((candidate) => (
                    <option key={candidate.id} value={candidate.id}>
                      {candidate.candidate_code} · {candidate.candidate_name}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Panel">
                <Select
                  required
                  value={bookForm.panel_id}
                  onChange={(event) => {
                    setChosenSlot(null);
                    setBookForm((state) => ({ ...state, panel_id: event.target.value }));
                  }}
                >
                  <option value="">Select a panel</option>
                  {(panels ?? []).map((panel) => (
                    <option key={panel.id} value={panel.id}>
                      {panel.panel_code} · {panel.panel_name}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Date">
                <Input
                  type="date"
                  required
                  value={bookForm.date}
                  onChange={(event) => {
                    setChosenSlot(null);
                    setBookForm((state) => ({ ...state, date: event.target.value }));
                  }}
                />
              </Field>
            </div>

            <div className="mt-4">
              <p className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-slate-500">
                Available slots
              </p>
              {!bookForm.candidate_id || !bookForm.panel_id ? (
                <p className="rounded-lg border border-dashed border-[var(--color-border)] px-3 py-6 text-center text-xs text-slate-400">
                  Choose a candidate, a panel and a date to see what is bookable.
                </p>
              ) : slotsLoading ? (
                <LoadingState label="Finding free slots..." />
              ) : slotsError ? (
                <Alert tone="danger">{(slotsError as Error).message}</Alert>
              ) : !slots?.length ? (
                <Alert tone="warning">
                  No free slots for this panel on {formatDate(bookForm.date)}. The
                  panel may not have enough free faculty that day, or the candidate
                  may be unavailable. Try another date or panel.
                </Alert>
              ) : (
                <div className="max-h-56 space-y-1.5 overflow-y-auto rounded-lg border border-[var(--color-border)] p-2">
                  {slots.map((slot) => {
                    const key = `${slot.date}-${slot.start_time}`;
                    const active =
                      chosenSlot?.date === slot.date &&
                      chosenSlot?.start_time === slot.start_time;
                    return (
                      <button
                        key={key}
                        type="button"
                        onClick={() => setChosenSlot(slot)}
                        aria-pressed={active}
                        className={`flex w-full items-center justify-between gap-3 rounded-md border px-2.5 py-2 text-left transition-colors ${
                          active
                            ? "border-[var(--color-brand)] bg-[var(--color-brand-light)]"
                            : "border-transparent hover:bg-slate-50"
                        }`}
                      >
                        <span className="min-w-0">
                          <span className="block text-xs font-medium tabular-nums text-slate-900">
                            {formatTime(slot.start_time)} - {formatTime(slot.end_time)}
                          </span>
                          <span className="block truncate text-[10px] text-slate-500">
                            {slot.faculty_names.join(", ")}
                          </span>
                        </span>
                        <Badge tone={active ? "brand" : "neutral"}>
                          {Math.round(slot.score).toLocaleString()}
                        </Badge>
                      </button>
                    );
                  })}
                </div>
              )}
              {slots?.length ? (
                <p className="mt-1 text-[10px] text-slate-400">
                  Ranked the way the automated scheduler ranks them - the highest
                  score is the slot it would have picked.
                </p>
              ) : null}
            </div>

            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <Field label="Venue (optional)">
                <Input
                  value={bookForm.location}
                  placeholder="Room B-204"
                  onChange={(event) =>
                    setBookForm((state) => ({ ...state, location: event.target.value }))
                  }
                />
              </Field>
              <Field label="Notes (optional)">
                <Input
                  value={bookForm.notes}
                  onChange={(event) =>
                    setBookForm((state) => ({ ...state, notes: event.target.value }))
                  }
                />
              </Field>
            </div>

            <DialogFooter>
              <Button type="button" variant="secondary" onClick={() => setBookOpen(false)}>
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={createInterview.isPending || !chosenSlot}
              >
                {createInterview.isPending
                  ? "Booking..."
                  : chosenSlot
                    ? `Book ${formatTime(chosenSlot.start_time)}`
                    : "Pick a slot"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* ------------------------------------------- mark faculty unavailable */}
      <Dialog open={unavailableOpen} onOpenChange={setUnavailableOpen}>
        <DialogContent
          title="Mark a faculty member unavailable"
          description="Blocks the time and flags every interview that depends on them."
        >
          <form
            onSubmit={(event) => {
              event.preventDefault();
              markUnavailable.mutate(
                {
                  faculty_id: Number(unavailableForm.faculty_id),
                  date: unavailableForm.date,
                  start_time: unavailableForm.start_time,
                  end_time: unavailableForm.end_time,
                  reason: unavailableForm.reason || null,
                },
                {
                  onSuccess: (result) => {
                    setUnavailableOpen(false);
                    notify(
                      result.affected_interviews.length
                        ? `${result.affected_interviews.length} interview(s) now need attention.`
                        : "Time blocked - no interview was affected.",
                      result.affected_interviews.length ? "error" : "success",
                    );
                  },
                  onError: (err: Error) => notify(err.message, "error"),
                },
              );
            }}
          >
            <Field label="Faculty" className="mb-3">
              <Select
                required
                value={unavailableForm.faculty_id}
                onChange={(event) =>
                  setUnavailableForm({ ...unavailableForm, faculty_id: event.target.value })
                }
              >
                <option value="">Select a faculty member</option>
                {(faculty ?? []).map((member) => (
                  <option key={member.id} value={member.id}>
                    {member.faculty_code} · {member.faculty_name}
                  </option>
                ))}
              </Select>
            </Field>
            <div className="grid gap-3 sm:grid-cols-3">
              <Field label="Date">
                <Input
                  type="date"
                  required
                  value={unavailableForm.date}
                  onChange={(event) =>
                    setUnavailableForm({ ...unavailableForm, date: event.target.value })
                  }
                />
              </Field>
              <Field label="From">
                <Input
                  type="time"
                  required
                  value={unavailableForm.start_time}
                  onChange={(event) =>
                    setUnavailableForm({ ...unavailableForm, start_time: event.target.value })
                  }
                />
              </Field>
              <Field label="To">
                <Input
                  type="time"
                  required
                  value={unavailableForm.end_time}
                  onChange={(event) =>
                    setUnavailableForm({ ...unavailableForm, end_time: event.target.value })
                  }
                />
              </Field>
            </div>
            <Field label="Reason" className="mt-3">
              <Input
                placeholder="Medical leave"
                value={unavailableForm.reason}
                onChange={(event) =>
                  setUnavailableForm({ ...unavailableForm, reason: event.target.value })
                }
              />
            </Field>
            <Alert tone="warning" className="mt-3">
              <TriangleAlert className="hidden" />
              Affected interviews are flagged as conflicts so you can reschedule them.
            </Alert>
            <DialogFooter>
              <Button
                type="button"
                variant="secondary"
                onClick={() => setUnavailableOpen(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={markUnavailable.isPending}>
                Block time
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
