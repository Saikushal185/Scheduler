"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CalendarPlus, Ban, Trash2 } from "lucide-react";
import * as React from "react";

import { usePageMeta } from "@/components/layout/page";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogFooter } from "@/components/ui/dialog";
import { Alert, ErrorState, LoadingState } from "@/components/ui/feedback";
import { Field, Input, Select } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { EmptyRow, TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { useAvailability, useBusySlots, useFaculty } from "@/lib/queries";
import type { Availability, BusySlot } from "@/lib/types";
import { formatDate, formatTime, todayISO } from "@/lib/utils";

export default function AvailabilityPage() {
  const [facultyId, setFacultyId] = React.useState<string>("");
  const [dialog, setDialog] = React.useState<"availability" | "busy" | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [form, setForm] = React.useState({
    faculty_id: "",
    date: todayISO(),
    start_time: "09:00",
    end_time: "17:00",
    availability_status: "AVAILABLE",
    reason: "",
  });

  const { notify } = useToast();
  const client = useQueryClient();
  const { data: faculty } = useFaculty();
  const params = facultyId ? { faculty_id: Number(facultyId) } : {};
  const { data: availability, isLoading, error: loadError } = useAvailability(params);
  const { data: busySlots } = useBusySlots(params);

  usePageMeta(
    "Faculty Availability",
    "Declared working windows and blocking commitments - free slots update automatically",
    <div className="flex gap-2">
      <Button
        size="sm"
        variant="secondary"
        onClick={() => {
          setError(null);
          setForm({ ...form, faculty_id: facultyId || "" });
          setDialog("busy");
        }}
      >
        <Ban className="h-3.5 w-3.5" /> Block time
      </Button>
      <Button
        size="sm"
        onClick={() => {
          setError(null);
          setForm({ ...form, faculty_id: facultyId || "" });
          setDialog("availability");
        }}
      >
        <CalendarPlus className="h-3.5 w-3.5" /> Add availability
      </Button>
    </div>,
    [facultyId],
  );

  const facultyById = React.useMemo(
    () => new Map((faculty ?? []).map((member) => [member.id, member])),
    [faculty],
  );

  const createAvailability = useMutation({
    mutationFn: () =>
      api.post<Availability>("/faculty-availability", {
        faculty_id: Number(form.faculty_id),
        date: form.date,
        start_time: form.start_time,
        end_time: form.end_time,
        availability_status: form.availability_status,
      }),
    onSuccess: () => {
      notify("Availability saved - free slots recalculated.");
      setDialog(null);
      client.invalidateQueries();
    },
    onError: (err: Error) => setError(err.message),
  });

  const createBusy = useMutation({
    mutationFn: () =>
      api.post<BusySlot>("/faculty-busy-slots", {
        faculty_id: Number(form.faculty_id),
        date: form.date,
        start_time: form.start_time,
        end_time: form.end_time,
        reason: form.reason || null,
      }),
    onSuccess: () => {
      notify("Busy slot added - free slots recalculated.");
      setDialog(null);
      client.invalidateQueries();
    },
    onError: (err: Error) => setError(err.message),
  });

  const removeAvailability = useMutation({
    mutationFn: (id: number) => api.delete(`/faculty-availability/${id}`),
    onSuccess: () => {
      notify("Availability window removed.");
      client.invalidateQueries();
    },
    onError: (err: Error) => notify(err.message, "error"),
  });

  const removeBusy = useMutation({
    mutationFn: (id: number) => api.delete(`/faculty-busy-slots/${id}`),
    onSuccess: () => {
      notify("Busy slot removed.");
      client.invalidateQueries();
    },
    onError: (err: Error) => notify(err.message, "error"),
  });

  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="flex flex-wrap items-end gap-3 pt-5">
          <Field label="Faculty" className="w-72">
            <Select value={facultyId} onChange={(event) => setFacultyId(event.target.value)}>
              <option value="">All faculty</option>
              {(faculty ?? []).map((member) => (
                <option key={member.id} value={member.id}>
                  {member.faculty_code} · {member.faculty_name}
                </option>
              ))}
            </Select>
          </Field>
          <div className="ml-auto text-xs text-slate-500">
            {availability?.length ?? 0} availability window(s) ·{" "}
            {busySlots?.length ?? 0} busy slot(s)
          </div>
        </CardContent>
      </Card>

      <Tabs defaultValue="availability">
        <TabsList>
          <TabsTrigger value="availability">Availability windows</TabsTrigger>
          <TabsTrigger value="busy">Busy slots</TabsTrigger>
        </TabsList>

        <TabsContent value="availability">
          <Card>
            <CardHeader>
              <CardTitle>Declared working windows</CardTitle>
              <p className="text-[11px] text-slate-400">
                Free slots = availability − busy slots − booked interviews
              </p>
            </CardHeader>
            <CardContent className="px-0 pb-0">
              {isLoading ? (
                <LoadingState />
              ) : loadError ? (
                <ErrorState error={loadError} />
              ) : (
                <Table>
                  <THead>
                    <TR>
                      <TH>Faculty</TH>
                      <TH>Date</TH>
                      <TH>Window</TH>
                      <TH>Status</TH>
                      <TH className="text-right">Actions</TH>
                    </TR>
                  </THead>
                  <TBody>
                    {availability?.length ? (
                      availability.map((row) => (
                        <TR key={row.id}>
                          <TD>
                            {facultyById.get(row.faculty_id)?.faculty_name ??
                              `Faculty ${row.faculty_id}`}
                          </TD>
                          <TD>{formatDate(row.date)}</TD>
                          <TD className="whitespace-nowrap">
                            {formatTime(row.start_time)} - {formatTime(row.end_time)}
                          </TD>
                          <TD>
                            <StatusBadge status={row.availability_status} />
                          </TD>
                          <TD className="text-right">
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => removeAvailability.mutate(row.id)}
                            >
                              <Trash2 className="h-3.5 w-3.5 text-[var(--color-danger)]" />
                            </Button>
                          </TD>
                        </TR>
                      ))
                    ) : (
                      <EmptyRow
                        colSpan={5}
                        message="No availability declared - import the Faculty Availability sheet."
                      />
                    )}
                  </TBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="busy">
          <Card>
            <CardHeader>
              <CardTitle>Blocking commitments</CardTitle>
              <p className="text-[11px] text-slate-400">
                Slots created by interviews cannot be deleted here - cancel the interview instead.
              </p>
            </CardHeader>
            <CardContent className="px-0 pb-0">
              <Table>
                <THead>
                  <TR>
                    <TH>Faculty</TH>
                    <TH>Date</TH>
                    <TH>Window</TH>
                    <TH>Source</TH>
                    <TH>Reason</TH>
                    <TH className="text-right">Actions</TH>
                  </TR>
                </THead>
                <TBody>
                  {busySlots?.length ? (
                    busySlots.map((row) => (
                      <TR key={row.id}>
                        <TD>
                          {facultyById.get(row.faculty_id)?.faculty_name ??
                            `Faculty ${row.faculty_id}`}
                        </TD>
                        <TD>{formatDate(row.date)}</TD>
                        <TD className="whitespace-nowrap">
                          {formatTime(row.start_time)} - {formatTime(row.end_time)}
                        </TD>
                        <TD>
                          <Badge tone={row.source === "INTERVIEW" ? "brand" : "neutral"}>
                            {row.source}
                          </Badge>
                        </TD>
                        <TD className="text-[11px] text-slate-500">{row.reason ?? "-"}</TD>
                        <TD className="text-right">
                          <Button
                            variant="ghost"
                            size="icon"
                            disabled={Boolean(row.interview_id)}
                            onClick={() => removeBusy.mutate(row.id)}
                          >
                            <Trash2 className="h-3.5 w-3.5 text-[var(--color-danger)]" />
                          </Button>
                        </TD>
                      </TR>
                    ))
                  ) : (
                    <EmptyRow colSpan={6} message="No busy slots recorded." />
                  )}
                </TBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <Dialog open={dialog !== null} onOpenChange={(open) => !open && setDialog(null)}>
        <DialogContent
          title={dialog === "busy" ? "Block faculty time" : "Add availability window"}
          description={
            dialog === "busy"
              ? "Blocked time is removed from the faculty member's free slots."
              : "Free slots are recalculated as soon as the window is saved."
          }
        >
          <form
            onSubmit={(event) => {
              event.preventDefault();
              (dialog === "busy" ? createBusy : createAvailability).mutate();
            }}
          >
            {error ? (
              <Alert tone="danger" className="mb-3">
                {error}
              </Alert>
            ) : null}
            <Field label="Faculty" className="mb-3">
              <Select
                required
                value={form.faculty_id}
                onChange={(event) => setForm({ ...form, faculty_id: event.target.value })}
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
                  value={form.date}
                  onChange={(event) => setForm({ ...form, date: event.target.value })}
                />
              </Field>
              <Field label="From">
                <Input
                  type="time"
                  required
                  value={form.start_time}
                  onChange={(event) => setForm({ ...form, start_time: event.target.value })}
                />
              </Field>
              <Field label="To">
                <Input
                  type="time"
                  required
                  value={form.end_time}
                  onChange={(event) => setForm({ ...form, end_time: event.target.value })}
                />
              </Field>
            </div>
            {dialog === "busy" ? (
              <Field label="Reason" className="mt-3">
                <Input
                  placeholder="Department meeting"
                  value={form.reason}
                  onChange={(event) => setForm({ ...form, reason: event.target.value })}
                />
              </Field>
            ) : (
              <Field label="Status" className="mt-3">
                <Select
                  value={form.availability_status}
                  onChange={(event) =>
                    setForm({ ...form, availability_status: event.target.value })
                  }
                >
                  <option value="AVAILABLE">Available</option>
                  <option value="UNAVAILABLE">Unavailable</option>
                  <option value="TENTATIVE">Tentative</option>
                </Select>
              </Field>
            )}
            <DialogFooter>
              <Button type="button" variant="secondary" onClick={() => setDialog(null)}>
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={createAvailability.isPending || createBusy.isPending}
              >
                Save
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
