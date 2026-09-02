"""Pure data structures used by the scheduling engine.

Nothing in this module touches the database or FastAPI, which keeps the whole
algorithm unit-testable in isolation (see backend/tests/test_scheduler.py).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time
from typing import Any, Iterable

from app.models.enums import ConstraintPriority, ConstraintType
from app.utils.timeutils import Interval


# --------------------------------------------------------------------------- input
@dataclass(slots=True)
class CandidateSpec:
    id: int
    code: str
    name: str
    department: str | None = None
    preferred_date: date | None = None
    preferred_time: time | None = None
    preferred_panel_code: str | None = None
    # date -> windows the candidate is reachable.  Empty dict == always available.
    availability: dict[date, list[Interval]] = field(default_factory=dict)
    blocked_dates: set[date] = field(default_factory=set)
    required_panel_code: str | None = None
    priority: int = 0

    def is_available(self, day: date, slot: Interval) -> bool:
        if day in self.blocked_dates:
            return False
        if not self.availability:
            return True
        windows = self.availability.get(day)
        if not windows:
            return False
        return any(w.contains(slot) for w in windows)


@dataclass(slots=True)
class FacultySpec:
    id: int
    code: str
    name: str
    department: str | None = None
    max_per_day: int | None = None
    # date -> free intervals produced by the free-slot calculator
    free_slots: dict[date, list[Interval]] = field(default_factory=dict)

    def is_free(self, day: date, slot: Interval) -> bool:
        return any(window.contains(slot) for window in self.free_slots.get(day, ()))


@dataclass(slots=True)
class PanelSpec:
    id: int
    code: str
    name: str
    member_ids: list[int]
    mandatory_ids: set[int] = field(default_factory=set)
    department: str | None = None
    minimum_panel_size: int = 2
    maximum_panel_size: int = 4


@dataclass(slots=True)
class ConstraintSpec:
    id: int | None
    name: str
    constraint_type: ConstraintType
    priority: ConstraintPriority
    scope: dict[str, Any] = field(default_factory=dict)
    parameters: dict[str, Any] = field(default_factory=dict)
    weight_multiplier: float = 1.0

    @property
    def is_hard(self) -> bool:
        return self.priority == ConstraintPriority.HARD

    def applies_to(self, candidate: CandidateSpec) -> bool:
        target = self.scope.get("candidate_id")
        if target is not None and int(target) != candidate.id:
            return False
        dept = self.scope.get("department")
        if dept and (candidate.department or "").lower() != str(dept).lower():
            return False
        return True


@dataclass(slots=True)
class ExistingBooking:
    """An interview that must be honoured but not re-planned (locked/kept)."""

    interview_id: int
    candidate_id: int
    panel_id: int | None
    faculty_ids: list[int]
    day: date
    slot: Interval


@dataclass(slots=True)
class SchedulingOptions:
    dates: list[date]
    duration_minutes: int = 30
    break_minutes: int = 10
    granularity_minutes: int = 15
    day_start: time | None = None
    day_end: time | None = None
    max_interviews_per_faculty_per_day: int = 12
    algorithm: str = "backtracking"
    allow_weekends: bool = False
    max_options_per_candidate: int = 400
    backtrack_limit: int = 20000
    priority_weights: dict[str, float] = field(default_factory=dict)
    _date_index: dict[date, int] | None = field(default=None, repr=False, compare=False)

    def weight_for(self, priority: ConstraintPriority) -> float:
        return float(self.priority_weights.get(priority.value, 0.0))

    def date_index(self, day: date) -> int:
        """Position of `day` in the scheduling window, O(1).

        Scoring runs this for every candidate x panel x slot combination, so a
        linear scan over `dates` here is measurable on large instances.
        """
        if self._date_index is None or len(self._date_index) != len(self.dates):
            self._date_index = {d: i for i, d in enumerate(self.dates)}
        return self._date_index.get(day, len(self.dates) - 1)


@dataclass(slots=True)
class SchedulingContext:
    """Everything the algorithms need, already materialised in memory."""

    candidates: list[CandidateSpec]
    faculty: dict[int, FacultySpec]
    panels: list[PanelSpec]
    constraints: list[ConstraintSpec]
    options: SchedulingOptions
    existing: list[ExistingBooking] = field(default_factory=list)

    def panel_by_code(self, code: str | None) -> PanelSpec | None:
        if not code:
            return None
        wanted = code.strip().lower()
        for panel in self.panels:
            if panel.code.lower() == wanted or panel.name.lower() == wanted:
                return panel
        return None

    def constraints_of(self, ctype: ConstraintType) -> Iterable[ConstraintSpec]:
        return (c for c in self.constraints if c.constraint_type == ctype)


# -------------------------------------------------------------------------- output
@dataclass(slots=True)
class ConstraintOutcome:
    constraint_type: str
    priority: str
    satisfied: bool
    score: float
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.constraint_type,
            "priority": self.priority,
            "satisfied": self.satisfied,
            "score": round(self.score, 3),
            "detail": self.detail,
        }


@dataclass(slots=True)
class SlotOption:
    """One feasible candidate x panel x time-slot combination."""

    candidate_id: int
    panel_id: int
    day: date
    slot: Interval
    eligible_faculty_ids: list[int]
    required_size: int
    score: float = 0.0
    outcomes: list[ConstraintOutcome] = field(default_factory=list)
    # Outcomes fixed by (candidate, panel, day, slot).  Cached here so placement
    # re-runs only the three rules that depend on the chosen faculty.
    slot_outcomes: list[ConstraintOutcome] = field(default_factory=list)

    @property
    def blocking_slot(self) -> Interval:
        return self.slot


@dataclass(slots=True)
class Assignment:
    candidate_id: int
    panel_id: int
    faculty_ids: list[int]
    day: date
    slot: Interval
    score: float
    outcomes: list[ConstraintOutcome] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "panel_id": self.panel_id,
            "faculty_ids": list(self.faculty_ids),
            "date": self.day.isoformat(),
            "start_time": self.slot.start_time.strftime("%H:%M"),
            "end_time": self.slot.end_time.strftime("%H:%M"),
            "score": round(self.score, 3),
            "priority_info": [o.to_dict() for o in self.outcomes],
        }


@dataclass(slots=True)
class UnscheduledCandidate:
    candidate_id: int
    reason: str
    details: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"candidate_id": self.candidate_id, "reason": self.reason,
                "details": self.details}


@dataclass(slots=True)
class Conflict:
    kind: str
    message: str
    candidate_ids: list[int] = field(default_factory=list)
    faculty_ids: list[int] = field(default_factory=list)
    panel_ids: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "message": self.message,
                "candidate_ids": self.candidate_ids,
                "faculty_ids": self.faculty_ids, "panel_ids": self.panel_ids}


@dataclass(slots=True)
class SchedulingResult:
    algorithm: str
    assignments: list[Assignment] = field(default_factory=list)
    unscheduled: list[UnscheduledCandidate] = field(default_factory=list)
    conflicts: list[Conflict] = field(default_factory=list)
    total_score: float = 0.0
    duration_ms: int = 0
    statistics: dict[str, Any] = field(default_factory=dict)

    @property
    def scheduled_count(self) -> int:
        return len(self.assignments)

    @property
    def success_rate(self) -> float:
        total = len(self.assignments) + len(self.unscheduled)
        return round(100.0 * len(self.assignments) / total, 2) if total else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "algorithm": self.algorithm,
            "assignments": [a.to_dict() for a in self.assignments],
            "unscheduled": [u.to_dict() for u in self.unscheduled],
            "conflicts": [c.to_dict() for c in self.conflicts],
            "total_score": round(self.total_score, 3),
            "scheduled_count": self.scheduled_count,
            "unscheduled_count": len(self.unscheduled),
            "success_rate": self.success_rate,
            "duration_ms": self.duration_ms,
            "statistics": self.statistics,
        }
