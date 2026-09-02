"use client";

import { CalendarCheck, CheckCircle2, Clock, MapPin, Users } from "lucide-react";
import * as React from "react";

import { usePageMeta } from "@/components/layout/page";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogFooter } from "@/components/ui/dialog";
import { Alert, EmptyState, LoadingState } from "@/components/ui/feedback";
import { Field, Input, Textarea } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import {
  useChangeRequests,
  useConfirmAttendance,
  useInterviews,
  useMyResult,
  useRequestChange,
} from "@/lib/queries";
import type { Interview } from "@/lib/types";
import { formatDate, formatTime } from "@/lib/utils";

/**
 * The candidate's own view: their slot, an attendance confirmation, a way to ask
 * for a different time, and their marks once an administrator releases them.
 * Everything here is scoped server-side to this candidate.
 */
export default function MyInterviewPage() {
  const { notify } = useToast();
  const { data: interviews, isLoading } = useInterviews({});
  const { data: result } = useMyResult();
  const { data: requests } = useChangeRequests({});
  const confirm = useConfirmAttendance();
  const requestChange = useRequestChange();

  const [open, setOpen] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [form, setForm] = React.useState({
    requested_date: "",
    requested_start_time: "",
    reason: "",
  });

  usePageMeta("My interview", "Your interview details, attendance and results");

  const interview: Interview | undefined = interviews?.[0];
  const pending = (requests ?? []).find((row) => row.status === "PENDING");

  if (isLoading) return <LoadingState label="Loading your interview..." />;

  if (!interview) {
    return (
      <EmptyState
        title="No interview scheduled yet"
        description="Once the scheduling team assigns your slot it will appear here."
      />
    );
  }

  const confirmed = Boolean(interview.candidate_confirmed_at);

  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CalendarCheck className="h-4 w-4 text-[var(--color-brand)]" />
            Your interview
          </CardTitle>
          <StatusBadge status={interview.status} />
        </CardHeader>
        <CardContent className="grid gap-4">
          <dl className="grid gap-3 sm:grid-cols-2">
            <Detail icon={<Clock className="h-3.5 w-3.5" />} label="Date">
              {interview.date ? formatDate(interview.date) : "To be confirmed"}
            </Detail>
            <Detail icon={<Clock className="h-3.5 w-3.5" />} label="Time">
              {interview.start_time
                ? `${formatTime(interview.start_time)} - ${formatTime(interview.end_time ?? "")}`
                : "To be confirmed"}
            </Detail>
            <Detail icon={<Users className="h-3.5 w-3.5" />} label="Panel">
              {interview.panel?.panel_name ?? "To be confirmed"}
            </Detail>
            <Detail icon={<MapPin className="h-3.5 w-3.5" />} label="Venue">
              {interview.location ?? "To be confirmed"}
            </Detail>
          </dl>

          {confirmed ? (
            <Alert tone="success">
              <CheckCircle2 className="mr-1 inline h-3.5 w-3.5" />
              You confirmed your attendance on{" "}
              {formatDate(interview.candidate_confirmed_at as string)}.
            </Alert>
          ) : (
            <Alert tone="warning">
              Please confirm you can attend this slot, or request a different time.
            </Alert>
          )}

          {pending ? (
            <Alert tone="info">
              Your reschedule request is awaiting a decision
              {pending.requested_date
                ? ` (asked for ${formatDate(pending.requested_date)}${
                    pending.requested_start_time
                      ? ` at ${formatTime(pending.requested_start_time)}`
                      : ""
                  })`
                : ""}
              .
            </Alert>
          ) : null}

          <div className="flex flex-wrap gap-2">
            <Button
              onClick={() =>
                confirm.mutate(interview.id, {
                  onSuccess: () => notify("Attendance confirmed."),
                  onError: (err: Error) => notify(err.message, "error"),
                })
              }
              disabled={confirmed || confirm.isPending}
            >
              {confirmed ? "Attendance confirmed" : "Confirm attendance"}
            </Button>
            <Button
              variant="secondary"
              onClick={() => {
                setError(null);
                setOpen(true);
              }}
              disabled={Boolean(pending)}
            >
              Request a different time
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>My result</CardTitle>
        </CardHeader>
        <CardContent>
          {!result?.published ? (
            <p className="text-xs text-slate-500">
              {result?.message ?? "Your results have not been released yet."}
            </p>
          ) : !result.profile ? (
            <p className="text-xs text-slate-500">{result.message}</p>
          ) : (
            <div className="grid gap-2">
              <div className="flex items-baseline justify-between">
                <span className="text-xs text-slate-500">Overall</span>
                <span className="text-lg font-semibold tabular-nums text-slate-900">
                  {result.profile.overall_score.toFixed(2)}
                </span>
              </div>
              <p className="text-[11px] text-slate-400">
                Compiled from {result.profile.evaluator_count} evaluator
                {result.profile.evaluator_count === 1 ? "" : "s"}
              </p>
              <div className="mt-1 grid gap-1.5">
                {(result.profile.metrics as Record<string, never>[]).map((metric) => (
                  <div
                    key={String(metric.metric_key)}
                    className="flex items-center justify-between gap-2 text-xs"
                  >
                    <span className="truncate text-slate-600">
                      {String(metric.metric_name)}
                    </span>
                    <span className="tabular-nums font-medium text-slate-900">
                      {Number(metric.raw_score).toFixed(1)} / {String(metric.max_score)}
                    </span>
                  </div>
                ))}
              </div>
              {result.profile.strongest_metric ? (
                <Badge tone="success" className="mt-2 w-fit">
                  Strongest: {result.profile.strongest_metric}
                </Badge>
              ) : null}
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent
          title="Request a different time"
          description="The scheduling team will review your request."
        >
          <form
            onSubmit={(event) => {
              event.preventDefault();
              requestChange.mutate(
                {
                  id: interview.id,
                  body: {
                    requested_date: form.requested_date || null,
                    requested_start_time: form.requested_start_time || null,
                    reason: form.reason || null,
                  },
                },
                {
                  onSuccess: () => {
                    notify("Request submitted.");
                    setOpen(false);
                    setForm({ requested_date: "", requested_start_time: "", reason: "" });
                  },
                  onError: (err: Error) => setError(err.message),
                },
              );
            }}
          >
            {error ? (
              <Alert tone="danger" className="mb-3">
                {error}
              </Alert>
            ) : null}
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Preferred date">
                <Input
                  type="date"
                  value={form.requested_date}
                  onChange={(event) =>
                    setForm((state) => ({ ...state, requested_date: event.target.value }))
                  }
                />
              </Field>
              <Field label="Preferred start time">
                <Input
                  type="time"
                  value={form.requested_start_time}
                  onChange={(event) =>
                    setForm((state) => ({
                      ...state,
                      requested_start_time: event.target.value,
                    }))
                  }
                />
              </Field>
            </div>
            <Field label="Reason" className="mt-3">
              <Textarea
                rows={3}
                required
                value={form.reason}
                placeholder="Why do you need a different slot?"
                onChange={(event) =>
                  setForm((state) => ({ ...state, reason: event.target.value }))
                }
              />
            </Field>
            <DialogFooter>
              <Button type="button" variant="secondary" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={requestChange.isPending}>
                {requestChange.isPending ? "Sending..." : "Send request"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function Detail({
  icon,
  label,
  children,
}: {
  icon: React.ReactNode;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <dt className="flex items-center gap-1.5 text-[11px] uppercase tracking-wide text-slate-400">
        {icon}
        {label}
      </dt>
      <dd className="mt-0.5 text-sm font-medium text-slate-900">{children}</dd>
    </div>
  );
}
