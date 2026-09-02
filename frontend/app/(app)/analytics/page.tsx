"use client";

import { Download } from "lucide-react";
import * as React from "react";

import {
  DistributionChart,
  MetricRadarChart,
  SimpleBarChart,
  SimpleLineChart,
} from "@/components/charts/charts";
import { usePageMeta } from "@/components/layout/page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/feedback";
import { StatCard } from "@/components/ui/stat-card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { EmptyRow, TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { useEvaluationAnalytics, useSchedulingAnalytics } from "@/lib/queries";
import { formatDate, minutesToHours } from "@/lib/utils";

export default function AnalyticsPage() {
  const { notify } = useToast();
  const scheduling = useSchedulingAnalytics();
  const evaluation = useEvaluationAnalytics();
  const [downloading, setDownloading] = React.useState(false);

  async function downloadReport() {
    setDownloading(true);
    try {
      const report = await api.get<Record<string, unknown>>("/analytics/report");
      const blob = new Blob([JSON.stringify(report, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `interview-report-${new Date().toISOString().slice(0, 10)}.json`;
      anchor.click();
      URL.revokeObjectURL(url);
      notify("Report downloaded.");
    } catch (err) {
      notify(err instanceof Error ? err.message : "Report failed", "error");
    } finally {
      setDownloading(false);
    }
  }

  usePageMeta(
    "Analytics & Reports",
    "Scheduling efficiency, workload distribution and evaluation performance",
    <Button size="sm" variant="secondary" onClick={downloadReport} disabled={downloading}>
      <Download className="h-3.5 w-3.5" />
      {downloading ? "Preparing..." : "Export report"}
    </Button>,
  );

  if (scheduling.isLoading || evaluation.isLoading) return <LoadingState />;
  if (scheduling.error) return <ErrorState error={scheduling.error} />;
  if (evaluation.error) return <ErrorState error={evaluation.error} />;

  const s = scheduling.data;
  const e = evaluation.data;
  if (!s || !e) return null;

  const efficiency = s.scheduling_efficiency ?? {};

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Scheduling success"
          value={`${efficiency.success_rate ?? 0}%`}
          tone="success"
          hint={`${s.scheduled_vs_unscheduled.scheduled ?? 0} of ${
            (s.scheduled_vs_unscheduled.scheduled ?? 0) +
            (s.scheduled_vs_unscheduled.unscheduled ?? 0)
          } candidates`}
        />
        <StatCard
          label="Average slot score"
          value={efficiency.average_score ?? 0}
          tone="brand"
          hint="Soft-constraint satisfaction"
        />
        <StatCard
          label="Conflicts"
          value={efficiency.conflict_count ?? 0}
          tone={efficiency.conflict_count ? "danger" : "success"}
        />
        <StatCard
          label="Manual overrides"
          value={efficiency.manual_overrides ?? 0}
          tone="neutral"
          hint={`${efficiency.locked_interviews ?? 0} locked`}
        />
      </div>

      <Tabs defaultValue="scheduling">
        <TabsList>
          <TabsTrigger value="scheduling">Scheduling</TabsTrigger>
          <TabsTrigger value="evaluation">Evaluation</TabsTrigger>
        </TabsList>

        <TabsContent value="scheduling" className="space-y-4">
          <div className="grid gap-4 xl:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Interviews per day</CardTitle>
              </CardHeader>
              <CardContent>
                {s.interviews_per_day.length ? (
                  <SimpleLineChart
                    data={s.interviews_per_day.map((row) => ({
                      ...row,
                      date: formatDate(row.date),
                    }))}
                    xKey="date"
                    lines={[{ key: "count", name: "Interviews" }]}
                  />
                ) : (
                  <EmptyState title="No interviews scheduled yet" />
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Slot utilisation</CardTitle>
                <p className="text-[11px] text-slate-400">Booked vs free faculty minutes</p>
              </CardHeader>
              <CardContent>
                {s.slot_utilisation.length ? (
                  <SimpleBarChart
                    data={s.slot_utilisation.map((row) => ({
                      date: formatDate(row.date),
                      booked: Math.round(row.booked_minutes / 60),
                      free: Math.round(row.free_minutes / 60),
                    }))}
                    xKey="date"
                    bars={[
                      { key: "booked", name: "Booked (h)", color: "#2f4bd8" },
                      { key: "free", name: "Free (h)", color: "#0f9d58" },
                    ]}
                  />
                ) : (
                  <EmptyState title="No free slots calculated yet" />
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Faculty workload</CardTitle>
              </CardHeader>
              <CardContent>
                {s.faculty_workload.length ? (
                  <SimpleBarChart
                    layout="vertical"
                    height={Math.max(240, s.faculty_workload.slice(0, 10).length * 28)}
                    data={s.faculty_workload.slice(0, 10).map((row) => ({
                      name: row.name,
                      interviews: row.interviews,
                    }))}
                    xKey="name"
                    bars={[{ key: "interviews", name: "Interviews" }]}
                  />
                ) : (
                  <EmptyState title="No workload yet" />
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Panel workload</CardTitle>
              </CardHeader>
              <CardContent>
                {s.panel_workload.length ? (
                  <SimpleBarChart
                    layout="vertical"
                    height={Math.max(220, s.panel_workload.length * 30)}
                    data={s.panel_workload.map((row) => ({
                      name: row.name,
                      interviews: row.interviews,
                    }))}
                    xKey="name"
                    bars={[{ key: "interviews", name: "Interviews", color: "#8b5cf6" }]}
                  />
                ) : (
                  <EmptyState title="No panel workload yet" />
                )}
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Scheduled vs unscheduled by department</CardTitle>
              </CardHeader>
              <CardContent>
                {s.department_breakdown.length ? (
                  <SimpleBarChart
                    data={s.department_breakdown}
                    xKey="department"
                    bars={[
                      { key: "scheduled", name: "Scheduled", color: "#0f9d58" },
                      { key: "unscheduled", name: "Unscheduled", color: "#d98324" },
                    ]}
                  />
                ) : (
                  <EmptyState title="No candidates yet" />
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Faculty utilisation detail</CardTitle>
              </CardHeader>
              <CardContent className="px-0 pb-0">
                <Table>
                  <THead>
                    <TR>
                      <TH>Faculty</TH>
                      <TH>Interviews</TH>
                      <TH>Time booked</TH>
                      <TH>Share</TH>
                    </TR>
                  </THead>
                  <TBody>
                    {s.faculty_workload.length ? (
                      s.faculty_workload.slice(0, 12).map((row) => (
                        <TR key={row.id}>
                          <TD>
                            <p className="font-medium text-slate-800">{row.name}</p>
                            <p className="text-[11px] text-slate-400">
                              {row.department ?? row.code}
                            </p>
                          </TD>
                          <TD>{row.interviews}</TD>
                          <TD>{minutesToHours(row.minutes)}</TD>
                          <TD>{row.share}%</TD>
                        </TR>
                      ))
                    ) : (
                      <EmptyRow colSpan={4} message="No workload recorded." />
                    )}
                  </TBody>
                </Table>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Scheduling run history</CardTitle>
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
                    <TH>Score</TH>
                    <TH>Duration</TH>
                  </TR>
                </THead>
                <TBody>
                  {s.run_history.length ? (
                    s.run_history.map((run, index) => (
                      <TR key={index}>
                        <TD className="font-mono text-[11px]">{String(run.run_code)}</TD>
                        <TD>{String(run.algorithm)}</TD>
                        <TD>
                          <Badge tone="neutral">{String(run.status)}</Badge>
                        </TD>
                        <TD>{String(run.scheduled)}</TD>
                        <TD>{String(run.unscheduled)}</TD>
                        <TD>{String(run.score)}</TD>
                        <TD>{String(run.duration_ms)} ms</TD>
                      </TR>
                    ))
                  ) : (
                    <EmptyRow colSpan={7} message="No scheduling runs yet." />
                  )}
                </TBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="evaluation" className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-3">
            <StatCard label="Evaluations" value={e.total_evaluations} tone="brand" />
            <StatCard
              label="Average overall score"
              value={e.average_overall_score.toFixed(2)}
              tone="info"
            />
            <StatCard label="Metrics tracked" value={e.metric_averages.length} />
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Average score per metric</CardTitle>
              </CardHeader>
              <CardContent>
                {e.metric_averages.length ? (
                  <SimpleBarChart
                    data={e.metric_averages.map((metric) => ({
                      name: metric.metric_name,
                      average: metric.average,
                    }))}
                    xKey="name"
                    layout="vertical"
                    height={Math.max(240, e.metric_averages.length * 32)}
                    bars={[{ key: "average", name: "Average score" }]}
                  />
                ) : (
                  <EmptyState title="No evaluations yet" />
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Metric profile (cohort average)</CardTitle>
              </CardHeader>
              <CardContent>
                {e.metric_averages.length ? (
                  <MetricRadarChart
                    series="Cohort average"
                    data={e.metric_averages.map((metric) => ({
                      metric: metric.metric_name,
                      value: metric.normalized_average,
                      fullMark: 100,
                    }))}
                  />
                ) : (
                  <EmptyState title="No evaluations yet" />
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Score distribution</CardTitle>
                <p className="text-[11px] text-slate-400">Normalised overall score bands</p>
              </CardHeader>
              <CardContent>
                {e.score_distribution.length ? (
                  <DistributionChart data={e.score_distribution} />
                ) : (
                  <EmptyState title="No evaluations yet" />
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Top candidates</CardTitle>
              </CardHeader>
              <CardContent className="px-0 pb-0">
                <Table>
                  <THead>
                    <TR>
                      <TH>#</TH>
                      <TH>Candidate</TH>
                      <TH>Overall</TH>
                      <TH>Strongest</TH>
                      <TH>Weakest</TH>
                    </TR>
                  </THead>
                  <TBody>
                    {e.top_candidates.length ? (
                      e.top_candidates.map((row) => (
                        <TR key={row.candidate_id}>
                          <TD>{row.rank}</TD>
                          <TD>
                            <p className="font-medium text-slate-800">
                              {row.candidate_name}
                            </p>
                            <p className="text-[11px] text-slate-400">
                              {row.candidate_code}
                            </p>
                          </TD>
                          <TD className="font-semibold">{row.overall_score.toFixed(2)}</TD>
                          <TD className="text-[11px] text-[var(--color-success)]">
                            {row.strongest_metric ?? "-"}
                          </TD>
                          <TD className="text-[11px] text-[var(--color-warning)]">
                            {row.weakest_metric ?? "-"}
                          </TD>
                        </TR>
                      ))
                    ) : (
                      <EmptyRow colSpan={5} message="No evaluations yet." />
                    )}
                  </TBody>
                </Table>
              </CardContent>
            </Card>
          </div>

          {e.panel_statistics.length || e.faculty_statistics.length ? (
            <div className="grid gap-4 xl:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle>Panel evaluation statistics</CardTitle>
                </CardHeader>
                <CardContent className="px-0 pb-0">
                  <Table>
                    <THead>
                      <TR>
                        <TH>Panel</TH>
                        <TH>Evaluations</TH>
                        <TH>Average score</TH>
                      </TR>
                    </THead>
                    <TBody>
                      {e.panel_statistics.map((row, index) => (
                        <TR key={index}>
                          <TD>{String(row.panel_name)}</TD>
                          <TD>{String(row.evaluations)}</TD>
                          <TD>{String(row.average_score)}</TD>
                        </TR>
                      ))}
                    </TBody>
                  </Table>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Evaluator statistics</CardTitle>
                </CardHeader>
                <CardContent className="px-0 pb-0">
                  <Table>
                    <THead>
                      <TR>
                        <TH>Faculty</TH>
                        <TH>Evaluations</TH>
                        <TH>Average score</TH>
                      </TR>
                    </THead>
                    <TBody>
                      {e.faculty_statistics.map((row, index) => (
                        <TR key={index}>
                          <TD>{String(row.faculty_name)}</TD>
                          <TD>{String(row.evaluations)}</TD>
                          <TD>{String(row.average_score)}</TD>
                        </TR>
                      ))}
                    </TBody>
                  </Table>
                </CardContent>
              </Card>
            </div>
          ) : null}
        </TabsContent>
      </Tabs>
    </div>
  );
}
