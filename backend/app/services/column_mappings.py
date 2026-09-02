"""Declarative column mappings for every supported input sheet.

Sheets are matched by their columns rather than by position, and every field
accepts a list of aliases, so real-world spreadsheets ("Faculty ID", "faculty
code", "FacultyId") import without being reshaped by hand.

Evaluation metric columns are resolved at runtime from the `evaluation_metrics`
table - no metric name appears in this file.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.models.enums import DatasetType


def normalise(column: object) -> str:
    text = re.sub(r"[^a-z0-9]+", "_", str(column).strip().lower())
    return text.strip("_")


@dataclass(frozen=True)
class FieldSpec:
    name: str
    aliases: tuple[str, ...] = ()
    required: bool = False
    description: str = ""

    @property
    def all_names(self) -> tuple[str, ...]:
        return (self.name,) + self.aliases


@dataclass(frozen=True)
class DatasetSpec:
    dataset: DatasetType
    fields: tuple[FieldSpec, ...]
    sheet_aliases: tuple[str, ...] = ()
    dynamic_metric_columns: bool = False
    description: str = ""
    # Tie-break nudge for sheets whose columns fit more than one dataset.
    preference: float = 0.0

    @property
    def required_fields(self) -> tuple[FieldSpec, ...]:
        return tuple(f for f in self.fields if f.required)

    def resolve(self, columns: list[str]) -> dict[str, str]:
        """Map canonical field name -> actual column name in the sheet."""
        available = {normalise(c): c for c in columns}
        mapping: dict[str, str] = {}
        for spec in self.fields:
            for alias in spec.all_names:
                key = normalise(alias)
                if key in available:
                    mapping[spec.name] = available[key]
                    break
        return mapping

    def missing_required(self, columns: list[str]) -> list[str]:
        mapping = self.resolve(columns)
        return [f.name for f in self.required_fields if f.name not in mapping]

    def match_score(self, sheet_name: str, columns: list[str]) -> float:
        mapping = self.resolve(columns)
        required = self.required_fields
        if required and any(f.name not in mapping for f in required):
            score = 0.0
        else:
            score = 1.0 + len(mapping) / max(1, len(self.fields))
        if normalise(sheet_name) in {normalise(a) for a in self.sheet_aliases}:
            score += 2.0
        return score + self.preference if score else score


CANDIDATES = DatasetSpec(
    dataset=DatasetType.CANDIDATES,
    sheet_aliases=("candidates", "candidate", "applicants", "students"),
    description="Candidates to be interviewed",
    fields=(
        FieldSpec("candidate_id", ("candidate_code", "id", "code", "roll_no",
                                   "application_id"), required=True),
        FieldSpec("candidate_name", ("name", "full_name", "candidate"), required=True),
        FieldSpec("email", ("email_id", "mail", "email_address")),
        FieldSpec("phone", ("mobile", "contact", "phone_number")),
        FieldSpec("department", ("dept", "branch", "discipline", "program")),
        FieldSpec("position", ("role", "applied_for", "designation")),
        FieldSpec("preferred_date", ("pref_date", "preferred_interview_date", "date")),
        FieldSpec("preferred_time", ("pref_time", "preferred_interview_time", "time")),
        FieldSpec("preferred_panel", ("panel", "preferred_panel_id",
                                      "preferred_panel_code")),
        FieldSpec("availability", ("available_slots", "availability_windows",
                                   "free_time", "available")),
        FieldSpec("priority", ("weight", "rank_priority")),
        FieldSpec("constraints", ("additional_constraints", "notes_constraints",
                                  "special_requirements")),
        FieldSpec("notes", ("remarks", "comment", "comments")),
    ),
)

FACULTY = DatasetSpec(
    dataset=DatasetType.FACULTY,
    sheet_aliases=("faculty", "faculties", "interviewers", "panel_members", "staff"),
    description="Faculty members who conduct interviews",
    fields=(
        FieldSpec("faculty_id", ("faculty_code", "id", "code", "employee_id"),
                  required=True),
        FieldSpec("faculty_name", ("name", "full_name", "faculty"), required=True),
        FieldSpec("department", ("dept", "branch", "discipline")),
        FieldSpec("email", ("email_id", "mail", "email_address")),
        FieldSpec("phone", ("mobile", "contact", "phone_number")),
        FieldSpec("designation", ("title", "position", "role")),
        FieldSpec("max_interviews_per_day", ("max_per_day", "daily_limit",
                                             "max_interviews")),
    ),
)

FACULTY_AVAILABILITY = DatasetSpec(
    dataset=DatasetType.FACULTY_AVAILABILITY,
    sheet_aliases=("faculty_availability", "availability", "faculty_slots",
                   "available_slots"),
    description="Working windows declared by faculty",
    preference=0.2,
    fields=(
        FieldSpec("faculty_id", ("faculty_code", "id", "code", "employee_id"),
                  required=True),
        FieldSpec("date", ("day", "available_date", "availability_date"), required=True),
        FieldSpec("start_time", ("from", "from_time", "start", "begin"), required=True),
        FieldSpec("end_time", ("to", "to_time", "end", "finish"), required=True),
        FieldSpec("availability_status", ("status", "availability", "available")),
        FieldSpec("note", ("remarks", "comment", "reason")),
    ),
)

FACULTY_BUSY_SLOTS = DatasetSpec(
    dataset=DatasetType.FACULTY_BUSY_SLOTS,
    sheet_aliases=("faculty_busy_slots", "busy_slots", "busy", "engagements",
                   "commitments"),
    description="Existing commitments that block faculty time",
    fields=(
        FieldSpec("faculty_id", ("faculty_code", "id", "code"), required=True),
        FieldSpec("date", ("day", "busy_date"), required=True),
        FieldSpec("start_time", ("from", "from_time", "start"), required=True),
        FieldSpec("end_time", ("to", "to_time", "end"), required=True),
        FieldSpec("reason", ("remarks", "note", "activity", "comment")),
    ),
)

PANEL_GROUPS = DatasetSpec(
    dataset=DatasetType.PANEL_GROUPS,
    sheet_aliases=("panel_groups", "panels", "panel", "interview_panels"),
    description="Interview panels and their members",
    fields=(
        FieldSpec("panel_id", ("panel_code", "id", "code"), required=True),
        FieldSpec("panel_name", ("name", "panel", "title"), required=True),
        FieldSpec("faculty_members", ("members", "faculty", "faculty_ids",
                                      "panel_members", "faculty_list"), required=True),
        FieldSpec("minimum_panel_size", ("min_size", "min_panel_size", "minimum")),
        FieldSpec("maximum_panel_size", ("max_size", "max_panel_size", "maximum")),
        FieldSpec("department", ("dept", "branch")),
        FieldSpec("description", ("remarks", "notes", "comment")),
        FieldSpec("mandatory_members", ("chair", "mandatory", "required_members")),
    ),
)

INTERVIEW_SETTINGS = DatasetSpec(
    dataset=DatasetType.INTERVIEW_SETTINGS,
    sheet_aliases=("interview_settings", "settings", "configuration", "config"),
    description="Global scheduling parameters",
    fields=(
        FieldSpec("interview_duration", ("duration", "interview_duration_minutes",
                                         "slot_duration"), required=True),
        FieldSpec("break_duration", ("break", "break_duration_minutes",
                                     "buffer", "gap")),
        FieldSpec("start_time", ("day_start", "day_start_time", "from")),
        FieldSpec("end_time", ("day_end", "day_end_time", "to")),
        FieldSpec("scheduling_date_range", ("date_range", "range", "schedule_range")),
        FieldSpec("schedule_start_date", ("start_date", "from_date")),
        FieldSpec("schedule_end_date", ("end_date", "to_date")),
        FieldSpec("slot_granularity", ("granularity", "step", "interval")),
        FieldSpec("min_panel_size", ("minimum_panel_size", "min_size")),
        FieldSpec("max_panel_size", ("maximum_panel_size", "max_size")),
        FieldSpec("max_interviews_per_faculty_per_day", ("max_per_faculty",
                                                         "faculty_daily_limit")),
        FieldSpec("allow_weekends", ("weekends", "include_weekends")),
    ),
)

EVALUATIONS = DatasetSpec(
    dataset=DatasetType.EVALUATIONS,
    sheet_aliases=("evaluation", "evaluations", "scores", "results", "marks"),
    description="Scores for the configured evaluation metrics",
    dynamic_metric_columns=True,
    fields=(
        FieldSpec("candidate_id", ("candidate_code", "id", "code", "roll_no"),
                  required=True),
        FieldSpec("interview_id", ("schedule_code", "interview_code")),
        FieldSpec("panel_id", ("panel_code", "panel")),
        FieldSpec("evaluator_id", ("faculty_id", "evaluator", "evaluator_code")),
        FieldSpec("evaluation_date", ("date", "evaluated_on")),
        FieldSpec("recommendation", ("decision", "verdict", "result")),
        FieldSpec("remarks", ("comment", "comments", "notes", "feedback")),
    ),
)

DATASETS: tuple[DatasetSpec, ...] = (
    CANDIDATES, FACULTY, FACULTY_AVAILABILITY, FACULTY_BUSY_SLOTS,
    PANEL_GROUPS, INTERVIEW_SETTINGS, EVALUATIONS,
)

BY_TYPE: dict[DatasetType, DatasetSpec] = {spec.dataset: spec for spec in DATASETS}


def detect_dataset(sheet_name: str, columns: list[str],
                   metric_columns: list[str] | None = None) -> DatasetSpec | None:
    """Pick the dataset whose column signature best matches the sheet."""
    best: tuple[float, DatasetSpec] | None = None
    for spec in DATASETS:
        score = spec.match_score(sheet_name, columns)
        if spec.dynamic_metric_columns and metric_columns:
            present = {normalise(c) for c in columns}
            hits = sum(1 for m in metric_columns if normalise(m) in present)
            if hits:
                score += 1.0 + hits * 0.5
        if score <= 0:
            continue
        if best is None or score > best[0]:
            best = (score, spec)
    return best[1] if best else None
