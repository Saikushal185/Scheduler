"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Eye, EyeOff, Save } from "lucide-react";
import * as React from "react";

import { usePageMeta } from "@/components/layout/page";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, LoadingState } from "@/components/ui/feedback";
import { Field, Input, Select } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { useAlgorithms, useSettings } from "@/lib/queries";
import type { InterviewSettings } from "@/lib/types";
import { formatDateTime } from "@/lib/utils";

export default function SettingsPage() {
  const { notify } = useToast();
  const client = useQueryClient();
  const { data, isLoading } = useSettings();
  const { data: algorithms } = useAlgorithms();
  const [form, setForm] = React.useState<InterviewSettings | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  usePageMeta("Settings", "Global scheduling configuration used by the engine");

  React.useEffect(() => {
    if (data) setForm(data);
  }, [data]);

  const save = useMutation({
    mutationFn: (payload: InterviewSettings) =>
      api.put<InterviewSettings>("/settings", {
        interview_duration_minutes: Number(payload.interview_duration_minutes),
        break_duration_minutes: Number(payload.break_duration_minutes),
        day_start_time: payload.day_start_time.slice(0, 5),
        day_end_time: payload.day_end_time.slice(0, 5),
        schedule_start_date: payload.schedule_start_date || null,
        schedule_end_date: payload.schedule_end_date || null,
        slot_granularity_minutes: Number(payload.slot_granularity_minutes),
        min_panel_size: Number(payload.min_panel_size),
        max_panel_size: Number(payload.max_panel_size),
        max_interviews_per_faculty_per_day: Number(
          payload.max_interviews_per_faculty_per_day,
        ),
        allow_weekends: payload.allow_weekends,
        default_algorithm: payload.default_algorithm,
        organisation_name: payload.organisation_name,
      }),
    onSuccess: () => {
      notify("Settings saved.");
      client.invalidateQueries();
    },
    onError: (err: Error) => setError(err.message),
  });

  // Releasing results is deliberately its own action rather than a field on the
  // settings form: it makes marks visible to every candidate at once, and that
  // should not happen as a side effect of editing an interview duration.
  const publish = useMutation({
    mutationFn: (next: boolean) =>
      api.put<InterviewSettings>("/settings", { results_published: next }),
    onSuccess: (result) => {
      notify(
        result.results_published
          ? "Results released. Candidates can now see their own marks."
          : "Results hidden from candidates again.",
      );
      client.invalidateQueries();
    },
    onError: (err: Error) => notify(err.message, "error"),
  });

  if (isLoading || !form) return <LoadingState />;

  const update = (patch: Partial<InterviewSettings>) =>
    setForm({ ...form, ...patch } as InterviewSettings);

  return (
    <form
      className="max-w-4xl space-y-4"
      onSubmit={(event) => {
        event.preventDefault();
        setError(null);
        save.mutate(form);
      }}
    >
      {error ? (
        <Alert tone="danger" title="Could not save settings">
          {error}
        </Alert>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Interview timing</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Field label="Interview duration (minutes)">
            <Input
              type="number"
              min={5}
              max={480}
              value={form.interview_duration_minutes}
              onChange={(event) =>
                update({ interview_duration_minutes: Number(event.target.value) })
              }
            />
          </Field>
          <Field label="Break between interviews (minutes)" hint="Enforced per faculty">
            <Input
              type="number"
              min={0}
              max={240}
              value={form.break_duration_minutes}
              onChange={(event) =>
                update({ break_duration_minutes: Number(event.target.value) })
              }
            />
          </Field>
          <Field label="Slot granularity (minutes)" hint="Start positions tried per window">
            <Input
              type="number"
              min={5}
              max={120}
              value={form.slot_granularity_minutes}
              onChange={(event) =>
                update({ slot_granularity_minutes: Number(event.target.value) })
              }
            />
          </Field>
          <Field label="Day starts at">
            <Input
              type="time"
              value={form.day_start_time.slice(0, 5)}
              onChange={(event) => update({ day_start_time: event.target.value })}
            />
          </Field>
          <Field label="Day ends at">
            <Input
              type="time"
              value={form.day_end_time.slice(0, 5)}
              onChange={(event) => update({ day_end_time: event.target.value })}
            />
          </Field>
          <Field label="Weekends">
            <Select
              value={form.allow_weekends ? "yes" : "no"}
              onChange={(event) => update({ allow_weekends: event.target.value === "yes" })}
            >
              <option value="no">Skip weekends</option>
              <option value="yes">Allow weekend interviews</option>
            </Select>
          </Field>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Scheduling window and limits</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Field label="Schedule from">
            <Input
              type="date"
              value={form.schedule_start_date ?? ""}
              onChange={(event) => update({ schedule_start_date: event.target.value })}
            />
          </Field>
          <Field label="Schedule to">
            <Input
              type="date"
              value={form.schedule_end_date ?? ""}
              onChange={(event) => update({ schedule_end_date: event.target.value })}
            />
          </Field>
          <Field label="Max interviews per faculty per day">
            <Input
              type="number"
              min={1}
              max={50}
              value={form.max_interviews_per_faculty_per_day}
              onChange={(event) =>
                update({ max_interviews_per_faculty_per_day: Number(event.target.value) })
              }
            />
          </Field>
          <Field label="Minimum panel size">
            <Input
              type="number"
              min={1}
              max={20}
              value={form.min_panel_size}
              onChange={(event) => update({ min_panel_size: Number(event.target.value) })}
            />
          </Field>
          <Field label="Maximum panel size">
            <Input
              type="number"
              min={1}
              max={20}
              value={form.max_panel_size}
              onChange={(event) => update({ max_panel_size: Number(event.target.value) })}
            />
          </Field>
          <Field label="Default algorithm">
            <Select
              value={form.default_algorithm}
              onChange={(event) => update({ default_algorithm: event.target.value })}
            >
              {(algorithms ?? []).map((algorithm) => (
                <option key={algorithm.name} value={algorithm.name}>
                  {algorithm.name}
                </option>
              ))}
            </Select>
          </Field>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Candidate results</CardTitle>
          <Badge tone={data?.results_published ? "success" : "neutral"}>
            {data?.results_published ? "Released" : "Not released"}
          </Badge>
        </CardHeader>
        <CardContent className="grid gap-3">
          <p className="text-xs text-slate-500">
            Candidates only see their own compiled marks once released, so a
            teacher&apos;s part-finished entry is never visible. Rankings and other
            candidates stay hidden either way.
          </p>
          {data?.results_published ? (
            <Alert tone="success">
              Released
              {data.results_published_at
                ? ` on ${formatDateTime(data.results_published_at)}`
                : ""}
              . Every candidate with an account can see their own result.
            </Alert>
          ) : (
            <Alert tone="warning">
              Marks are being collected. Candidates cannot see anything yet.
            </Alert>
          )}
          <div>
            <Button
              type="button"
              variant={data?.results_published ? "secondary" : "default"}
              disabled={publish.isPending}
              onClick={() => publish.mutate(!data?.results_published)}
            >
              {data?.results_published ? (
                <>
                  <EyeOff className="h-3.5 w-3.5" /> Hide results again
                </>
              ) : (
                <>
                  <Eye className="h-3.5 w-3.5" /> Release results to candidates
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Organisation</CardTitle>
        </CardHeader>
        <CardContent>
          <Field label="Organisation name" className="max-w-md">
            <Input
              value={form.organisation_name}
              onChange={(event) => update({ organisation_name: event.target.value })}
            />
          </Field>
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button type="submit" disabled={save.isPending}>
          <Save className="h-3.5 w-3.5" />
          {save.isPending ? "Saving..." : "Save settings"}
        </Button>
      </div>
    </form>
  );
}
