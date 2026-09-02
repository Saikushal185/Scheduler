"""Constraint evaluation.

Every rule is a small function registered against a `ConstraintType`.  A rule
returns a `ConstraintOutcome`; when a HARD rule reports `satisfied=False` the
combination is discarded, otherwise the outcome's score feeds the optimiser.

Adding a new rule means writing one function and registering it - the solver
itself never changes.
"""
from __future__ import annotations

from datetime import date
from typing import Callable, Protocol

from app.models.enums import ConstraintPriority, ConstraintType
from app.scheduling.types import (CandidateSpec, ConstraintOutcome, ConstraintSpec,
                                  PanelSpec, SchedulingContext)
from app.utils.timeutils import Interval, parse_time, to_minutes


class Evaluator(Protocol):
    def __call__(self, ctx: SchedulingContext, constraint: ConstraintSpec,
                 candidate: CandidateSpec, panel: PanelSpec, day: date,
                 slot: Interval, faculty_ids: list[int]) -> ConstraintOutcome | None:
        ...


_REGISTRY: dict[ConstraintType, Evaluator] = {}


def register(ctype: ConstraintType) -> Callable[[Evaluator], Evaluator]:
    def decorator(fn: Evaluator) -> Evaluator:
        _REGISTRY[ctype] = fn
        return fn
    return decorator


def _outcome(constraint: ConstraintSpec, ctx: SchedulingContext, satisfied: bool,
             detail: str, *, ratio: float = 1.0) -> ConstraintOutcome:
    """Score = priority band weight x rule multiplier x satisfaction ratio."""
    weight = ctx.options.weight_for(constraint.priority) * constraint.weight_multiplier
    score = weight * ratio if satisfied else 0.0
    return ConstraintOutcome(
        constraint_type=constraint.constraint_type.value,
        priority=constraint.priority.value,
        satisfied=satisfied,
        score=score,
        detail=detail,
    )


# --------------------------------------------------------------------------- rules
@register(ConstraintType.CANDIDATE_UNAVAILABLE)
def _candidate_availability(ctx, constraint, candidate, panel, day, slot, faculty_ids):
    ok = candidate.is_available(day, slot)
    return _outcome(constraint, ctx, ok,
                    "Candidate available for the slot" if ok
                    else f"Candidate not available on {day} at {slot}")


@register(ConstraintType.FACULTY_UNAVAILABLE)
def _faculty_availability(ctx, constraint, candidate, panel, day, slot, faculty_ids):
    blocked = [fid for fid in faculty_ids
               if fid in ctx.faculty and not ctx.faculty[fid].is_free(day, slot)]
    ok = not blocked
    return _outcome(constraint, ctx, ok,
                    "All assigned faculty are free" if ok
                    else f"Faculty {blocked} not free in this slot")


@register(ConstraintType.PANEL_SIZE)
def _panel_size(ctx, constraint, candidate, panel, day, slot, faculty_ids):
    required = int(constraint.parameters.get("minimum", panel.minimum_panel_size))
    maximum = int(constraint.parameters.get("maximum", panel.maximum_panel_size))
    count = len(faculty_ids)
    ok = required <= count <= max(maximum, required)
    return _outcome(constraint, ctx, ok,
                    f"{count} faculty assigned (required {required}-{maximum})")


@register(ConstraintType.REQUIRED_PANEL)
def _required_panel(ctx, constraint, candidate, panel, day, slot, faculty_ids):
    wanted = constraint.parameters.get("panel_code") or candidate.required_panel_code
    if not wanted:
        return None
    ok = panel.code.lower() == str(wanted).lower()
    return _outcome(constraint, ctx, ok,
                    f"Panel {panel.code} matches required panel {wanted}" if ok
                    else f"Panel {panel.code} is not the required panel {wanted}")


@register(ConstraintType.BLOCKED_PERIOD)
def _blocked_period(ctx, constraint, candidate, panel, day, slot, faculty_ids):
    params = constraint.parameters
    block_date = params.get("date")
    if block_date and str(block_date) != day.isoformat():
        return None
    start = parse_time(params.get("start_time")) if params.get("start_time") else None
    end = parse_time(params.get("end_time")) if params.get("end_time") else None
    if start is None or end is None:
        # whole day block
        ok = not block_date
        return _outcome(constraint, ctx, ok, f"{day} is a blocked day")
    blocked = Interval.from_times(start, end)
    ok = not blocked.overlaps(slot)
    return _outcome(constraint, ctx, ok,
                    "Outside the blocked period" if ok
                    else f"Overlaps blocked period {blocked}")


@register(ConstraintType.CANDIDATE_PREFERRED_DATE)
def _preferred_date(ctx, constraint, candidate, panel, day, slot, faculty_ids):
    preferred = candidate.preferred_date
    if preferred is None:
        return None
    if day == preferred:
        return _outcome(constraint, ctx, True, f"Scheduled on preferred date {preferred}")
    # Partial credit that decays with distance from the preferred date.
    delta = abs((day - preferred).days)
    tolerance = int(constraint.parameters.get("tolerance_days", 5))
    ratio = max(0.0, 1.0 - delta / max(1, tolerance)) * 0.5
    satisfied = constraint.priority != ConstraintPriority.HARD
    return _outcome(constraint, ctx, satisfied,
                    f"{delta} day(s) away from preferred date {preferred}", ratio=ratio)


@register(ConstraintType.CANDIDATE_PREFERRED_TIME)
def _preferred_time(ctx, constraint, candidate, panel, day, slot, faculty_ids):
    preferred = candidate.preferred_time
    if preferred is None:
        return None
    target = to_minutes(preferred)
    delta = abs(slot.start - target)
    if delta == 0:
        return _outcome(constraint, ctx, True, f"Starts at preferred time {preferred:%H:%M}")
    tolerance = int(constraint.parameters.get("tolerance_minutes", 120))
    ratio = max(0.0, 1.0 - delta / max(1, tolerance))
    satisfied = constraint.priority != ConstraintPriority.HARD or delta == 0
    return _outcome(constraint, ctx, satisfied,
                    f"{delta} min from preferred time {preferred:%H:%M}", ratio=ratio)


@register(ConstraintType.PREFERRED_PANEL)
def _preferred_panel(ctx, constraint, candidate, panel, day, slot, faculty_ids):
    wanted = candidate.preferred_panel_code or constraint.parameters.get("panel_code")
    if not wanted:
        return None
    ok = panel.code.lower() == str(wanted).lower() or panel.name.lower() == str(wanted).lower()
    return _outcome(constraint, ctx, ok,
                    f"Assigned preferred panel {panel.code}" if ok
                    else f"Alternative panel {panel.code} used instead of {wanted}")


@register(ConstraintType.DEPARTMENT_MATCH)
def _department_match(ctx, constraint, candidate, panel, day, slot, faculty_ids):
    if not candidate.department:
        return None
    panel_dept = (panel.department or "").lower()
    member_depts = {(ctx.faculty[fid].department or "").lower()
                    for fid in faculty_ids if fid in ctx.faculty}
    wanted = candidate.department.lower()
    ok = wanted == panel_dept or wanted in member_depts
    return _outcome(constraint, ctx, ok,
                    f"Panel covers department {candidate.department}" if ok
                    else f"No department match for {candidate.department}")


@register(ConstraintType.EARLIEST_SLOT)
def _earliest_slot(ctx, constraint, candidate, panel, day, slot, faculty_ids):
    """Compact the schedule: earlier days and earlier times score higher."""
    dates = ctx.options.dates
    if not dates:
        return None
    day_index = dates.index(day) if day in dates else len(dates) - 1
    day_ratio = 1.0 - (day_index / max(1, len(dates)))
    span_start = to_minutes(ctx.options.day_start) if ctx.options.day_start else 0
    span_end = to_minutes(ctx.options.day_end) if ctx.options.day_end else 24 * 60
    span = max(1, span_end - span_start)
    time_ratio = 1.0 - min(1.0, max(0.0, (slot.start - span_start) / span))
    ratio = 0.6 * day_ratio + 0.4 * time_ratio
    return _outcome(constraint, ctx, True,
                    f"Compactness score for {day} {slot}", ratio=ratio)


def evaluate_static(ctx: SchedulingContext, candidate: CandidateSpec, panel: PanelSpec,
                    day: date, slot: Interval,
                    faculty_ids: list[int]) -> tuple[bool, list[ConstraintOutcome], str | None]:
    """Run every rule that does not depend on other assignments.

    Returns (feasible, outcomes, hard_violation_reason).
    """
    outcomes: list[ConstraintOutcome] = []
    for constraint in ctx.constraints:
        evaluator = _REGISTRY.get(constraint.constraint_type)
        if evaluator is None or not constraint.applies_to(candidate):
            continue
        outcome = evaluator(ctx, constraint, candidate, panel, day, slot, faculty_ids)
        if outcome is None:
            continue
        if constraint.priority == ConstraintPriority.HARD and not outcome.satisfied:
            return False, outcomes, f"{constraint.name}: {outcome.detail}"
        outcomes.append(outcome)
    return True, outcomes, None


def registered_types() -> list[str]:
    return sorted(t.value for t in _REGISTRY)
