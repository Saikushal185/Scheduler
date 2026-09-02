"""Modular constraint-based scheduling engine."""
from app.scheduling.engine import SchedulingEngine, list_algorithms
from app.scheduling.types import (Assignment, CandidateSpec, ConstraintSpec,
                                  ExistingBooking, FacultySpec, PanelSpec,
                                  SchedulingContext, SchedulingOptions,
                                  SchedulingResult, SlotOption, UnscheduledCandidate)

__all__ = [
    "SchedulingEngine", "list_algorithms", "SchedulingContext", "SchedulingOptions",
    "SchedulingResult", "CandidateSpec", "FacultySpec", "PanelSpec", "ConstraintSpec",
    "Assignment", "SlotOption", "UnscheduledCandidate", "ExistingBooking",
]
