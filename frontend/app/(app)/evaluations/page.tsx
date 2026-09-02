"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Save, Trophy } from "lucide-react";
import * as React from "react";

import { MetricRadarChart } from "@/components/charts/charts";
import { usePageMeta } from "@/components/layout/page";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogFooter } from "@/components/ui/dialog";
import { Alert, EmptyState, LoadingState } from "@/components/ui/feedback";
import { Field, Input, Select } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { EmptyRow, TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import {
  useCandidates,
  useEvaluations,
  useFaculty,
  useMetrics,
  usePanels,
  useRankings,
} from "@/lib/queries";
import type { CandidateProfile, EvaluationMetric } from "@/lib/types";

export default function EvaluationsPage() {
  const { notify } = useToast();
  const client = useQueryClient();
  const { data: metrics, isLoading: metricsLoading } = useMetrics();
  const { data: evaluations, isLoading } = useEvaluations();
  const { data: rankings } = useRankings();
  const { data: candidates } = useCandidates();
  const { data: panels } = usePanels();
  const { data: faculty } = useFaculty();

  const [open, setOpen] = React.useState(false);
  const [profile, setProfile] = React.useState<CandidateProfile | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [weights, setWeights] = React.useState<Record<number, string>>({});
  const [form, setForm] = React.useState<{
    candidate_id: string;
    panel_id: string;
    evaluator_faculty_id: string;
    recommendation: string;
    remarks: string;
    scores: Record<number, string>;
  }>({
    candidate_id: "",
    panel_id: "",
    evaluator_faculty_id: "",
    recommendation: "SELECT",
    remarks: "",
    scores: {},
  });

  usePageMeta(
    "Evaluation Management",
    "Configurable metrics, weighted scoring and candidate rankings",
    <Button
      size="sm"
      onClick={() => {
        setError(null);
        setForm({
          candidate_id: "",
          panel_id: "",
          evaluator_faculty_id: "",
          recommendation: "SELECT",
          remarks: "",
          scores: Object.fromEntries((metrics ?? []).map((m) => [m.id, ""])),
        });
        setOpen(true);
      }}
    >
      <Plus className="h-3.5 w-3.5" /> Record evaluation
    </Button>,
    [metrics],
  );

  React.useEffect(() => {
    if (metrics) {
      setWeights(Object.fromEntries(metrics.map((m) => [m.id, String(m.weight)])));
    }
  }, [metrics]);

  const saveWeights = useMutation({
    mutationFn: (normalise: boolean) =>
      api.put<EvaluationMetric[]>("/evaluation-metrics", {
        normalise,
        weights: Object.entries(weights).map(([id, weight]) => ({
          metric_id: Number(id),
          weight: Number(weight) || 0,
        })),
      }),
    onSuccess: () => {
      notify("Weights saved - every evaluation was rescored.");
      client.invalidateQueries();
    },
    onError: (err: Error) => notify(err.message, "error"),
  });

  const renameMetric = useMutation({
    mutationFn: ({ id, body }: { id: number; body: Partial<EvaluationMetric> }) =>
      api.put<EvaluationMetric>(`/evaluation-metrics/${id}`, body),
    onSuccess: () => {
      notify("Metric updated.");
      client.invalidateQueries();
    },
    onError: (err: Error) => notify(err.message, "error"),
  });

  const createEvaluation = useMutation({
    mutationFn: () =>
      api.post("/evaluations", {
        candidate_id: Number(form.candidate_id),
        panel_id: form.panel_id ? Number(form.panel_id) : null,
        evaluator_faculty_id: form.evaluator_faculty_id
          ? Number(form.evaluator_faculty_id)
          : null,
        recommendation: form.recommendation,
        remarks: form.remarks || null,
        scores: Object.entries(form.scores)
          .filter(([, value]) => value !== "")
          .map(([metricId, value]) => ({
            metric_id: Number(metricId),
            raw_score: Number(value),
          })),
      }),
    onSuccess: () => {
      notify("Evaluation recorded.");
      setOpen(false);
      client.invalidateQueries();
    },
    onError: (err: Error) => setError(err.message),
  });

  async function openProfile(candidateId: number) {
    try {
      setProfile(await api.get<CandidateProfile>(
        `/evaluations/candidate/${candidateId}/profile`));
    } catch (err) {
      notify(err instanceof Error ? err.message : "No evaluation for this candidate", "error");
    }
  }

  const weightTotal = Object.values(weights).reduce(
    (sum, value) => sum + (Number(value) || 0),
    0,
  );

  return (
    <div className="space-y-4">
      <Tabs defaultValue="rankings">
        <TabsList>
          <TabsTrigger value="rankings">Rankings</TabsTrigger>
          <TabsTrigger value="evaluations">Evaluations</TabsTrigger>
          <TabsTrigger value="metrics">Metric configuration</TabsTrigger>
        </TabsList>

        <TabsContent value="rankings">
          <Card>
            <CardHeader>
              <div>
                <CardTitle>
                  <Trophy className="mr-1 inline h-3.5 w-3.5 text-[var(--color-warning)]" />
                  Candidate ranking
                </CardTitle>
                <p className="text-[11px] text-slate-400">
                  overall = Σ (metric score × weight) · click a row for the metric profile
                </p>
              </div>
            </CardHeader>
            <CardContent className="px-0 pb-0">
              <Table>
                <THead>
                  <TR>
                    <TH>#</TH>
                    <TH>Candidate</TH>
                    <TH>Department</TH>
                    {(metrics ?? []).map((metric) => (
                      <TH key={metric.id} className="whitespace-nowrap">
                        {metric.name}
                      </TH>
                    ))}
                    <TH>Overall</TH>
                    <TH>Normalised</TH>
                    <TH>Recommendation</TH>
                  </TR>
                </THead>
                <TBody>
                  {rankings?.length ? (
                    rankings.map((row) => (
                      <TR
                        key={row.candidate_id}
                        className="cursor-pointer"
                        onClick={() => openProfile(row.candidate_id)}
                      >
                        <TD className="font-semibold text-slate-500">{row.rank}</TD>
                        <TD>
                          <p className="font-medium text-slate-800">{row.candidate_name}</p>
                          <p className="text-[11px] text-slate-400">{row.candidate_code}</p>
                        </TD>
                        <TD>{row.department ?? "-"}</TD>
                        {(metrics ?? []).map((metric) => (
                          <TD key={metric.id} className="text-center">
                            {row.metric_scores[metric.metric_key] ?? "-"}
                          </TD>
                        ))}
                        <TD className="font-semibold text-slate-900">
                          {row.overall_score.toFixed(2)}
                        </TD>
                        <TD>{row.normalized_score.toFixed(1)}</TD>
                        <TD>
                          {row.recommendation ? (
                            <StatusBadge status={row.recommendation} />
                          ) : (
                            "-"
                          )}
                        </TD>
                      </TR>
                    ))
                  ) : (
                    <EmptyRow
                      colSpan={(metrics?.length ?? 0) + 6}
                      message="No evaluations recorded yet - upload the evaluation sheet or add one manually."
                    />
                  )}
                </TBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="evaluations">
          <Card>
            <CardContent className="px-0 pb-0 pt-2">
              {isLoading ? (
                <LoadingState />
              ) : (
                <Table>
                  <THead>
                    <TR>
                      <TH>Candidate</TH>
                      <TH>Scores</TH>
                      <TH>Overall</TH>
                      <TH>Normalised</TH>
                      <TH>Recommendation</TH>
                    </TR>
                  </THead>
                  <TBody>
                    {evaluations?.length ? (
                      evaluations.map((evaluation) => (
                        <TR
                          key={evaluation.id}
                          className="cursor-pointer"
                          onClick={() => openProfile(evaluation.candidate_id)}
                        >
                          <TD>
                            <p className="font-medium text-slate-800">
                              {evaluation.candidate_name}
                            </p>
                            <p className="text-[11px] text-slate-400">
                              {evaluation.candidate_code}
                            </p>
                          </TD>
                          <TD>
                            <div className="flex flex-wrap gap-1">
                              {evaluation.scores.map((score) => (
                                <span
                                  key={score.id}
                                  title={score.metric?.name}
                                  className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-600"
                                >
                                  {score.metric?.metric_key}: {score.raw_score}
                                </span>
                              ))}
                            </div>
                          </TD>
                          <TD className="font-semibold">
                            {evaluation.overall_score.toFixed(2)}
                          </TD>
                          <TD>{evaluation.normalized_score.toFixed(1)}</TD>
                          <TD>
                            {evaluation.recommendation ? (
                              <StatusBadge status={evaluation.recommendation} />
                            ) : (
                              "-"
                            )}
                          </TD>
                        </TR>
                      ))
                    ) : (
                      <EmptyRow colSpan={5} message="No evaluations recorded yet." />
                    )}
                  </TBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="metrics">
          <Card>
            <CardHeader>
              <div>
                <CardTitle>Evaluation metrics</CardTitle>
                <p className="text-[11px] text-slate-400">
                  Names, weights and ranges are configuration - the code never references a
                  metric by name
                </p>
              </div>
              <div className="flex gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => saveWeights.mutate(true)}
                  disabled={saveWeights.isPending}
                >
                  Normalise to 1.0
                </Button>
                <Button
                  size="sm"
                  onClick={() => saveWeights.mutate(false)}
                  disabled={saveWeights.isPending}
                >
                  <Save className="h-3.5 w-3.5" /> Save weights
                </Button>
              </div>
            </CardHeader>
            <CardContent className="px-0 pb-0">
              {metricsLoading ? (
                <LoadingState />
              ) : (
                <>
                  <Table>
                    <THead>
                      <TR>
                        <TH>Key</TH>
                        <TH>Name</TH>
                        <TH>Weight</TH>
                        <TH>Range</TH>
                        <TH>Active</TH>
                      </TR>
                    </THead>
                    <TBody>
                      {(metrics ?? []).map((metric) => (
                        <TR key={metric.id}>
                          <TD className="font-mono text-[11px] text-slate-500">
                            {metric.metric_key}
                          </TD>
                          <TD>
                            <Input
                              className="h-7 w-56 text-xs"
                              defaultValue={metric.name}
                              onBlur={(event) => {
                                if (event.target.value !== metric.name) {
                                  renameMetric.mutate({
                                    id: metric.id,
                                    body: { name: event.target.value },
                                  });
                                }
                              }}
                            />
                          </TD>
                          <TD>
                            <Input
                              type="number"
                              step="0.01"
                              min={0}
                              className="h-7 w-24 text-xs"
                              value={weights[metric.id] ?? ""}
                              onChange={(event) =>
                                setWeights({ ...weights, [metric.id]: event.target.value })
                              }
                            />
                          </TD>
                          <TD className="whitespace-nowrap text-[11px] text-slate-500">
                            {metric.min_score} – {metric.max_score}
                          </TD>
                          <TD>
                            <input
                              type="checkbox"
                              checked={metric.is_active}
                              onChange={(event) =>
                                renameMetric.mutate({
                                  id: metric.id,
                                  body: { is_active: event.target.checked },
                                })
                              }
                            />
                          </TD>
                        </TR>
                      ))}
                    </TBody>
                  </Table>
                  <div className="border-t border-[var(--color-border)] px-5 py-3">
                    <Badge tone={Math.abs(weightTotal - 1) < 0.001 ? "success" : "neutral"}>
                      total weight {weightTotal.toFixed(2)}
                    </Badge>
                    <span className="ml-2 text-[11px] text-slate-400">
                      Excel columns are matched against the metric key, name and aliases.
                    </span>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* ---------------------------------------------------- metric profile */}
      <Dialog open={Boolean(profile)} onOpenChange={(open) => !open && setProfile(null)}>
        {profile ? (
          <DialogContent
            title={`${profile.candidate_name} · ${profile.candidate_code}`}
            description="Normalised metric profile"
          >
            <div className="mb-3 flex flex-wrap gap-2">
              <Badge tone="brand">rank #{profile.rank ?? "-"}</Badge>
              <Badge tone="neutral">overall {profile.overall_score.toFixed(2)}</Badge>
              <Badge tone="info">normalised {profile.normalized_score.toFixed(1)}</Badge>
              {profile.strongest_metric ? (
                <Badge tone="success">strongest: {profile.strongest_metric}</Badge>
              ) : null}
              {profile.weakest_metric ? (
                <Badge tone="warning">weakest: {profile.weakest_metric}</Badge>
              ) : null}
            </div>
            <MetricRadarChart
              series={profile.candidate_name}
              data={profile.metrics.map((metric) => ({
                metric: metric.metric_name,
                value: metric.normalized_score,
                fullMark: 100,
              }))}
            />
            <Table>
              <THead>
                <TR>
                  <TH>Metric</TH>
                  <TH>Score</TH>
                  <TH>Normalised</TH>
                  <TH>Weighted</TH>
                </TR>
              </THead>
              <TBody>
                {profile.metrics.map((metric) => (
                  <TR key={metric.metric_id}>
                    <TD>{metric.metric_name}</TD>
                    <TD>
                      {metric.raw_score} / {metric.max_score}
                    </TD>
                    <TD>{metric.normalized_score.toFixed(1)}</TD>
                    <TD>{metric.weighted_score.toFixed(2)}</TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          </DialogContent>
        ) : null}
      </Dialog>

      {/* ------------------------------------------------- record evaluation */}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent
          title="Record an evaluation"
          description="Scores must fall inside each metric's configured range."
        >
          <form
            onSubmit={(event) => {
              event.preventDefault();
              createEvaluation.mutate();
            }}
          >
            {error ? (
              <Alert tone="danger" className="mb-3">
                {error}
              </Alert>
            ) : null}
            <Field label="Candidate" className="mb-3">
              <Select
                required
                value={form.candidate_id}
                onChange={(event) => setForm({ ...form, candidate_id: event.target.value })}
              >
                <option value="">Select a candidate</option>
                {(candidates ?? []).map((candidate) => (
                  <option key={candidate.id} value={candidate.id}>
                    {candidate.candidate_code} · {candidate.candidate_name}
                  </option>
                ))}
              </Select>
            </Field>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Panel">
                <Select
                  value={form.panel_id}
                  onChange={(event) => setForm({ ...form, panel_id: event.target.value })}
                >
                  <option value="">Not specified</option>
                  {(panels ?? []).map((panel) => (
                    <option key={panel.id} value={panel.id}>
                      {panel.panel_code}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Evaluator">
                <Select
                  value={form.evaluator_faculty_id}
                  onChange={(event) =>
                    setForm({ ...form, evaluator_faculty_id: event.target.value })
                  }
                >
                  <option value="">Not specified</option>
                  {(faculty ?? []).map((member) => (
                    <option key={member.id} value={member.id}>
                      {member.faculty_name}
                    </option>
                  ))}
                </Select>
              </Field>
            </div>

            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              {(metrics ?? []).map((metric) => (
                <Field
                  key={metric.id}
                  label={metric.name}
                  hint={`${metric.min_score} – ${metric.max_score} · weight ${metric.weight}`}
                >
                  <Input
                    type="number"
                    step="0.1"
                    min={metric.min_score}
                    max={metric.max_score}
                    value={form.scores[metric.id] ?? ""}
                    onChange={(event) =>
                      setForm({
                        ...form,
                        scores: { ...form.scores, [metric.id]: event.target.value },
                      })
                    }
                  />
                </Field>
              ))}
            </div>

            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <Field label="Recommendation">
                <Select
                  value={form.recommendation}
                  onChange={(event) =>
                    setForm({ ...form, recommendation: event.target.value })
                  }
                >
                  <option value="SELECT">Select</option>
                  <option value="HOLD">Hold</option>
                  <option value="REJECT">Reject</option>
                </Select>
              </Field>
              <Field label="Remarks">
                <Input
                  value={form.remarks}
                  onChange={(event) => setForm({ ...form, remarks: event.target.value })}
                />
              </Field>
            </div>

            <DialogFooter>
              <Button type="button" variant="secondary" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createEvaluation.isPending}>
                Save evaluation
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {!metrics?.length && !metricsLoading ? (
        <Card>
          <EmptyState
            title="No metrics configured"
            description="The seven default metrics are seeded on first start."
          />
        </Card>
      ) : null}
    </div>
  );
}
