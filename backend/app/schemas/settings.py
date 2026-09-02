from __future__ import annotations

import datetime as _dt

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.common import ORMModel


class SettingsRead(ORMModel):
    id: int
    interview_duration_minutes: int
    break_duration_minutes: int
    day_start_time: _dt.time
    day_end_time: _dt.time
    schedule_start_date: _dt.date | None = None
    schedule_end_date: _dt.date | None = None
    slot_granularity_minutes: int
    min_panel_size: int
    max_panel_size: int
    max_interviews_per_faculty_per_day: int
    allow_weekends: bool
    default_algorithm: str
    organisation_name: str


class SettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    interview_duration_minutes: int | None = Field(default=None, ge=5, le=480)
    break_duration_minutes: int | None = Field(default=None, ge=0, le=240)
    day_start_time: _dt.time | None = None
    day_end_time: _dt.time | None = None
    schedule_start_date: _dt.date | None = None
    schedule_end_date: _dt.date | None = None
    slot_granularity_minutes: int | None = Field(default=None, ge=5, le=120)
    min_panel_size: int | None = Field(default=None, ge=1, le=20)
    max_panel_size: int | None = Field(default=None, ge=1, le=20)
    max_interviews_per_faculty_per_day: int | None = Field(default=None, ge=1, le=50)
    allow_weekends: bool | None = None
    default_algorithm: str | None = None
    organisation_name: str | None = None

    @model_validator(mode="after")
    def _check(self):
        if (self.day_start_time and self.day_end_time
                and self.day_end_time <= self.day_start_time):
            raise ValueError("day_end_time must be after day_start_time")
        if (self.min_panel_size and self.max_panel_size
                and self.max_panel_size < self.min_panel_size):
            raise ValueError("max_panel_size must be >= min_panel_size")
        return self
