from __future__ import annotations

import datetime as _dt

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.common import ORMModel
from app.schemas.faculty import FacultyRead


class PanelMemberRead(ORMModel):
    id: int
    faculty_id: int
    role: str
    is_mandatory: bool
    faculty: FacultyRead | None = None


class PanelMemberInput(BaseModel):
    faculty_id: int
    role: str = "MEMBER"
    is_mandatory: bool = False


class PanelBase(BaseModel):
    panel_name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    department: str | None = None
    minimum_panel_size: int = Field(default=2, ge=1, le=20)
    maximum_panel_size: int = Field(default=4, ge=1, le=20)
    is_active: bool = True

    @model_validator(mode="after")
    def _check_sizes(self):
        if self.maximum_panel_size < self.minimum_panel_size:
            raise ValueError("maximum_panel_size must be >= minimum_panel_size")
        return self


class PanelCreate(PanelBase):
    panel_code: str = Field(min_length=1, max_length=64)
    members: list[PanelMemberInput] = Field(default_factory=list)


class PanelUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    panel_name: str | None = None
    description: str | None = None
    department: str | None = None
    minimum_panel_size: int | None = None
    maximum_panel_size: int | None = None
    is_active: bool | None = None
    members: list[PanelMemberInput] | None = None


class PanelRead(ORMModel):
    id: int
    panel_code: str
    panel_name: str
    description: str | None = None
    department: str | None = None
    minimum_panel_size: int
    maximum_panel_size: int
    is_active: bool
    members: list[PanelMemberRead] = Field(default_factory=list)


class PanelAvailabilitySlot(BaseModel):
    date: _dt.date
    start_time: _dt.time
    end_time: _dt.time
    available_faculty_ids: list[int]
    available_count: int
    is_complete_panel: bool
    meets_minimum: bool


class PanelAvailabilityResponse(BaseModel):
    panel_id: int
    panel_code: str
    panel_name: str
    date_from: _dt.date
    date_to: _dt.date
    minimum_panel_size: int
    total_members: int
    fully_available_windows: list[PanelAvailabilitySlot]
    partially_available_windows: list[PanelAvailabilitySlot]
    conflicts: list[str] = Field(default_factory=list)


class AlternativePanel(BaseModel):
    panel_id: int
    panel_code: str
    panel_name: str
    available_faculty_ids: list[int]
    available_count: int
    minimum_panel_size: int
    department: str | None = None
    match_score: float


class AlternativePanelRequest(BaseModel):
    date: _dt.date
    start_time: _dt.time
    end_time: _dt.time
    exclude_panel_ids: list[int] = Field(default_factory=list)
    department: str | None = None
