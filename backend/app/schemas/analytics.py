from __future__ import annotations

import datetime as _dt
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import InterviewStatus


class SummaryCards(BaseModel):
    total_candidates: int = 0
    scheduled_candidates: int = 0
    unscheduled_candidates: int = 0
    total_faculty: int = 0
    available_faculty: int = 0
    total_panel_groups: int = 0
    available_free_slots: int = 0
    free_slot_hours: float = 0.0
    scheduling_success_rate: float = 0.0
    conflicts_detected: int = 0
    completed_interviews: int = 0
    evaluations_recorded: int = 0
    candidates_evaluated: int = 0


class UpcomingInterview(BaseModel):
    interview_id: int
    schedule_code: str
    candidate_name: str
    candidate_code: str
    date: _dt.date
    start_time: _dt.time
    end_time: _dt.time
    panel_name: str | None = None
    faculty_names: list[str] = Field(default_factory=list)
    status: InterviewStatus


class ActivityItem(BaseModel):
    id: int
    interview_id: int
    action: str
    reason: str | None = None
    schedule_code: str | None = None
    candidate_name: str | None = None
    created_at: str


class ConflictAlert(BaseModel):
    kind: str
    message: str
    candidate_ids: list[int] = Field(default_factory=list)
    faculty_ids: list[int] = Field(default_factory=list)
    panel_ids: list[int] = Field(default_factory=list)


class FacultyAvailabilityOverview(BaseModel):
    faculty_id: int
    faculty_code: str
    faculty_name: str
    department: str | None = None
    free_minutes: int = 0
    booked_minutes: int = 0
    interviews: int = 0
    utilisation: float = 0.0


class UnscheduledSummary(BaseModel):
    candidate_id: int
    candidate_code: str
    candidate_name: str
    department: str | None = None
    reason: str | None = None


class DashboardResponse(BaseModel):
    summary: SummaryCards
    upcoming_interviews: list[UpcomingInterview] = Field(default_factory=list)
    recent_activity: list[ActivityItem] = Field(default_factory=list)
    unscheduled_candidates: list[UnscheduledSummary] = Field(default_factory=list)
    conflict_alerts: list[ConflictAlert] = Field(default_factory=list)
    faculty_availability: list[FacultyAvailabilityOverview] = Field(default_factory=list)
    status_breakdown: dict[str, int] = Field(default_factory=dict)
    interviews_per_day: list[dict[str, Any]] = Field(default_factory=list)


class MetricAverage(BaseModel):
    metric_id: int
    metric_key: str
    metric_name: str
    average: float
    max_score: float
    weight: float
    evaluations: int
    normalized_average: float


class DistributionBucket(BaseModel):
    label: str
    lower: float
    upper: float
    count: int


class WorkloadRow(BaseModel):
    id: int
    code: str
    name: str
    department: str | None = None
    interviews: int = 0
    minutes: int = 0
    share: float = 0.0


class SlotUtilisation(BaseModel):
    date: _dt.date
    free_minutes: int
    booked_minutes: int
    utilisation: float
    interviews: int


class EvaluationAnalytics(BaseModel):
    metric_averages: list[MetricAverage] = Field(default_factory=list)
    score_distribution: list[DistributionBucket] = Field(default_factory=list)
    top_candidates: list[dict[str, Any]] = Field(default_factory=list)
    panel_statistics: list[dict[str, Any]] = Field(default_factory=list)
    faculty_statistics: list[dict[str, Any]] = Field(default_factory=list)
    total_evaluations: int = 0
    candidates_evaluated: int = 0
    average_overall_score: float = 0.0


class SchedulingAnalytics(BaseModel):
    scheduled_vs_unscheduled: dict[str, int] = Field(default_factory=dict)
    status_breakdown: dict[str, int] = Field(default_factory=dict)
    faculty_workload: list[WorkloadRow] = Field(default_factory=list)
    panel_workload: list[WorkloadRow] = Field(default_factory=list)
    slot_utilisation: list[SlotUtilisation] = Field(default_factory=list)
    interviews_per_day: list[dict[str, Any]] = Field(default_factory=list)
    scheduling_efficiency: dict[str, float] = Field(default_factory=dict)
    department_breakdown: list[dict[str, Any]] = Field(default_factory=list)
    run_history: list[dict[str, Any]] = Field(default_factory=list)


class ReportResponse(BaseModel):
    generated_at: str
    organisation: str
    summary: SummaryCards
    scheduling: SchedulingAnalytics
    evaluation: EvaluationAnalytics
    rankings: list[dict[str, Any]] = Field(default_factory=list)
