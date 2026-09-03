"use client";

import { RefreshCw } from "lucide-react";
import * as React from "react";

import {
  FacultyTimeline,
  TimelineLegend,
  TimelineTotals,
} from "@/components/faculty-timeline";
import { usePageMeta } from "@/components/layout/page";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, EmptyState, ErrorState, LoadingState } from "@/components/ui/feedback";
import { Field, Input, Select } from "@/components/ui/input";
import { StatCard } from "@/components/ui/stat-card";
import { useToast } from "@/components/ui/toast";
import {
  useFaculty,
  useFacultyTimeline,
  useRecalculateFreeSlots,
  useSettings,
} from "@/lib/queries";
import { addDaysISO, formatDate, minutesToHours, todayISO } from "@/lib/utils";

/**
 * Free time in the context that makes it readable: what a faculty member's day
 * is actually doing. Free slots on their own do not say whether the gap next to
 * them is an interview or a blocked-out afternoon, so the whole day is drawn.
 */
export default function FreeSlotsPage() {
  const [facultyId, setFacultyId] = React.useState("");
  const [startDate, setStartDate] = React.useState(todayISO());
  const [endDate, setEndDate] = React.useState(addDaysISO(todayISO(), 13));

  const { notify } = useToast();
  const { data: faculty } = useFaculty();
  const { data: settings } = useSettings();
  const recalculate = useRecalculateFreeSlots();
  const { data, isLoading, error } = useFacultyTimeline({
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

  // Draw the same working day the scheduler uses, with an hour of margin, so a
  // block sitting at the edge is still visible.
  const [dayStart, dayEnd] = React.useMemo(() => {
    const toMinutes = (value?: string) => {
      if (!value) return null;
      const [h, m] = value.split(":").map(Number);
      return h * 60 + m;
    };
    return [
      (toMinutes(settings?.day_start_time) ?? 9 * 60) - 60,
      (toMinutes(settings?.day_end_time) ?? 17 * 60) + 60,
    ];
  }, [settings]);

  const totals = React.useMemo(() => {
    const days = data ?? [];
    return {
      booked: days.reduce((sum, day) => sum + day.booked_minutes, 0),
      busy: days.reduce((sum, day) => sum + day.busy_minutes, 0),
      free: days.reduce((sum, day) => sum + day.free_minutes, 0),
      faculty: new Set(days.map((day) => day.faculty_id)).size,
    };
  }, [data]);

  const byDate = React.useMemo(() => {
    const map = new Map<string, NonNullable<typeof data>>();
    (data ?? []).forEach((day) => {
      map.set(day.date, [...(map.get(day.date) ?? []), day]);
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
        <StatCard label="Free time" value={minutesToHours(totals.free)} tone="success" />
        <StatCard label="Booked" value={minutesToHours(totals.booked)} tone="brand" />
        <StatCard label="Blocked out" value={minutesToHours(totals.busy)} tone="warning" />
        <StatCard label="Faculty covered" value={totals.faculty} tone="neutral" />
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
          {byDate.map(([date, days]) => (
            <Card key={date}>
              <CardHeader>
                <CardTitle>{formatDate(date)}</CardTitle>
                <TimelineLegend />
              </CardHeader>
              <CardContent className="space-y-2.5">
                {days.map((day) => (
                  <div
                    key={`${day.faculty_id}-${day.date}`}
                    className="grid grid-cols-1 items-center gap-2 sm:grid-cols-[200px_1fr_230px]"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-xs font-medium text-slate-800">
                        {day.faculty_name}
                      </p>
                      <p className="truncate text-[10px] text-slate-400">
                        {day.department ?? day.faculty_code}
                      </p>
                    </div>
                    <FacultyTimeline
                      segments={day.segments}
                      dayStart={dayStart}
                      dayEnd={dayEnd}
                    />
                    <TimelineTotals
                      booked={day.booked_minutes}
                      busy={day.busy_minutes}
                      free={day.free_minutes}
                    />
                  </div>
                ))}
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <EmptyState
            title="No availability in this range"
            description="Import faculty availability, then recalculate to derive the free slots."
          />
        </Card>
      )}
    </div>
  );
}
