"use client";

import {
  AlertTriangle,
  CalendarCheck,
  CalendarClock,
  ClipboardList,
  Percent,
  Timer,
  UserRoundX,
  Users,
  UsersRound,
} from "lucide-react";
import Link from "next/link";

import { usePageMeta } from "@/components/layout/page";
import { StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, EmptyState, ErrorState, LoadingState } from "@/components/ui/feedback";
import { StatCard } from "@/components/ui/stat-card";
import { EmptyRow, TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { useDashboard } from "@/lib/queries";
import { formatDate, formatDateTime, formatTime, minutesToHours } from "@/lib/utils";

export default function DashboardPage() {
  usePageMeta(
    "Dashboard",
    "Live view of scheduling progress, conflicts and faculty availability",
    <Button asChild size="sm">
      <Link href="/scheduler">Run scheduler</Link>
    </Button>,
  );

  const { data, isLoading, error } = useDashboard();

  if (isLoading) return <LoadingState label="Loading dashboard..." />;
  if (error) return <ErrorState error={error} />;
  if (!data) return null;

  const s = data.summary;

  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        <StatCard label="Total candidates" value={s.total_candidates} icon={Users} />
        <StatCard
          label="Scheduled"
          value={s.scheduled_candidates}
          tone="success"
          icon={CalendarCheck}
          hint={`${s.completed_interviews} completed`}
        />
        <StatCard
          label="Unscheduled"
          value={s.unscheduled_candidates}
          tone={s.unscheduled_candidates ? "warning" : "success"}
          icon={UserRoundX}
        />
        <StatCard
          label="Success rate"
          value={`${s.scheduling_success_rate}%`}
          tone="info"
          icon={Percent}
        />
        <StatCard
          label="Conflicts detected"
          value={s.conflicts_detected}
          tone={s.conflicts_detected ? "danger" : "success"}
          icon={AlertTriangle}
        />
        <StatCard label="Total faculty" value={s.total_faculty} icon={UsersRound} />
        <StatCard
          label="Faculty with free time"
          value={s.available_faculty}
          tone="success"
          icon={UsersRound}
        />
        <StatCard
          label="Panel groups"
          value={s.total_panel_groups}
          icon={ClipboardList}
        />
        <StatCard
          label="Free slots"
          value={s.available_free_slots}
          hint={`${s.free_slot_hours} hours available`}
          tone="info"
          icon={Timer}
        />
        <StatCard
          label="Evaluations recorded"
          value={s.evaluations_recorded}
          icon={ClipboardList}
          tone="neutral"
        />
      </div>

      {data.conflict_alerts.length ? (
        <Alert tone="danger" title={`${data.conflict_alerts.length} conflict(s) detected`}>
          <ul className="mt-1 list-disc space-y-0.5 pl-4">
            {data.conflict_alerts.slice(0, 4).map((conflict, index) => (
              <li key={index}>{conflict.message}</li>
            ))}
          </ul>
        </Alert>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader>
            <CardTitle>Upcoming interviews</CardTitle>
            <Button asChild variant="ghost" size="sm">
              <Link href="/schedule">View schedule</Link>
            </Button>
          </CardHeader>
          <CardContent className="px-0 pb-0">
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
                {data.upcoming_interviews.length ? (
                  data.upcoming_interviews.map((item) => (
                    <TR key={item.interview_id}>
                      <TD>
                        <p className="font-medium text-slate-800">{item.candidate_name}</p>
                        <p className="text-[11px] text-slate-400">{item.candidate_code}</p>
                      </TD>
                      <TD>{formatDate(item.date)}</TD>
                      <TD className="whitespace-nowrap">
                        {formatTime(item.start_time)} - {formatTime(item.end_time)}
                      </TD>
                      <TD>
                        <p>{item.panel_name ?? "-"}</p>
                        <p className="text-[11px] text-slate-400">
                          {item.faculty_names.join(", ")}
                        </p>
                      </TD>
                      <TD>
                        <StatusBadge status={item.status} />
                      </TD>
                    </TR>
                  ))
                ) : (
                  <EmptyRow colSpan={5} message="No upcoming interviews scheduled yet." />
                )}
              </TBody>
            </Table>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Recent scheduling activity</CardTitle>
          </CardHeader>
          <CardContent className="max-h-[420px] space-y-3 overflow-y-auto">
            {data.recent_activity.length ? (
              data.recent_activity.map((item) => (
                <div key={item.id} className="flex gap-2.5">
                  <CalendarClock className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-400" />
                  <div className="min-w-0">
                    <p className="text-xs font-medium text-slate-800">
                      {item.action.replace(/_/g, " ").toLowerCase()}
                      {item.candidate_name ? ` · ${item.candidate_name}` : ""}
                    </p>
                    {item.reason ? (
                      <p className="truncate text-[11px] text-slate-500">{item.reason}</p>
                    ) : null}
                    <p className="text-[10px] text-slate-400">
                      {formatDateTime(item.created_at)}
                    </p>
                  </div>
                </div>
              ))
            ) : (
              <EmptyState
                title="No activity yet"
                description="Scheduling actions and manual overrides appear here."
              />
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Unscheduled candidates</CardTitle>
            <Button asChild variant="ghost" size="sm">
              <Link href="/candidates">All candidates</Link>
            </Button>
          </CardHeader>
          <CardContent className="px-0 pb-0">
            <Table>
              <THead>
                <TR>
                  <TH>Candidate</TH>
                  <TH>Department</TH>
                  <TH>Reason</TH>
                </TR>
              </THead>
              <TBody>
                {data.unscheduled_candidates.length ? (
                  data.unscheduled_candidates.slice(0, 8).map((item) => (
                    <TR key={item.candidate_id}>
                      <TD>
                        <p className="font-medium text-slate-800">{item.candidate_name}</p>
                        <p className="text-[11px] text-slate-400">{item.candidate_code}</p>
                      </TD>
                      <TD>{item.department ?? "-"}</TD>
                      <TD className="text-[11px] text-slate-500">
                        {item.reason ?? "Not included in a scheduling run yet"}
                      </TD>
                    </TR>
                  ))
                ) : (
                  <EmptyRow colSpan={3} message="Every candidate has an interview." />
                )}
              </TBody>
            </Table>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Faculty availability overview</CardTitle>
            <Button asChild variant="ghost" size="sm">
              <Link href="/free-slots">Free slots</Link>
            </Button>
          </CardHeader>
          <CardContent className="px-0 pb-0">
            <Table>
              <THead>
                <TR>
                  <TH>Faculty</TH>
                  <TH>Interviews</TH>
                  <TH>Free time</TH>
                  <TH>Utilisation</TH>
                </TR>
              </THead>
              <TBody>
                {data.faculty_availability.length ? (
                  data.faculty_availability.slice(0, 8).map((item) => (
                    <TR key={item.faculty_id}>
                      <TD>
                        <p className="font-medium text-slate-800">{item.faculty_name}</p>
                        <p className="text-[11px] text-slate-400">
                          {item.department ?? item.faculty_code}
                        </p>
                      </TD>
                      <TD>{item.interviews}</TD>
                      <TD>{minutesToHours(item.free_minutes)}</TD>
                      <TD>
                        <div className="flex items-center gap-2">
                          <div className="h-1.5 w-16 overflow-hidden rounded-full bg-slate-100">
                            <div
                              className="h-full rounded-full bg-[var(--color-brand)]"
                              style={{ width: `${Math.min(100, item.utilisation)}%` }}
                            />
                          </div>
                          <span className="text-[11px] text-slate-500">
                            {item.utilisation}%
                          </span>
                        </div>
                      </TD>
                    </TR>
                  ))
                ) : (
                  <EmptyRow colSpan={4} message="No faculty availability recorded." />
                )}
              </TBody>
            </Table>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
