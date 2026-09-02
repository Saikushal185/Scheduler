"use client";

import * as React from "react";

import {
  FacultyTimeline,
  TimelineLegend,
  TimelineTotals,
} from "@/components/faculty-timeline";
import { usePageMeta } from "@/components/layout/page";
import { StatusBadge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/feedback";
import { Field, Input } from "@/components/ui/input";
import { StatCard } from "@/components/ui/stat-card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useFacultyTimeline, useInterviews, useSettings } from "@/lib/queries";
import { addDaysISO, formatDate, formatTime, minutesToHours, todayISO } from "@/lib/utils";

/**
 * A faculty member's own view. Every request here is scoped server-side to the
 * signed-in faculty record, so this is their panels and their diary only.
 */
export default function MySchedulePage() {
  const [startDate, setStartDate] = React.useState(todayISO());
  const [endDate, setEndDate] = React.useState(addDaysISO(todayISO(), 13));

  const { data: settings } = useSettings();
  const {
    data: interviews,
    isLoading,
    error,
  } = useInterviews({ start_date: startDate, end_date: endDate });
  const { data: timeline } = useFacultyTimeline({
    start_date: startDate,
    end_date: endDate,
  });

  usePageMeta("My schedule", "Your interviews and your availability");

  // Drive the timeline window from the configured working day rather than a
  // hardcoded range, so the bars line up with what the scheduler actually uses.
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

  const upcoming = (interviews ?? []).filter((row) => row.date);
  const totals = (timeline ?? []).reduce(
    (acc, day) => ({
      booked: acc.booked + day.booked_minutes,
      busy: acc.busy + day.busy_minutes,
      free: acc.free + day.free_minutes,
    }),
    { booked: 0, busy: 0, free: 0 },
  );

  if (error) return <ErrorState error={error} />;

  return (
    <div className="grid gap-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="My interviews" value={upcoming.length} tone="brand" />
        <StatCard label="Booked" value={minutesToHours(totals.booked)} tone="brand" />
        <StatCard label="Blocked out" value={minutesToHours(totals.busy)} tone="warning" />
        <StatCard label="Still free" value={minutesToHours(totals.free)} tone="success" />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Date range</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 sm:grid-cols-2 lg:max-w-md">
            <Field label="From">
              <Input
                type="date"
                value={startDate}
                onChange={(event) => setStartDate(event.target.value)}
              />
            </Field>
            <Field label="To">
              <Input
                type="date"
                value={endDate}
                onChange={(event) => setEndDate(event.target.value)}
              />
            </Field>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>My availability</CardTitle>
          <TimelineLegend />
        </CardHeader>
        <CardContent>
          {!timeline?.length ? (
            <EmptyState
              title="No availability declared"
              description="Declare availability windows so the scheduler can use your time."
            />
          ) : (
            <div className="grid gap-2.5">
              {timeline.map((day) => (
                <div
                  key={`${day.faculty_id}-${day.date}`}
                  className="grid items-center gap-3 lg:grid-cols-[130px_1fr_220px]"
                >
                  <p className="text-xs font-medium text-slate-700">
                    {formatDate(day.date)}
                  </p>
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
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>My interviews</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <LoadingState />
          ) : !upcoming.length ? (
            <EmptyState
              title="Nothing scheduled in this range"
              description="Interviews you are on the panel for will appear here."
            />
          ) : (
            <Table>
              <THead>
                <TR>
                  <TH>Candidate</TH>
                  <TH>Date</TH>
                  <TH>Time</TH>
                  <TH>Panel</TH>
                  <TH>Status</TH>
                </TR>
              </THead>
              <TBody>
                {upcoming.map((row) => (
                  <TR key={row.id}>
                    <TD className="font-medium text-slate-900">
                      {row.candidate?.candidate_name ?? row.schedule_code}
                    </TD>
                    <TD>{row.date ? formatDate(row.date) : "-"}</TD>
                    <TD className="tabular-nums">
                      {row.start_time
                        ? `${formatTime(row.start_time)} - ${formatTime(row.end_time ?? "")}`
                        : "-"}
                    </TD>
                    <TD>{row.panel?.panel_name ?? "-"}</TD>
                    <TD>
                      <StatusBadge status={row.status} />
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
