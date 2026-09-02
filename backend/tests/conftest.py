from __future__ import annotations

import os
import sys
from datetime import date, time
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_academisync.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key")

from app.models.enums import ConstraintPriority, ConstraintType  # noqa: E402
from app.scheduling.types import (CandidateSpec, ConstraintSpec, FacultySpec,  # noqa: E402
                                  PanelSpec, SchedulingContext, SchedulingOptions)
from app.utils.timeutils import Interval, parse_time  # noqa: E402

DAY1 = date(2026, 3, 2)
DAY2 = date(2026, 3, 3)


def iv(start: str, end: str) -> Interval:
    return Interval.from_times(parse_time(start), parse_time(end))


def make_faculty(fid: int, name: str, days: dict[date, list[Interval]],
                 department: str | None = "CSE", max_per_day: int | None = None
                 ) -> FacultySpec:
    return FacultySpec(id=fid, code=f"F{fid:03d}", name=name, department=department,
                       max_per_day=max_per_day, free_slots=days)


def make_panel(pid: int, members: list[int], minimum: int = 2, maximum: int = 3,
               department: str | None = "CSE", mandatory: set[int] | None = None
               ) -> PanelSpec:
    return PanelSpec(id=pid, code=f"P{pid}", name=f"Panel {pid}", member_ids=members,
                     mandatory_ids=mandatory or set(), department=department,
                     minimum_panel_size=minimum, maximum_panel_size=maximum)


def make_candidate(cid: int, **kwargs) -> CandidateSpec:
    return CandidateSpec(id=cid, code=f"C{cid:03d}", name=f"Candidate {cid}",
                         department=kwargs.pop("department", "CSE"), **kwargs)


def default_constraints() -> list[ConstraintSpec]:
    """Mirrors the rows seeded into `scheduling_constraints`."""
    return [
        ConstraintSpec(None, "Candidate availability", ConstraintType.CANDIDATE_UNAVAILABLE,
                       ConstraintPriority.HARD),
        ConstraintSpec(None, "Faculty availability", ConstraintType.FACULTY_UNAVAILABLE,
                       ConstraintPriority.HARD),
        ConstraintSpec(None, "Panel size", ConstraintType.PANEL_SIZE,
                       ConstraintPriority.HARD),
        ConstraintSpec(None, "Preferred date", ConstraintType.CANDIDATE_PREFERRED_DATE,
                       ConstraintPriority.HIGH),
        ConstraintSpec(None, "Preferred time", ConstraintType.CANDIDATE_PREFERRED_TIME,
                       ConstraintPriority.MEDIUM),
        ConstraintSpec(None, "Preferred panel", ConstraintType.PREFERRED_PANEL,
                       ConstraintPriority.LOW),
        ConstraintSpec(None, "Compact schedule", ConstraintType.EARLIEST_SLOT,
                       ConstraintPriority.FLEXIBLE),
        ConstraintSpec(None, "Balance faculty load", ConstraintType.LOAD_BALANCE,
                       ConstraintPriority.FLEXIBLE),
    ]


def make_options(**kwargs) -> SchedulingOptions:
    params = dict(
        dates=[DAY1],
        duration_minutes=30,
        break_minutes=10,
        granularity_minutes=15,
        day_start=time(9, 0),
        day_end=time(17, 0),
        max_interviews_per_faculty_per_day=12,
        algorithm="backtracking",
        priority_weights={"HARD": 1000.0, "HIGH": 100.0, "MEDIUM": 50.0,
                          "LOW": 20.0, "FLEXIBLE": 5.0},
    )
    params.update(kwargs)
    return SchedulingOptions(**params)


def make_context(candidates, faculty, panels, constraints=None, options=None,
                 existing=None) -> SchedulingContext:
    return SchedulingContext(
        candidates=candidates,
        faculty={f.id: f for f in faculty},
        panels=panels,
        constraints=constraints if constraints is not None else default_constraints(),
        options=options or make_options(),
        existing=existing or [],
    )


@pytest.fixture
def simple_setup():
    """Three faculty free 09:00-13:00, one panel, three candidates."""
    free = {DAY1: [iv("09:00", "13:00")], DAY2: [iv("09:00", "13:00")]}
    faculty = [make_faculty(i, f"Faculty {i}", {k: list(v) for k, v in free.items()})
               for i in (1, 2, 3)]
    panels = [make_panel(1, [1, 2, 3])]
    candidates = [make_candidate(i) for i in (10, 11, 12)]
    return candidates, faculty, panels
