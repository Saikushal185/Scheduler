from __future__ import annotations

import datetime as _dt
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import CandidateStatus
from app.schemas.common import ORMModel
from app.utils.timeutils import parse_date, parse_time


class AvailabilityWindow(BaseModel):
    date: _dt.date
    start_time: _dt.time
    end_time: _dt.time

    @field_validator("date", mode="before")
    @classmethod
    def _date(cls, v):
        return parse_date(v) if not isinstance(v, _dt.date) else v

    @field_validator("start_time", "end_time", mode="before")
    @classmethod
    def _time(cls, v):
        return parse_time(v) if not isinstance(v, _dt.time) else v


class CandidateBase(BaseModel):
    candidate_name: str = Field(min_length=1, max_length=255)
    email: str | None = None
    phone: str | None = None
    department: str | None = None
    position: str | None = None
    preferred_date: _dt.date | None = None
    preferred_time: _dt.time | None = None
    preferred_panel_code: str | None = None
    availability: list[AvailabilityWindow] = Field(default_factory=list)
    constraints: dict[str, Any] = Field(default_factory=dict)
    priority: int = 0
    notes: str | None = None
    is_active: bool = True


class CandidateCreate(CandidateBase):
    candidate_code: str = Field(min_length=1, max_length=64)


class CandidateUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    candidate_name: str | None = None
    email: str | None = None
    phone: str | None = None
    department: str | None = None
    position: str | None = None
    preferred_date: _dt.date | None = None
    preferred_time: _dt.time | None = None
    preferred_panel_code: str | None = None
    availability: list[AvailabilityWindow] | None = None
    constraints: dict[str, Any] | None = None
    priority: int | None = None
    status: CandidateStatus | None = None
    notes: str | None = None
    is_active: bool | None = None


class CandidateRead(ORMModel):
    id: int
    candidate_code: str
    candidate_name: str
    email: str | None = None
    phone: str | None = None
    department: str | None = None
    position: str | None = None
    preferred_date: _dt.date | None = None
    preferred_time: _dt.time | None = None
    preferred_panel_code: str | None = None
    availability: list[dict[str, Any]] = Field(default_factory=list)
    constraints: dict[str, Any] = Field(default_factory=dict)
    priority: int = 0
    status: CandidateStatus
    notes: str | None = None
    is_active: bool = True
