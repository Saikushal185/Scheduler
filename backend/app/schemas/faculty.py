from __future__ import annotations

import datetime as _dt

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import AvailabilityStatus, BusySlotSource
from app.schemas.common import ORMModel


class FacultyBase(BaseModel):
    faculty_name: str = Field(min_length=1, max_length=255)
    email: str | None = None
    phone: str | None = None
    department: str | None = None
    designation: str | None = None
    max_interviews_per_day: int | None = Field(default=None, ge=1, le=50)
    is_active: bool = True
    notes: str | None = None


class FacultyCreate(FacultyBase):
    faculty_code: str = Field(min_length=1, max_length=64)


class FacultyUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    faculty_name: str | None = None
    email: str | None = None
    phone: str | None = None
    department: str | None = None
    designation: str | None = None
    max_interviews_per_day: int | None = None
    is_active: bool | None = None
    notes: str | None = None


class FacultyRead(ORMModel):
    id: int
    faculty_code: str
    faculty_name: str
    email: str | None = None
    phone: str | None = None
    department: str | None = None
    designation: str | None = None
    max_interviews_per_day: int | None = None
    is_active: bool
    notes: str | None = None


class _Window(BaseModel):
    date: _dt.date
    start_time: _dt.time
    end_time: _dt.time

    @model_validator(mode="after")
    def _check_order(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class AvailabilityCreate(_Window):
    faculty_id: int
    availability_status: AvailabilityStatus = AvailabilityStatus.AVAILABLE
    note: str | None = None


class AvailabilityUpdate(BaseModel):
    date: _dt.date | None = None
    start_time: _dt.time | None = None
    end_time: _dt.time | None = None
    availability_status: AvailabilityStatus | None = None
    note: str | None = None


class AvailabilityRead(ORMModel):
    id: int
    faculty_id: int
    date: _dt.date
    start_time: _dt.time
    end_time: _dt.time
    availability_status: AvailabilityStatus
    note: str | None = None


class BusySlotCreate(_Window):
    faculty_id: int
    source: BusySlotSource = BusySlotSource.MANUAL
    reason: str | None = None


class BusySlotRead(ORMModel):
    id: int
    faculty_id: int
    date: _dt.date
    start_time: _dt.time
    end_time: _dt.time
    source: BusySlotSource
    reason: str | None = None
    interview_id: int | None = None


class FreeSlotRead(ORMModel):
    id: int
    faculty_id: int
    date: _dt.date
    start_time: _dt.time
    end_time: _dt.time
    duration_minutes: int


class FreeSlotGroup(BaseModel):
    faculty_id: int
    faculty_code: str
    faculty_name: str
    department: str | None = None
    date: _dt.date
    slots: list[FreeSlotRead]
    total_free_minutes: int


class FreeSlotRecalculateRequest(BaseModel):
    faculty_ids: list[int] | None = None
    start_date: _dt.date | None = None
    end_date: _dt.date | None = None


class FreeSlotRecalculateResponse(BaseModel):
    faculty_processed: int
    slots_created: int
    slots_removed: int
    start_date: _dt.date | None = None
    end_date: _dt.date | None = None
