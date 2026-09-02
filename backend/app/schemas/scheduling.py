from __future__ import annotations

import datetime as _dt
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.models.enums import (ConstraintPriority, ConstraintType,
                              ScheduleRunStatus)
from app.schemas.common import ORMModel


class ConstraintBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    constraint_type: ConstraintType
    priority: ConstraintPriority = ConstraintPriority.MEDIUM
    description: str | None = None
    scope: dict[str, Any] = Field(default_factory=dict)
    parameters: dict[str, Any] = Field(default_factory=dict)
    weight_multiplier: float = Field(default=1.0, ge=0.0, le=100.0)
    is_active: bool = True
    display_order: int = 0


class ConstraintCreate(ConstraintBase):
    pass


class ConstraintUpdate(BaseModel):
    name: str | None = None
    constraint_type: ConstraintType | None = None
    priority: ConstraintPriority | None = None
    description: str | None = None
    scope: dict[str, Any] | None = None
    parameters: dict[str, Any] | None = None
    weight_multiplier: float | None = None
    is_active: bool | None = None
    display_order: int | None = None


class ConstraintRead(ORMModel, ConstraintBase):
    id: int


class GenerateScheduleRequest(BaseModel):
    start_date: _dt.date | None = None
    end_date: _dt.date | None = None
    candidate_ids: list[int] | None = None
    panel_ids: list[int] | None = None
    algorithm: str | None = None
    interview_duration_minutes: int | None = Field(default=None, ge=5, le=480)
    break_duration_minutes: int | None = Field(default=None, ge=0, le=240)
    slot_granularity_minutes: int | None = Field(default=None, ge=5, le=120)
    day_start_time: _dt.time | None = None
    day_end_time: _dt.time | None = None
    max_interviews_per_faculty_per_day: int | None = Field(default=None, ge=1, le=50)
    allow_weekends: bool | None = None
    keep_locked_interviews: bool = True
    replace_existing: bool = Field(
        default=True,
        description="Discard previous unlocked interviews before scheduling")

    @model_validator(mode="after")
    def _check_range(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class ScheduledItem(BaseModel):
    candidate_id: int
    candidate_code: str
    candidate_name: str
    panel_id: int
    panel_code: str
    panel_name: str
    faculty_ids: list[int]
    faculty_names: list[str]
    date: _dt.date
    start_time: _dt.time
    end_time: _dt.time
    scheduling_score: float
    priority_info: list[dict[str, Any]] = Field(default_factory=list)


class UnscheduledItem(BaseModel):
    candidate_id: int
    candidate_code: str
    candidate_name: str
    reason: str
    details: list[str] = Field(default_factory=list)


class ConflictItem(BaseModel):
    kind: str
    message: str
    candidate_ids: list[int] = Field(default_factory=list)
    faculty_ids: list[int] = Field(default_factory=list)
    panel_ids: list[int] = Field(default_factory=list)


class SchedulePreview(BaseModel):
    run_id: int
    run_code: str
    algorithm: str
    status: ScheduleRunStatus
    scheduled: list[ScheduledItem]
    unscheduled: list[UnscheduledItem]
    conflicts: list[ConflictItem]
    total_score: float
    success_rate: float
    duration_ms: int
    statistics: dict[str, Any] = Field(default_factory=dict)
    parameters: dict[str, Any] = Field(default_factory=dict)


class RunRead(ORMModel):
    id: int
    run_code: str
    algorithm: str
    status: ScheduleRunStatus
    total_candidates: int
    scheduled_count: int
    unscheduled_count: int
    total_score: float
    duration_ms: int
    parameters: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)


class ConfirmScheduleResponse(BaseModel):
    run_id: int
    interviews_created: int
    interviews_replaced: int
    free_slots_recalculated: int
    conflicts: list[ConflictItem] = Field(default_factory=list)


class AlgorithmInfo(BaseModel):
    name: str
    description: str
