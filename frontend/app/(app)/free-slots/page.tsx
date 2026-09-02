"use client";

import { RefreshCw } from "lucide-react";
import * as React from "react";

import { usePageMeta } from "@/components/layout/page";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, EmptyState, ErrorState, LoadingState } from "@/components/ui/feedback";
import { Field, Input, Select } from "@/components/ui/input";
import { StatCard } from "@/components/ui/stat-card";
import { useToast } from "@/components/ui/toast";
import {
  useFaculty,
  useFreeSlotGroups,
  useRecalculateFreeSlots,
} from "@/lib/queries";
import { addDaysISO, formatDate, formatTime, minutesToHours, todayISO } from "@/lib/utils";

/** Renders one day's free windows as a proportional timeline. */
function SlotTimeline({
  slots,
}: {
  slots: { id: number; start_time: string; end_time: string; duration_minutes: number }[];
}) {
  const DAY_START = 8 * 60;
  const DAY_END = 19 * 60;
  const span = DAY_END - DAY_START;
  const toMinutes = (value: string) => {
    const [hours, minutes] = value.split(":").map(Number);
    return hours * 60 + minutes;
  };

  return (
    <div className="relative h-7 w-full overflow-hidden rounded-md bg-slate-100">
      {slots.map((slot) => {
        const start = Math.max(DAY_START, toMinutes(slot.start_time));
        const end = Math.min(DAY_END, toMinutes(slot.end_time));
        const left = ((start - DAY_START) / span) * 100;
        const width = Math.max(1, ((end - start) / span) * 100);
        return (
          <div
            key={slot.id}
            title={`${formatTime(slot.start_time)} - ${formatTime(slot.end_time)} (${minutesToHours(slot.duration_minutes)})`}
            className="absolute top-0 flex h-full items-center justify-center overflow-hidden rounded-[4px] bg-[var(--color-success)]/85 px-1 text-[9px] font-medium text-white"
            style={{ left: `${left}%`, width: `${width}%` }}
          >
            {width > 9 ? formatTime(slot.start_time) : ""}
          </div>
        );
      })}
    </div>
  );
}

export default function FreeSlotsPage() {
  const [facultyId, setFacultyId] = React.useState("");
  const [startDate, setStartDate] = React.useState(todayISO());
  const [endDate, setEndDate] = React.useState(addDaysISO(todayISO(), 13));

  const { notify } = useToast();
  const { data: faculty } = useFaculty();
  const recalculate = useRecalculateFreeSlots();
  const { data, isLoading, error } = useFreeSlotGroups({
    faculty_id: facultyId ? Number(facultyId) : undefined,
    start_date: startDate,
    end_date: endDate,
  });

  usePageMeta(
    "Free Slots",
    "Calculated from availability minus busy slots and booked interviews",
    <Button
      size="sm"
      disabled={recalculate.isPending}
      onClick={() =>
        recalculate.mutate(
          {},
          {
            onSuccess: (result) =>
              notify(
                `Recalculated ${result.slots_created} free slot(s) for ${result.faculty_processed} faculty.`,
              ),
            onError: (err: Error) => notify(err.message, "error"),
          },
        )
      }
    >
      <RefreshCw className="h-3.5 w-3.5" />
      {recalculate.isPending ? "Recalculating..." : "Recalculate"}
    </Button>,
  );

  const totals = React.useMemo(() => {
    const groups = data ?? [];
    const minutes = groups.reduce((sum, group) => sum + group.total_free_minutes, 0);
    const slots = groups.reduce((sum, group) => sum + group.slots.length, 0);
    return {
      minutes,
      slots,
      faculty: new Set(groups.map((group) => group.faculty_id)).size,
      days: new Set(groups.map((group) => group.date)).size,
    };
  }, [data]);

  const byDate = React.useMemo(() => {
    const map = new Map<string, typeof data>();
    (data ?? []).forEach((group) => {
      map.set(group.date, [...(map.get(group.date) ?? []), group]);
    });
    return [...map.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [data]);

  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="flex flex-wrap items-end gap-3 pt-5">
          <Field label="Faculty" className="w-64">
            <Select value={facultyId} onChange={(event) => setFacultyId(event.target.value)}>
              <option value="">All faculty</option>
              {(faculty ?? []).map((member) => (
                <option key={member.id} value={member.id}>
                  {member.faculty_code} · {member.faculty_name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="From" className="w-40">
            <Input
              type="date"
              value={startDate}
              onChange={(event) => setStartDate(event.target.value)}
            />
          </Field>
          <Field label="To" className="w-40">
            <Input
              type="date"
              value={endDate}
              onChange={(event) => setEndDate(event.target.value)}
            />
          </Field>
        </CardContent>
      </Card>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Free windows" value={totals.slots} tone="success" />
        <StatCard label="Total free time" value={minutesToHours(totals.minutes)} tone="info" />
        <StatCard label="Faculty with free time" value={totals.faculty} />
        <StatCard label="Days covered" value={totals.days} tone="neutral" />
      </div>

      <Alert tone="info">
        Free slots are derived data. They are recalculated automatically whenever
        availability changes or an interview is scheduled, rescheduled or cancelled.
      </Alert>

      {isLoading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState error={error} />
      ) : byDate.length ? (
        <div className="space-y-4">
          {byDate.map(([date, groups]) => (
            <Card key={date}>
              <CardHeader>
                <CardTitle>{formatDate(date)}</CardTitle>
                <span className="text-[11px] text-slate-400">
                  {groups?.length ?? 0} faculty ·{" "}
                  {minutesToHours(
                    (groups ?? []).reduce((sum, g) => sum + g.total_free_minutes, 0),
                  )}{" "}
                  free
                </span>
              </CardHeader>
              <CardContent className="space-y-2.5">
                {(groups ?? []).map((group) => (
                  <div
                    key={`${group.faculty_id}-${group.date}`}
                    className="grid grid-cols-1 items-center gap-2 sm:grid-cols-[200px_1fr_120px]"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-xs font-medium text-slate-800">
                        {group.faculty_name}
                      </p>
                      <p className="truncate text-[10px] text-slate-400">
                        {group.department ?? group.faculty_code}
                      </p>
                    </div>
                    <SlotTimeline slots={group.slots} />
                    <p className="text-right text-[11px] text-slate-500">
                      {group.slots.length} slot(s) ·{" "}
                      {minutesToHours(group.total_free_minutes)}
                    </p>
                  </div>
                ))}
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <EmptyState
            title="No free slots in this range"
            description="Import faculty availability, then recalculate to derive the free slots."
          />
        </Card>
      )}
    </div>
  );
}
