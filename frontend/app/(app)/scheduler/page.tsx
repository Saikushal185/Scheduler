"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Play, Settings2, TriangleAlert } from "lucide-react";
import * as React from "react";

import { usePageMeta } from "@/components/layout/page";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, EmptyState, LoadingState } from "@/components/ui/feedback";
import { Field, Input, Select } from "@/components/ui/input";
import { StatCard } from "@/components/ui/stat-card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { EmptyRow, TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import {
  useAlgorithms,
  useConfirmRun,
  useConstraints,
  useGenerateSchedule,
  useRuns,
  useSettings,
} from "@/lib/queries";
import type { SchedulePreview, SchedulingConstraint } from "@/lib/types";
import { formatDate, formatTime } from "@/lib/utils";

const PRIORITIES = ["HARD", "HIGH", "MEDIUM", "LOW", "FLEXIBLE"];

export default function SchedulerPage() {
  const { notify } = useToast();
  const client = useQueryClient();
  const { data: settings } = useSettings();
  const { data: algorithms } = useAlgorithms();
  const { data: constraints } = useConstraints();
  const { data: runs } = useRuns();
  const generate = useGenerateSchedule();
  const confirm = useConfirmRun();

  const [preview, setPreview] = React.useState<SchedulePreview | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [params, setParams] = React.useState({
    start_date: "",
    end_date: "",
    algorithm: "",
    interview_duration_minutes: "",
    break_duration_minutes: "",
    max_interviews_per_faculty_per_day: "",
    keep_locked_interviews: true,
  });

  usePageMeta(
    "Automated Scheduler",
    "Constraint-based engine: hard rules filter, soft priorities are optimised",
  );

  React.useEffect(() => {
    if (settings && !params.algorithm) {
      setParams((current) => ({
        ...current,
        algorithm: settings.default_algorithm,
        start_date: settings.schedule_start_date ?? "",
        end_date: settings.schedule_end_date ?? "",
        interview_duration_minutes: String(settings.interview_duration_minutes),
        break_duration_minutes: String(settings.break_duration_minutes),
        max_interviews_per_faculty_per_day: String(
          settings.max_interviews_per_faculty_per_day,
        ),
      }));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [settings]);

  const updateConstraint = useMutation({
    mutationFn: ({ id, body }: { id: number; body: Partial<SchedulingConstraint> }) =>
      api.put<SchedulingConstraint>(`/constraints/${id}`, body),
    onSuccess: () => {
      notify("Constraint updated.");
      client.invalidateQueries({ queryKey: ["constraints"] });
    },
    onError: (err: Error) => notify(err.message, "error"),
  });

  function runScheduler() {
    setError(null);
    const body: Record<string, unknown> = {
      keep_locked_interviews: params.keep_locked_interviews,
    };
    if (params.start_date) body.start_date = params.start_date;
    if (params.end_date) body.end_date = params.end_date;
    if (params.algorithm) body.algorithm = params.algorithm;
    if (params.interview_duration_minutes)
      body.interview_duration_minutes = Number(params.interview_duration_minutes);
    if (params.break_duration_minutes !== "")
      body.break_duration_minutes = Number(params.break_duration_minutes);
    if (params.max_interviews_per_faculty_per_day)
      body.max_interviews_per_faculty_per_day = Number(
        params.max_interviews_per_faculty_per_day,
      );

    generate.mutate(body, {
      onSuccess: (result) => {
        setPreview(result);
        notify(
          `Run ${result.run_code}: ${result.scheduled.length} scheduled, ${result.unscheduled.length} unscheduled.`,
          result.unscheduled.length ? "error" : "success",
        );
      },
      onError: (err: Error) => {
        setError(err.message);
        notify(err.message, "error");
      },
    });
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <div>
            <CardTitle>Scheduling parameters</CardTitle>
            <p className="text-[11px] text-slate-400">
              Leave a field empty to use the value from Settings
            </p>
          </div>
          <Button size="sm" onClick={runScheduler} disabled={generate.isPending}>
            <Play className="h-3.5 w-3.5" />
            {generate.isPending ? "Scheduling..." : "Generate schedule"}
          </Button>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Field label="From date">
              <Input
                type="date"
                value={params.start_date}
                onChange={(event) =>
                  setParams({ ...params, start_date: event.target.value })
                }
              />
            </Field>
            <Field label="To date">
              <Input
                type="date"
                value={params.end_date}
                onChange={(event) => setParams({ ...params, end_date: event.target.value })}
              />
            </Field>
            <Field label="Algorithm" hint="The strategy is pluggable">
              <Select
                value={params.algorithm}
                onChange={(event) => setParams({ ...params, algorithm: event.target.value })}
              >
                {(algorithms ?? []).map((algorithm) => (
                  <option key={algorithm.name} value={algorithm.name}>
                    {algorithm.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Interview duration (min)">
              <Input
                type="number"
                min={5}
                max={480}
                value={params.interview_duration_minutes}
                onChange={(event) =>
                  setParams({ ...params, interview_duration_minutes: event.target.value })
                }
              />
            </Field>
            <Field label="Break between interviews (min)">
              <Input
                type="number"
                min={0}
                max={240}
                value={params.break_duration_minutes}
                onChange={(event) =>
                  setParams({ ...params, break_duration_minutes: event.target.value })
                }
              />
            </Field>
            <Field label="Max interviews / faculty / day">
              <Input
                type="number"
                min={1}
                max={50}
                value={params.max_interviews_per_faculty_per_day}
                onChange={(event) =>
                  setParams({
                    ...params,
                    max_interviews_per_faculty_per_day: event.target.value,
                  })
                }
              />
            </Field>
            <Field label="Locked interviews">
              <Select
                value={params.keep_locked_interviews ? "keep" : "replan"}
                onChange={(event) =>
                  setParams({
                    ...params,
                    keep_locked_interviews: event.target.value === "keep",
                  })
                }
              >
                <option value="keep">Keep locked interviews in place</option>
                <option value="replan">Re-plan everything</option>
              </Select>
            </Field>
          </div>

          {algorithms?.length ? (
            <p className="mt-3 text-[11px] text-slate-500">
              {algorithms.find((a) => a.name === params.algorithm)?.description}
            </p>
          ) : null}

          {error ? (
            <Alert tone="danger" title="Scheduling failed" className="mt-3">
              {error}
            </Alert>
          ) : null}
        </CardContent>
      </Card>

      {generate.isPending ? <LoadingState label="Running the scheduling engine..." /> : null}

      {preview ? (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <StatCard
              label="Scheduled"
              value={preview.scheduled.length}
              tone="success"
              icon={CheckCircle2}
            />
            <StatCard
              label="Unscheduled"
              value={preview.unscheduled.length}
              tone={preview.unscheduled.length ? "warning" : "success"}
              icon={TriangleAlert}
            />
            <StatCard label="Success rate" value={`${preview.success_rate}%`} tone="info" />
            <StatCard
              label="Optimisation score"
              value={Math.round(preview.total_score).toLocaleString()}
              tone="brand"
            />
            <StatCard
              label="Solve time"
              value={`${preview.duration_ms} ms`}
              tone="neutral"
              hint={`${String(preview.statistics.feasible_combinations ?? "-")} combinations`}
            />
          </div>

          <Card>
            <CardHeader>
              <div>
                <CardTitle>
                  Preview · {preview.run_code}{" "}
                  <Badge tone="brand">{preview.algorithm}</Badge>
                </CardTitle>
                <p className="text-[11px] text-slate-400">
                  Nothing is saved until you confirm this run
                </p>
              </div>
              <div className="flex gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => {
                    api
                      .post(`/scheduling/runs/${preview.run_id}/discard`)
                      .then(() => {
                        setPreview(null);
                        notify("Preview discarded.");
                        client.invalidateQueries({ queryKey: ["runs"] });
                      })
                      .catch((err: Error) => notify(err.message, "error"));
                  }}
                >
                  Discard
                </Button>
                <Button
                  size="sm"
                  disabled={confirm.isPending || !preview.scheduled.length}
                  onClick={() =>
                    confirm.mutate(preview.run_id, {
                      onSuccess: (result) => {
                        notify(
                          `Confirmed: ${result.interviews_created} interview(s) created.`,
                        );
                        setPreview(null);
                      },
                      onError: (err: Error) => notify(err.message, "error"),
                    })
                  }
                >
                  {confirm.isPending ? "Confirming..." : "Confirm schedule"}
                </Button>
              </div>
            </CardHeader>
            <CardContent className="px-0 pb-0">
              <Tabs defaultValue="scheduled">
                <div className="px-5">
                  <TabsList>
                    <TabsTrigger value="scheduled">
                      Scheduled ({preview.scheduled.length})
                    </TabsTrigger>
                    <TabsTrigger value="unscheduled">
                      Unscheduled ({preview.unscheduled.length})
                    </TabsTrigger>
                    <TabsTrigger value="conflicts">
                      Conflicts ({preview.conflicts.length})
                    </TabsTrigger>
                    <TabsTrigger value="why">Why this schedule</TabsTrigger>
                  </TabsList>
                </div>

                <TabsContent value="scheduled" className="mt-3">
                  <Table>
                    <THead>
                      <TR>
                        <TH>Candidate</TH>
                        <TH>Date</TH>
                        <TH>Time</TH>
                        <TH>Panel</TH>
                        <TH>Faculty</TH>
                        <TH>Score</TH>
                        <TH>Priorities satisfied</TH>
                      </TR>
                    </THead>
                    <TBody>
                      {preview.scheduled.map((item) => (
                        <TR key={item.candidate_id}>
                          <TD>
                            <p className="font-medium text-slate-800">
                              {item.candidate_name}
                            </p>
                            <p className="text-[11px] text-slate-400">
                              {item.candidate_code}
                            </p>
                          </TD>
                          <TD>{formatDate(item.date)}</TD>
                          <TD className="whitespace-nowrap">
                            {formatTime(item.start_time)} - {formatTime(item.end_time)}
                          </TD>
                          <TD>{item.panel_code}</TD>
                          <TD className="text-[11px] text-slate-500">
                            {item.faculty_names.join(", ")}
                          </TD>
                          <TD>{Math.round(item.scheduling_score)}</TD>
                          <TD>
                            <div className="flex flex-wrap gap-1">
                              {item.priority_info
                                .filter((info) => info.priority !== "HARD")
                                .slice(0, 4)
                                .map((info, index) => (
                                  <span
                                    key={index}
                                    title={info.detail}
                                    className={`rounded px-1.5 py-0.5 text-[10px] ${
                                      info.satisfied && info.score > 0
                                        ? "bg-[var(--color-success-light)] text-[var(--color-success)]"
                                        : "bg-slate-100 text-slate-500"
                                    }`}
                                  >
                                    {info.type.replace(/_/g, " ").toLowerCase()}
                                  </span>
                                ))}
                            </div>
                          </TD>
                        </TR>
                      ))}
                    </TBody>
                  </Table>
                </TabsContent>

                <TabsContent value="unscheduled" className="mt-3">
                  <Table>
                    <THead>
                      <TR>
                        <TH>Candidate</TH>
                        <TH>Reason</TH>
                        <TH>Details</TH>
                      </TR>
                    </THead>
                    <TBody>
                      {preview.unscheduled.length ? (
                        preview.unscheduled.map((item) => (
                          <TR key={item.candidate_id}>
                            <TD>
                              <p className="font-medium text-slate-800">
                                {item.candidate_name}
                              </p>
                              <p className="text-[11px] text-slate-400">
                                {item.candidate_code}
                              </p>
                            </TD>
                            <TD className="text-[var(--color-warning)]">{item.reason}</TD>
                            <TD className="text-[11px] text-slate-500">
                              <ul className="list-disc pl-4">
                                {item.details.map((detail, index) => (
                                  <li key={index}>{detail}</li>
                                ))}
                              </ul>
                            </TD>
                          </TR>
                        ))
                      ) : (
                        <EmptyRow colSpan={3} message="Every candidate was scheduled." />
                      )}
                    </TBody>
                  </Table>
                </TabsContent>

                <TabsContent value="conflicts" className="mt-3 px-5 pb-5">
                  {preview.conflicts.length ? (
                    <div className="space-y-2">
                      {preview.conflicts.map((conflict, index) => (
                        <Alert key={index} tone="danger" title={conflict.kind}>
                          {conflict.message}
                        </Alert>
                      ))}
                    </div>
                  ) : (
                    <Alert tone="success" title="No conflicts">
                      The generated schedule passed independent verification: no candidate,
                      faculty or panel is double-booked and every break is respected.
                    </Alert>
                  )}
                </TabsContent>

                <TabsContent value="why" className="mt-3 px-5 pb-5">
                  <Explanation statistics={preview.statistics} />
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>
        </>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Flexible scheduling rules</CardTitle>
              <p className="text-[11px] text-slate-400">
                HARD rules filter combinations; the rest are optimised by weight
              </p>
            </div>
            <Settings2 className="h-4 w-4 text-slate-400" />
          </CardHeader>
          <CardContent className="px-0 pb-0">
            <Table>
              <THead>
                <TR>
                  <TH>Rule</TH>
                  <TH>Priority</TH>
                  <TH>Active</TH>
                </TR>
              </THead>
              <TBody>
                {(constraints ?? []).map((constraint) => (
                  <TR key={constraint.id}>
                    <TD>
                      <p className="font-medium text-slate-800">{constraint.name}</p>
                      <p className="text-[11px] text-slate-400">
                        {constraint.description ?? constraint.constraint_type}
                      </p>
                    </TD>
                    <TD>
                      <Select
                        className="h-7 w-28 text-[11px]"
                        value={constraint.priority}
                        onChange={(event) =>
                          updateConstraint.mutate({
                            id: constraint.id,
                            body: { priority: event.target.value as never },
                          })
                        }
                      >
                        {PRIORITIES.map((priority) => (
                          <option key={priority} value={priority}>
                            {priority}
                          </option>
                        ))}
                      </Select>
                    </TD>
                    <TD>
                      <input
                        type="checkbox"
                        checked={constraint.is_active}
                        onChange={(event) =>
                          updateConstraint.mutate({
                            id: constraint.id,
                            body: { is_active: event.target.checked },
                          })
                        }
                      />
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Recent scheduling runs</CardTitle>
          </CardHeader>
          <CardContent className="px-0 pb-0">
            <Table>
              <THead>
                <TR>
                  <TH>Run</TH>
                  <TH>Algorithm</TH>
                  <TH>Status</TH>
                  <TH>Scheduled</TH>
                  <TH>Unscheduled</TH>
                  <TH>Time</TH>
                </TR>
              </THead>
              <TBody>
                {runs?.length ? (
                  runs.map((run) => (
                    <TR key={run.id}>
                      <TD className="font-medium text-slate-800">{run.run_code}</TD>
                      <TD>{run.algorithm}</TD>
                      <TD>
                        <StatusBadge status={run.status} />
                      </TD>
                      <TD>{run.scheduled_count}</TD>
                      <TD>{run.unscheduled_count}</TD>
                      <TD>{run.duration_ms} ms</TD>
                    </TR>
                  ))
                ) : (
                  <EmptyRow colSpan={6} message="No scheduling runs yet." />
                )}
              </TBody>
            </Table>
          </CardContent>
        </Card>
      </div>

      {!preview && !generate.isPending ? (
        <Card>
          <EmptyState
            title="Ready to schedule"
            description="The engine loads candidates, faculty free slots and panels, removes every combination that breaks a hard constraint, scores the rest against your soft priorities and returns a conflict-free schedule you can review before saving."
          />
        </Card>
      ) : null}
    </div>
  );
}

type SatisfactionRow = {
  type: string;
  priority: string;
  satisfied: number;
  violated: number;
  satisfaction_rate: number;
  score_awarded: number;
  score_forgone: number;
};

/**
 * What the run traded away, so the schedule can be defended rather than just
 * accepted. Constraints are ordered by score forfeited, which is the useful
 * ranking: it puts the preference that cost the most at the top.
 */
function Explanation({ statistics }: { statistics: Record<string, unknown> }) {
  const rows = (statistics.constraint_satisfaction ?? []) as SatisfactionRow[];
  const num = (key: string) =>
    typeof statistics[key] === "number" ? (statistics[key] as number) : null;

  const seedScheduled = num("seed_scheduled");
  const finalScheduled = num("final_scheduled");
  const scoreGain = num("score_gain");
  const scheduledGain = num("scheduled_gain");
  const optimised = seedScheduled !== null && finalScheduled !== null;

  return (
    <div className="grid gap-4">
      {optimised ? (
        <div className="rounded-lg border border-[var(--color-border)] p-3">
          <p className="mb-2 text-xs font-medium text-slate-700">
            Improvement pass
          </p>
          {scheduledGain === 0 && (scoreGain ?? 0) === 0 ? (
            <p className="text-xs text-slate-500">
              The first solution was already a local optimum for the moves
              available, so nothing changed. This is normal when there is
              slack in the timetable and everyone already fits.
            </p>
          ) : (
            <p className="text-xs text-slate-600">
              Improved the first solution from {seedScheduled} to {finalScheduled}{" "}
              scheduled
              {scoreGain ? `, gaining ${Math.round(scoreGain).toLocaleString()} score` : ""}
              .
            </p>
          )}
          <div className="mt-2 flex flex-wrap gap-3 text-[11px] text-slate-500 tabular-nums">
            <span>{String(statistics.insertion_moves ?? 0)} insertions</span>
            <span>{String(statistics.relocation_moves ?? 0)} relocations</span>
            <span>{String(statistics.swap_moves ?? 0)} swaps</span>
            <span>{String(statistics.improvement_passes ?? 0)} passes</span>
          </div>
        </div>
      ) : null}

      {rows.length ? (
        <div>
          <p className="mb-2 text-xs font-medium text-slate-700">
            Constraints, by score given up
          </p>
          <Table>
            <THead>
              <TR>
                <TH>Constraint</TH>
                <TH>Priority</TH>
                <TH className="text-right">Met</TH>
                <TH className="text-right">Missed</TH>
                <TH className="text-right">Satisfied</TH>
                <TH className="text-right">Score forfeited</TH>
              </TR>
            </THead>
            <TBody>
              {rows.map((row) => (
                <TR key={row.type}>
                  <TD className="font-medium text-slate-900">
                    {row.type.replaceAll("_", " ").toLowerCase()}
                  </TD>
                  <TD>
                    <Badge tone={row.priority === "HARD" ? "danger" : "neutral"}>
                      {row.priority}
                    </Badge>
                  </TD>
                  <TD className="text-right tabular-nums">{row.satisfied}</TD>
                  <TD className="text-right tabular-nums">{row.violated}</TD>
                  <TD className="text-right tabular-nums">
                    {row.satisfaction_rate}%
                  </TD>
                  <TD className="text-right tabular-nums">
                    {row.score_forgone
                      ? Math.round(row.score_forgone).toLocaleString()
                      : "-"}
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
          <p className="mt-2 text-[11px] text-slate-400">
            Forfeited score is measured against the best any placement in this run
            achieved for that constraint. A hard constraint below 100% would mean
            the schedule is invalid - none should ever appear here.
          </p>
        </div>
      ) : (
        <Alert tone="info">
          This run produced no constraint breakdown. Re-run with the optimised
          algorithm to see what the schedule traded away.
        </Alert>
      )}
    </div>
  );
}
