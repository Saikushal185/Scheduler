"use client";

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryOptions,
} from "@tanstack/react-query";

import { api } from "@/lib/api";
import type {
  Availability,
  BusySlot,
  CalendarEvent,
  Candidate,
  ColumnMapping,
  ConflictItem,
  DashboardResponse,
  Evaluation,
  EvaluationAnalytics,
  EvaluationMetric,
  Faculty,
  FreeSlot,
  FreeSlotGroup,
  HistoryEntry,
  Interview,
  InterviewSettings,
  ManualChangeResponse,
  Panel,
  PanelAvailability,
  RankingRow,
  SchedulePreview,
  SchedulingAnalytics,
  SchedulingConstraint,
  SchedulingRun,
  UploadRecord,
  AvailableSlot,
  FacultyTimelineDay,
  InterviewChangeRequest,
  MyResult,
  ProvisionResponse,
  User,
} from "@/lib/types";

export const keys = {
  dashboard: ["dashboard"] as const,
  summary: ["summary"] as const,
  candidates: (params?: unknown) => ["candidates", params ?? {}] as const,
  faculty: (params?: unknown) => ["faculty", params ?? {}] as const,
  departments: ["departments"] as const,
  availability: (params?: unknown) => ["availability", params ?? {}] as const,
  busySlots: (params?: unknown) => ["busy-slots", params ?? {}] as const,
  freeSlots: (params?: unknown) => ["free-slots", params ?? {}] as const,
  freeSlotGroups: (params?: unknown) => ["free-slot-groups", params ?? {}] as const,
  panels: ["panels"] as const,
  panelAvailability: (id: number, params?: unknown) =>
    ["panel-availability", id, params ?? {}] as const,
  interviews: (params?: unknown) => ["interviews", params ?? {}] as const,
  interview: (id: number) => ["interview", id] as const,
  history: (id: number) => ["interview-history", id] as const,
  calendar: (params?: unknown) => ["calendar", params ?? {}] as const,
  conflicts: ["conflicts"] as const,
  runs: ["runs"] as const,
  run: (id: number) => ["run", id] as const,
  algorithms: ["algorithms"] as const,
  constraints: ["constraints"] as const,
  metrics: ["metrics"] as const,
  evaluations: (params?: unknown) => ["evaluations", params ?? {}] as const,
  rankings: ["rankings"] as const,
  analyticsScheduling: ["analytics-scheduling"] as const,
  analyticsEvaluation: ["analytics-evaluation"] as const,
  settings: ["settings"] as const,
  uploads: ["uploads"] as const,
  columnMappings: ["column-mappings"] as const,
  timeline: (params?: unknown) => ["faculty-timeline", params ?? {}] as const,
  availableSlots: (params?: unknown) => ["available-slots", params ?? {}] as const,
  changeRequests: (params?: unknown) => ["change-requests", params ?? {}] as const,
  myResult: ["my-result"] as const,
  users: ["users"] as const,
};

type Options<T> = Omit<UseQueryOptions<T, Error, T>, "queryKey" | "queryFn">;

/** Anything that changes the schedule invalidates these read models. */
export function useInvalidateSchedule() {
  const client = useQueryClient();
  return () => {
    ["dashboard", "summary", "interviews", "interview", "calendar", "conflicts",
      "free-slots", "free-slot-groups", "busy-slots", "candidates",
      "analytics-scheduling", "analytics-evaluation", "runs", "interview-history",
      "faculty-timeline", "available-slots", "change-requests", "my-result",
      "rankings",
    ].forEach((key) => client.invalidateQueries({ queryKey: [key] }));
  };
}

export const useDashboard = () =>
  useQuery({
    queryKey: keys.dashboard,
    queryFn: () => api.get<DashboardResponse>("/analytics/dashboard"),
    refetchInterval: 60_000,
  });

export const useCandidates = (params: {
  q?: string;
  status?: string;
  department?: string;
} = {}) =>
  useQuery({
    queryKey: keys.candidates(params),
    queryFn: () => api.get<Candidate[]>("/candidates", { ...params, limit: 1000 }),
  });

export const useFaculty = (params: { q?: string; department?: string } = {}) =>
  useQuery({
    queryKey: keys.faculty(params),
    queryFn: () => api.get<Faculty[]>("/faculty", { ...params, limit: 1000 }),
  });

export const useDepartments = () =>
  useQuery({
    queryKey: keys.departments,
    queryFn: () => api.get<string[]>("/faculty/departments"),
  });

export const useAvailability = (params: {
  faculty_id?: number;
  start_date?: string;
  end_date?: string;
} = {}) =>
  useQuery({
    queryKey: keys.availability(params),
    queryFn: () => api.get<Availability[]>("/faculty-availability", params),
  });

export const useBusySlots = (params: { faculty_id?: number } = {}) =>
  useQuery({
    queryKey: keys.busySlots(params),
    queryFn: () => api.get<BusySlot[]>("/faculty-busy-slots", params),
  });

export const useFreeSlots = (params: {
  faculty_id?: number;
  start_date?: string;
  end_date?: string;
  min_minutes?: number;
} = {}) =>
  useQuery({
    queryKey: keys.freeSlots(params),
    queryFn: () => api.get<FreeSlot[]>("/free-slots", params),
  });

export const useFreeSlotGroups = (params: {
  faculty_id?: number;
  start_date?: string;
  end_date?: string;
} = {}) =>
  useQuery({
    queryKey: keys.freeSlotGroups(params),
    queryFn: () => api.get<FreeSlotGroup[]>("/free-slots/grouped", params),
  });

export const usePanels = (options?: Options<Panel[]>) =>
  useQuery({
    queryKey: keys.panels,
    queryFn: () => api.get<Panel[]>("/panels"),
    ...options,
  });

export const usePanelAvailability = (
  panelId: number | null,
  params: { start_date?: string; end_date?: string } = {},
) =>
  useQuery({
    queryKey: keys.panelAvailability(panelId ?? 0, params),
    queryFn: () =>
      api.get<PanelAvailability>(`/panels/${panelId}/availability`, params),
    enabled: Boolean(panelId),
  });

export const useInterviews = (params: Record<string, string | number | undefined> = {}) =>
  useQuery({
    queryKey: keys.interviews(params),
    queryFn: () => api.get<Interview[]>("/interviews", { ...params, limit: 2000 }),
  });

export const useInterview = (id: number | null) =>
  useQuery({
    queryKey: keys.interview(id ?? 0),
    queryFn: () => api.get<Interview>(`/interviews/${id}`),
    enabled: Boolean(id),
  });

export const useInterviewHistory = (id: number | null) =>
  useQuery({
    queryKey: keys.history(id ?? 0),
    queryFn: () => api.get<HistoryEntry[]>(`/interviews/${id}/history`),
    enabled: Boolean(id),
  });

export const useCalendar = (params: Record<string, string | number | undefined> = {}) =>
  useQuery({
    queryKey: keys.calendar(params),
    queryFn: () => api.get<CalendarEvent[]>("/interviews/calendar", params),
  });

export const useConflicts = () =>
  useQuery({
    queryKey: keys.conflicts,
    queryFn: () => api.get<ConflictItem[]>("/interviews/conflicts"),
  });

export const useRuns = () =>
  useQuery({
    queryKey: keys.runs,
    queryFn: () => api.get<SchedulingRun[]>("/scheduling/runs", { limit: 10 }),
  });

export const useAlgorithms = () =>
  useQuery({
    queryKey: keys.algorithms,
    queryFn: () => api.get<{ name: string; description: string }[]>(
      "/scheduling/algorithms"),
  });

export const useConstraints = () =>
  useQuery({
    queryKey: keys.constraints,
    queryFn: () => api.get<SchedulingConstraint[]>("/constraints"),
  });

export const useMetrics = () =>
  useQuery({
    queryKey: keys.metrics,
    queryFn: () => api.get<EvaluationMetric[]>("/evaluation-metrics"),
  });

export const useEvaluations = (params: { candidate_id?: number } = {}) =>
  useQuery({
    queryKey: keys.evaluations(params),
    queryFn: () => api.get<Evaluation[]>("/evaluations", params),
  });

export const useRankings = () =>
  useQuery({
    queryKey: keys.rankings,
    queryFn: () => api.get<RankingRow[]>("/evaluations/rankings"),
  });

export const useSchedulingAnalytics = () =>
  useQuery({
    queryKey: keys.analyticsScheduling,
    queryFn: () => api.get<SchedulingAnalytics>("/analytics/scheduling"),
  });

export const useEvaluationAnalytics = () =>
  useQuery({
    queryKey: keys.analyticsEvaluation,
    queryFn: () => api.get<EvaluationAnalytics>("/analytics/evaluation"),
  });

export const useSettings = () =>
  useQuery({
    queryKey: keys.settings,
    queryFn: () => api.get<InterviewSettings>("/settings"),
  });

export const useUploads = () =>
  useQuery({
    queryKey: keys.uploads,
    queryFn: () => api.get<UploadRecord[]>("/uploads", { limit: 25 }),
  });

export const useColumnMappings = () =>
  useQuery({
    queryKey: keys.columnMappings,
    queryFn: () => api.get<ColumnMapping[]>("/uploads/column-mappings"),
  });

// ------------------------------------------------------------------ mutations
export function useGenerateSchedule() {
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post<SchedulePreview>("/scheduling/generate", body),
  });
}

export function useConfirmRun() {
  const invalidate = useInvalidateSchedule();
  return useMutation({
    mutationFn: (runId: number) =>
      api.post<{ interviews_created: number; interviews_replaced: number }>(
        `/scheduling/runs/${runId}/confirm`),
    onSuccess: invalidate,
  });
}

export function useRescheduleInterview() {
  const invalidate = useInvalidateSchedule();
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: Record<string, unknown> }) =>
      api.put<ManualChangeResponse>(`/interviews/${id}/reschedule`, body),
    onSuccess: invalidate,
  });
}

export function useChangeInterviewStatus() {
  const invalidate = useInvalidateSchedule();
  return useMutation({
    mutationFn: ({ id, status, reason }: { id: number; status: string; reason?: string }) =>
      api.put<ManualChangeResponse>(`/interviews/${id}/status`, { status, reason }),
    onSuccess: invalidate,
  });
}

export function useLockInterview() {
  const invalidate = useInvalidateSchedule();
  return useMutation({
    mutationFn: ({ id, is_locked }: { id: number; is_locked: boolean }) =>
      api.put<ManualChangeResponse>(`/interviews/${id}/lock`, { is_locked }),
    onSuccess: invalidate,
  });
}

export function useMarkFacultyUnavailable() {
  const invalidate = useInvalidateSchedule();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post<{ affected_interviews: Record<string, unknown>[]; warnings: string[] }>(
        "/interviews/faculty-unavailable", body),
    onSuccess: invalidate,
  });
}

export function useRecalculateFreeSlots() {
  const invalidate = useInvalidateSchedule();
  return useMutation({
    mutationFn: (body: Record<string, unknown> = {}) =>
      api.post<{ faculty_processed: number; slots_created: number }>(
        "/free-slots/recalculate", body),
    onSuccess: invalidate,
  });
}

// ---------------------------------------------------------------- timeline
export const useFacultyTimeline = (
  params: { faculty_id?: number; start_date?: string; end_date?: string },
  options?: Options<FacultyTimelineDay[]>,
) =>
  useQuery({
    queryKey: keys.timeline(params),
    queryFn: () => api.get<FacultyTimelineDay[]>("/free-slots/timeline", params),
    ...options,
  });

// ------------------------------------------------------- manual booking
/** Slots a manual booking may legally use - a clash is impossible by choice. */
export const useAvailableSlots = (
  params: { candidate_id?: number; panel_id?: number; date?: string },
  options?: Options<AvailableSlot[]>,
) =>
  useQuery({
    queryKey: keys.availableSlots(params),
    queryFn: () => api.get<AvailableSlot[]>("/interviews/available-slots", params),
    // Only meaningful once all three have been chosen.
    enabled: Boolean(params.candidate_id && params.panel_id && params.date),
    ...options,
  });

export function useCreateInterview() {
  const invalidate = useInvalidateSchedule();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post<ManualChangeResponse>("/interviews", body),
    onSuccess: invalidate,
  });
}

// ------------------------------------------------ candidate self-service
export const useMyResult = (options?: Options<MyResult>) =>
  useQuery({
    queryKey: keys.myResult,
    queryFn: () => api.get<MyResult>("/evaluations/my-result"),
    ...options,
  });

export function useConfirmAttendance() {
  const invalidate = useInvalidateSchedule();
  return useMutation({
    mutationFn: (id: number) =>
      api.post<ManualChangeResponse>(`/interviews/${id}/confirm`, {}),
    onSuccess: invalidate,
  });
}

export function useRequestChange() {
  const invalidate = useInvalidateSchedule();
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: Record<string, unknown> }) =>
      api.post<InterviewChangeRequest>(`/interviews/${id}/change-request`, body),
    onSuccess: invalidate,
  });
}

export const useChangeRequests = (
  params: { status?: string } = {},
  options?: Options<InterviewChangeRequest[]>,
) =>
  useQuery({
    queryKey: keys.changeRequests(params),
    queryFn: () => api.get<InterviewChangeRequest[]>("/interview-requests", params),
    ...options,
  });

export function useDecideChangeRequest() {
  const invalidate = useInvalidateSchedule();
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: Record<string, unknown> }) =>
      api.post<InterviewChangeRequest>(`/interview-requests/${id}/decide`, body),
    onSuccess: invalidate,
  });
}

// -------------------------------------------------------- administration
export const useUsers = (options?: Options<User[]>) =>
  useQuery({
    queryKey: keys.users,
    queryFn: () => api.get<User[]>("/auth/users"),
    ...options,
  });

export function useProvisionAccounts() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (params: { faculty?: boolean; candidates?: boolean } = {}) =>
      api.post<ProvisionResponse>("/uploads/provision-accounts", params),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.users }),
  });
}
