from __future__ import annotations

import datetime as _dt
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import HistoryAction, InterviewStatus
from app.schemas.candidate import CandidateRead
from app.schemas.common import ORMModel
from app.schemas.faculty import FacultyRead
from app.schemas.panel import PanelRead


class InterviewFacultyRead(ORMModel):
    faculty_id: int
    role: str
    faculty: FacultyRead | None = None


class InterviewRead(ORMModel):
    id: int
    schedule_code: str
    candidate_id: int
    panel_id: int | None = None
    run_id: int | None = None
    date: _dt.date | None = None
    start_time: _dt.time | None = None
    end_time: _dt.time | None = None
    duration_minutes: int
    status: InterviewStatus
    scheduling_score: float
    priority_info: list[dict[str, Any]] = Field(default_factory=list)
    unscheduled_reason: str | None = None
    is_locked: bool
    is_manual: bool
    round_number: int
    location: str | None = None
    notes: str | None = None
    candidate: CandidateRead | None = None
    panel: PanelRead | None = None
    panel_members: list[InterviewFacultyRead] = Field(default_factory=list)
    created_at: _dt.datetime | None = None
    updated_at: _dt.datetime | None = None


class InterviewCreate(BaseModel):
    candidate_id: int
    panel_id: int
    date: _dt.date
    start_time: _dt.time
    duration_minutes: int | None = None
    faculty_ids: list[int] = Field(default_factory=list)
    location: str | None = None
    notes: str | None = None
    force: bool = False


class RescheduleRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    date: _dt.date | None = None
    start_time: _dt.time | None = None
    duration_minutes: int | None = None
    panel_id: int | None = None
    faculty_ids: list[int] | None = None
    location: str | None = None
    notes: str | None = None
    reason: str | None = None
    force: bool = Field(default=False,
                        description="Apply even when conflicts are detected")


class StatusChangeRequest(BaseModel):
    status: InterviewStatus
    reason: str | None = None


class LockRequest(BaseModel):
    is_locked: bool
    reason: str | None = None


class ManualChangeResponse(BaseModel):
    interview: InterviewRead
    warnings: list[str] = Field(default_factory=list)
    conflicts: list[dict[str, Any]] = Field(default_factory=list)
    free_slots_recalculated: int = 0


class HistoryRead(ORMModel):
    id: int
    interview_id: int
    action: HistoryAction
    previous_state: dict[str, Any] = Field(default_factory=dict)
    new_state: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = None
    warnings: list[str] = Field(default_factory=list)
    created_at: _dt.datetime


class CalendarEvent(BaseModel):
    id: int
    title: str
    start: _dt.datetime
    end: _dt.datetime
    status: InterviewStatus
    candidate_name: str
    candidate_code: str
    panel_name: str | None = None
    faculty_names: list[str] = Field(default_factory=list)
    is_locked: bool
    has_conflict: bool = False
    department: str | None = None
