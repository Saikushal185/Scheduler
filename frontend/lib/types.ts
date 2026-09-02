/** Types mirroring the FastAPI schemas. */

export type CandidateStatus =
  | "PENDING" | "SCHEDULED" | "UNSCHEDULED" | "COMPLETED" | "WITHDRAWN";

export type InterviewStatus =
  | "SCHEDULED" | "PENDING" | "CONFLICT" | "UNSCHEDULED"
  | "RESCHEDULED" | "CANCELLED" | "COMPLETED";

export type ConstraintPriority = "HARD" | "HIGH" | "MEDIUM" | "LOW" | "FLEXIBLE";

export type AvailabilityStatus = "AVAILABLE" | "UNAVAILABLE" | "TENTATIVE";

export type DatasetType =
  | "CANDIDATES" | "FACULTY" | "FACULTY_AVAILABILITY" | "FACULTY_BUSY_SLOTS"
  | "PANEL_GROUPS" | "INTERVIEW_SETTINGS" | "EVALUATIONS";

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface AvailabilityWindow {
  date: string;
  start_time: string;
  end_time: string;
}

export interface Candidate {
  id: number;
  candidate_code: string;
  candidate_name: string;
  email?: string | null;
  phone?: string | null;
  department?: string | null;
  position?: string | null;
  preferred_date?: string | null;
  preferred_time?: string | null;
  preferred_panel_code?: string | null;
  availability: AvailabilityWindow[];
  constraints: Record<string, unknown>;
  priority: number;
  status: CandidateStatus;
  notes?: string | null;
  is_active: boolean;
}

export interface Faculty {
  id: number;
  faculty_code: string;
  faculty_name: string;
  email?: string | null;
  phone?: string | null;
  department?: string | null;
  designation?: string | null;
  max_interviews_per_day?: number | null;
  is_active: boolean;
  notes?: string | null;
}

export interface Availability {
  id: number;
  faculty_id: number;
  date: string;
  start_time: string;
  end_time: string;
  availability_status: AvailabilityStatus;
  note?: string | null;
}

export interface BusySlot {
  id: number;
  faculty_id: number;
  date: string;
  start_time: string;
  end_time: string;
  source: string;
  reason?: string | null;
  interview_id?: number | null;
}

export interface FreeSlot {
  id: number;
  faculty_id: number;
  date: string;
  start_time: string;
  end_time: string;
  duration_minutes: number;
}

export interface FreeSlotGroup {
  faculty_id: number;
  faculty_code: string;
  faculty_name: string;
  department?: string | null;
  date: string;
  slots: FreeSlot[];
  total_free_minutes: number;
}

export interface PanelMember {
  id: number;
  faculty_id: number;
  role: string;
  is_mandatory: boolean;
  faculty?: Faculty | null;
}

export interface Panel {
  id: number;
  panel_code: string;
  panel_name: string;
  description?: string | null;
  department?: string | null;
  minimum_panel_size: number;
  maximum_panel_size: number;
  is_active: boolean;
  members: PanelMember[];
}

export interface PanelAvailabilitySlot {
  date: string;
  start_time: string;
  end_time: string;
  available_faculty_ids: number[];
  available_count: number;
  is_complete_panel: boolean;
  meets_minimum: boolean;
}

export interface PanelAvailability {
  panel_id: number;
  panel_code: string;
  panel_name: string;
  date_from: string;
  date_to: string;
  minimum_panel_size: number;
  total_members: number;
  fully_available_windows: PanelAvailabilitySlot[];
  partially_available_windows: PanelAvailabilitySlot[];
  conflicts: string[];
}

export interface AlternativePanel {
  panel_id: number;
  panel_code: string;
  panel_name: string;
  available_faculty_ids: number[];
  available_count: number;
  minimum_panel_size: number;
  department?: string | null;
  match_score: number;
}

export interface PriorityOutcome {
  type: string;
  priority: ConstraintPriority;
  satisfied: boolean;
  score: number;
  detail: string;
}

export interface InterviewFaculty {
  faculty_id: number;
  role: string;
  faculty?: Faculty | null;
}

export interface Interview {
  id: number;
  schedule_code: string;
  candidate_id: number;
  panel_id?: number | null;
  run_id?: number | null;
  date?: string | null;
  start_time?: string | null;
  end_time?: string | null;
  duration_minutes: number;
  status: InterviewStatus;
  scheduling_score: number;
  priority_info: PriorityOutcome[];
  unscheduled_reason?: string | null;
  is_locked: boolean;
  is_manual: boolean;
  round_number: number;
  location?: string | null;
  notes?: string | null;
  candidate?: Candidate | null;
  panel?: Panel | null;
  panel_members: InterviewFaculty[];
}

export interface CalendarEvent {
  id: number;
  title: string;
  start: string;
  end: string;
  status: InterviewStatus;
  candidate_name: string;
  candidate_code: string;
  panel_name?: string | null;
  faculty_names: string[];
  is_locked: boolean;
  has_conflict: boolean;
  department?: string | null;
}

export interface HistoryEntry {
  id: number;
  interview_id: number;
  action: string;
  previous_state: Record<string, unknown>;
  new_state: Record<string, unknown>;
  reason?: string | null;
  warnings: string[];
  created_at: string;
}

export interface ManualChangeResponse {
  interview: Interview;
  warnings: string[];
  conflicts: { kind: string; message: string }[];
  free_slots_recalculated: number;
}

export interface ScheduledItem {
  candidate_id: number;
  candidate_code: string;
  candidate_name: string;
  panel_id: number;
  panel_code: string;
  panel_name: string;
  faculty_ids: number[];
  faculty_names: string[];
  date: string;
  start_time: string;
  end_time: string;
  scheduling_score: number;
  priority_info: PriorityOutcome[];
}

export interface UnscheduledItem {
  candidate_id: number;
  candidate_code: string;
  candidate_name: string;
  reason: string;
  details: string[];
}

export interface ConflictItem {
  kind: string;
  message: string;
  candidate_ids: number[];
  faculty_ids: number[];
  panel_ids: number[];
}

export interface SchedulePreview {
  run_id: number;
  run_code: string;
  algorithm: string;
  status: "PREVIEW" | "CONFIRMED" | "DISCARDED";
  scheduled: ScheduledItem[];
  unscheduled: UnscheduledItem[];
  conflicts: ConflictItem[];
  total_score: number;
  success_rate: number;
  duration_ms: number;
  statistics: Record<string, unknown>;
  parameters: Record<string, unknown>;
}

export interface SchedulingRun {
  id: number;
  run_code: string;
  algorithm: string;
  status: string;
  total_candidates: number;
  scheduled_count: number;
  unscheduled_count: number;
  total_score: number;
  duration_ms: number;
}

export interface SchedulingConstraint {
  id: number;
  name: string;
  constraint_type: string;
  priority: ConstraintPriority;
  description?: string | null;
  scope: Record<string, unknown>;
  parameters: Record<string, unknown>;
  weight_multiplier: number;
  is_active: boolean;
  display_order: number;
}

export interface EvaluationMetric {
  id: number;
  metric_key: string;
  name: string;
  description?: string | null;
  weight: number;
  min_score: number;
  max_score: number;
  display_order: number;
  is_active: boolean;
  column_aliases: string[];
}

export interface EvaluationScore {
  id: number;
  metric_id: number;
  raw_score: number;
  normalized_score: number;
  weighted_score: number;
  comment?: string | null;
  metric?: EvaluationMetric | null;
}

export interface Evaluation {
  id: number;
  candidate_id: number;
  interview_id?: number | null;
  panel_id?: number | null;
  evaluator_faculty_id?: number | null;
  evaluation_date?: string | null;
  overall_score: number;
  normalized_score: number;
  max_possible_score: number;
  strongest_metric_id?: number | null;
  weakest_metric_id?: number | null;
  recommendation?: string | null;
  remarks?: string | null;
  scores: EvaluationScore[];
  candidate_code?: string | null;
  candidate_name?: string | null;
}

export interface RankingRow {
  rank: number;
  candidate_id: number;
  candidate_code: string;
  candidate_name: string;
  department?: string | null;
  overall_score: number;
  normalized_score: number;
  metric_scores: Record<string, number>;
  strongest_metric?: string | null;
  weakest_metric?: string | null;
  recommendation?: string | null;
}

export interface CandidateProfile {
  candidate_id: number;
  candidate_code: string;
  candidate_name: string;
  overall_score: number;
  normalized_score: number;
  rank?: number | null;
  metrics: {
    metric_id: number;
    metric_key: string;
    metric_name: string;
    raw_score: number;
    normalized_score: number;
    weighted_score: number;
    max_score: number;
    weight: number;
  }[];
  strongest_metric?: string | null;
  weakest_metric?: string | null;
}

export interface SummaryCards {
  total_candidates: number;
  scheduled_candidates: number;
  unscheduled_candidates: number;
  total_faculty: number;
  available_faculty: number;
  total_panel_groups: number;
  available_free_slots: number;
  free_slot_hours: number;
  scheduling_success_rate: number;
  conflicts_detected: number;
  completed_interviews: number;
  evaluations_recorded: number;
}

export interface DashboardResponse {
  summary: SummaryCards;
  upcoming_interviews: {
    interview_id: number;
    schedule_code: string;
    candidate_name: string;
    candidate_code: string;
    date: string;
    start_time: string;
    end_time: string;
    panel_name?: string | null;
    faculty_names: string[];
    status: InterviewStatus;
  }[];
  recent_activity: {
    id: number;
    interview_id: number;
    action: string;
    reason?: string | null;
    schedule_code?: string | null;
    candidate_name?: string | null;
    created_at: string;
  }[];
  unscheduled_candidates: {
    candidate_id: number;
    candidate_code: string;
    candidate_name: string;
    department?: string | null;
    reason?: string | null;
  }[];
  conflict_alerts: ConflictItem[];
  faculty_availability: {
    faculty_id: number;
    faculty_code: string;
    faculty_name: string;
    department?: string | null;
    free_minutes: number;
    booked_minutes: number;
    interviews: number;
    utilisation: number;
  }[];
  status_breakdown: Record<string, number>;
  interviews_per_day: { date: string; count: number }[];
}

export interface SchedulingAnalytics {
  scheduled_vs_unscheduled: Record<string, number>;
  status_breakdown: Record<string, number>;
  faculty_workload: WorkloadRow[];
  panel_workload: WorkloadRow[];
  slot_utilisation: {
    date: string;
    free_minutes: number;
    booked_minutes: number;
    utilisation: number;
    interviews: number;
  }[];
  interviews_per_day: { date: string; count: number }[];
  scheduling_efficiency: Record<string, number>;
  department_breakdown: {
    department: string;
    total: number;
    scheduled: number;
    unscheduled: number;
  }[];
  run_history: Record<string, unknown>[];
}

export interface WorkloadRow {
  id: number;
  code: string;
  name: string;
  department?: string | null;
  interviews: number;
  minutes: number;
  share: number;
}

export interface EvaluationAnalytics {
  metric_averages: {
    metric_id: number;
    metric_key: string;
    metric_name: string;
    average: number;
    max_score: number;
    weight: number;
    evaluations: number;
    normalized_average: number;
  }[];
  score_distribution: { label: string; lower: number; upper: number; count: number }[];
  top_candidates: RankingRow[];
  panel_statistics: Record<string, unknown>[];
  faculty_statistics: Record<string, unknown>[];
  total_evaluations: number;
  average_overall_score: number;
}

export interface InterviewSettings {
  id: number;
  interview_duration_minutes: number;
  break_duration_minutes: number;
  day_start_time: string;
  day_end_time: string;
  schedule_start_date?: string | null;
  schedule_end_date?: string | null;
  slot_granularity_minutes: number;
  min_panel_size: number;
  max_panel_size: number;
  max_interviews_per_faculty_per_day: number;
  allow_weekends: boolean;
  default_algorithm: string;
  organisation_name: string;
}

export interface RowIssue {
  row?: number | null;
  column?: string | null;
  value?: unknown;
  message: string;
}

export interface SheetPreview {
  sheet_name: string;
  detected_dataset?: DatasetType | null;
  columns: string[];
  row_count: number;
  sample_rows: Record<string, string | null>[];
  missing_required_columns: string[];
  unmapped_columns: string[];
  errors: RowIssue[];
  warnings: RowIssue[];
  is_valid: boolean;
}

export interface ValidationResponse {
  upload_id: number;
  filename: string;
  sheets: SheetPreview[];
  is_valid: boolean;
  errors: RowIssue[];
}

export interface ImportResponse {
  upload_id: number;
  filename: string;
  status: string;
  summaries: {
    dataset: DatasetType;
    sheet_name?: string | null;
    rows_total: number;
    created: number;
    updated: number;
    failed: number;
    errors: RowIssue[];
    warnings: RowIssue[];
  }[];
  total_created: number;
  total_updated: number;
  total_failed: number;
  free_slots_recalculated: number;
  errors: RowIssue[];
}

export interface UploadRecord {
  id: number;
  original_filename: string;
  dataset_type?: DatasetType | null;
  status: string;
  sheet_name?: string | null;
  size_bytes: number;
  rows_total: number;
  rows_imported: number;
  rows_failed: number;
  errors: Record<string, unknown>[];
  warnings: Record<string, unknown>[];
  summary: Record<string, unknown>;
}

export interface ColumnMapping {
  dataset: DatasetType;
  required: string[];
  optional: string[];
  aliases: Record<string, string[]>;
}
