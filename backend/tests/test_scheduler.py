"""Behavioural tests for the constraint-based scheduling engine."""
from __future__ import annotations

from datetime import date, time

import pytest

from app.models.enums import ConstraintPriority, ConstraintType
from app.scheduling.conflicts import detect_conflicts
from app.scheduling.domain import generate_options
from app.scheduling.engine import SchedulingEngine
from app.scheduling.types import ConstraintSpec, ExistingBooking
from tests.conftest import (DAY1, DAY2, default_constraints, iv, make_candidate,
                            make_context, make_faculty, make_options, make_panel)

ALGORITHMS = ["greedy", "backtracking"]


def run(ctx, algorithm="backtracking"):
    return SchedulingEngine(algorithm).run(ctx)


# --------------------------------------------------------------- core guarantees
@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_every_candidate_gets_a_conflict_free_slot(simple_setup, algorithm):
    candidates, faculty, panels = simple_setup
    result = run(make_context(candidates, faculty, panels), algorithm)
    assert result.scheduled_count == 3
    assert result.unscheduled == []
    assert result.conflicts == []
    assert result.success_rate == 100.0


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_a_candidate_never_gets_overlapping_interviews(simple_setup, algorithm):
    candidates, faculty, panels = simple_setup
    # two panels sharing no faculty, so the same candidate could be double booked
    faculty += [make_faculty(i, f"Faculty {i}", {DAY1: [iv("09:00", "13:00")]})
                for i in (4, 5, 6)]
    panels.append(make_panel(2, [4, 5, 6]))
    result = run(make_context(candidates, faculty, panels), algorithm)
    seen: dict[int, list] = {}
    for assignment in result.assignments:
        seen.setdefault(assignment.candidate_id, []).append(assignment)
    assert all(len(v) == 1 for v in seen.values())
    assert not [c for c in result.conflicts if c.kind == "CANDIDATE_DOUBLE_BOOKED"]


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_faculty_are_never_double_booked_across_panels(algorithm):
    """Faculty 2 sits on both panels and must not be booked twice at once."""
    faculty = [make_faculty(i, f"Faculty {i}", {DAY1: [iv("09:00", "10:00")]})
               for i in (1, 2, 3)]
    panels = [make_panel(1, [1, 2]), make_panel(2, [2, 3])]
    candidates = [make_candidate(i) for i in (10, 11)]
    result = run(make_context(candidates, faculty, panels), algorithm)
    booked: dict[tuple[int, str], int] = {}
    for assignment in result.assignments:
        for fid in assignment.faculty_ids:
            key = (fid, str(assignment.slot))
            booked[key] = booked.get(key, 0) + 1
    assert all(count == 1 for count in booked.values())
    assert result.conflicts == []


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_break_period_is_enforced_between_consecutive_interviews(algorithm):
    faculty = [make_faculty(i, f"Faculty {i}", {DAY1: [iv("09:00", "11:00")]})
               for i in (1, 2)]
    panels = [make_panel(1, [1, 2])]
    candidates = [make_candidate(i) for i in (10, 11)]
    ctx = make_context(candidates, faculty, panels,
                       options=make_options(break_minutes=15))
    result = run(ctx, algorithm)
    assert result.scheduled_count == 2
    slots = sorted((a.slot for a in result.assignments), key=lambda s: s.start)
    assert slots[1].start - slots[0].end >= 15
    assert not [c for c in result.conflicts if c.kind == "BREAK_VIOLATION"]


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_interviews_only_land_inside_faculty_free_slots(algorithm):
    """Faculty are busy 10:00-11:00, so nothing may be booked there."""
    free = {DAY1: [iv("09:00", "10:00"), iv("11:00", "13:00")]}
    faculty = [make_faculty(i, f"Faculty {i}", {DAY1: list(free[DAY1])})
               for i in (1, 2)]
    panels = [make_panel(1, [1, 2])]
    candidates = [make_candidate(i) for i in range(10, 14)]
    result = run(make_context(candidates, faculty, panels), algorithm)
    assert result.assignments
    for assignment in result.assignments:
        assert not assignment.slot.overlaps(iv("10:00", "11:00"))
    assert not [c for c in result.conflicts if c.kind == "OUTSIDE_FREE_SLOT"]


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_interview_duration_is_respected(algorithm):
    faculty = [make_faculty(i, f"Faculty {i}", {DAY1: [iv("09:00", "12:00")]})
               for i in (1, 2)]
    ctx = make_context([make_candidate(10)], faculty, [make_panel(1, [1, 2])],
                       options=make_options(duration_minutes=45))
    result = run(ctx, algorithm)
    assert result.assignments[0].slot.duration == 45


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_panel_minimum_size_is_a_hard_constraint(algorithm):
    """Only one of the three panel members is free - nothing can be scheduled."""
    faculty = [make_faculty(1, "Faculty 1", {DAY1: [iv("09:00", "12:00")]}),
               make_faculty(2, "Faculty 2", {DAY1: []}),
               make_faculty(3, "Faculty 3", {DAY1: []})]
    ctx = make_context([make_candidate(10)], faculty, [make_panel(1, [1, 2, 3],
                                                                 minimum=2)])
    result = run(ctx, algorithm)
    assert result.scheduled_count == 0
    assert len(result.unscheduled) == 1
    assert "free faculty" in result.unscheduled[0].reason.lower() or \
           "no feasible slot" in result.unscheduled[0].reason.lower()


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_assigned_panel_size_matches_the_requirement(algorithm):
    faculty = [make_faculty(i, f"Faculty {i}", {DAY1: [iv("09:00", "12:00")]})
               for i in (1, 2, 3, 4)]
    ctx = make_context([make_candidate(10)], faculty,
                       [make_panel(1, [1, 2, 3, 4], minimum=3, maximum=4)])
    result = run(ctx, algorithm)
    assert len(result.assignments[0].faculty_ids) == 3


def test_mandatory_panel_member_must_be_available():
    faculty = [make_faculty(1, "Chair", {DAY1: []}),
               make_faculty(2, "Faculty 2", {DAY1: [iv("09:00", "12:00")]}),
               make_faculty(3, "Faculty 3", {DAY1: [iv("09:00", "12:00")]})]
    ctx = make_context([make_candidate(10)], faculty,
                       [make_panel(1, [1, 2, 3], minimum=2, mandatory={1})])
    result = run(ctx)
    assert result.scheduled_count == 0
    assert "mandatory" in " ".join(result.unscheduled[0].details).lower()


# ------------------------------------------------------------ flexible priorities
def test_candidate_preferred_date_is_honoured_when_possible():
    faculty = [make_faculty(i, f"Faculty {i}",
                            {DAY1: [iv("09:00", "12:00")], DAY2: [iv("09:00", "12:00")]})
               for i in (1, 2)]
    ctx = make_context([make_candidate(10, preferred_date=DAY2)], faculty,
                       [make_panel(1, [1, 2])], options=make_options(dates=[DAY1, DAY2]))
    result = run(ctx)
    assert result.assignments[0].day == DAY2
    outcome = next(o for o in result.assignments[0].outcomes
                   if o.constraint_type == "CANDIDATE_PREFERRED_DATE")
    assert outcome.satisfied and outcome.score > 0


def test_candidate_preferred_time_is_honoured_when_possible():
    faculty = [make_faculty(i, f"Faculty {i}", {DAY1: [iv("09:00", "16:00")]})
               for i in (1, 2)]
    ctx = make_context([make_candidate(10, preferred_time=time(14, 0))], faculty,
                       [make_panel(1, [1, 2])])
    result = run(ctx)
    assert result.assignments[0].slot.start_time == time(14, 0)


def test_preferred_panel_is_used_when_free_but_is_not_binding():
    faculty = [make_faculty(i, f"Faculty {i}", {DAY1: [iv("09:00", "10:00")]})
               for i in (1, 2, 3, 4)]
    panels = [make_panel(1, [1, 2]), make_panel(2, [3, 4])]
    candidates = [make_candidate(10, preferred_panel_code="P2"),
                  make_candidate(11, preferred_panel_code="P2")]
    result = run(make_context(candidates, faculty, panels))
    assert result.scheduled_count == 2
    used = {a.panel_id for a in result.assignments}
    # both wanted P2; the second falls back to the alternative panel
    assert used == {1, 2}


def test_hard_preferred_date_blocks_other_days():
    """Raising the preference to HARD turns it into a filter."""
    constraints = [c for c in default_constraints()
                   if c.constraint_type != ConstraintType.CANDIDATE_PREFERRED_DATE]
    constraints.append(ConstraintSpec(None, "Must be preferred date",
                                      ConstraintType.CANDIDATE_PREFERRED_DATE,
                                      ConstraintPriority.HARD))
    faculty = [make_faculty(i, f"Faculty {i}", {DAY1: [iv("09:00", "12:00")]})
               for i in (1, 2)]
    ctx = make_context([make_candidate(10, preferred_date=DAY2)], faculty,
                       [make_panel(1, [1, 2])], constraints=constraints,
                       options=make_options(dates=[DAY1]))
    result = run(ctx)
    assert result.scheduled_count == 0
    assert result.unscheduled[0].candidate_id == 10


def test_candidate_availability_window_is_a_hard_filter():
    faculty = [make_faculty(i, f"Faculty {i}", {DAY1: [iv("09:00", "17:00")]})
               for i in (1, 2)]
    candidate = make_candidate(10, availability={DAY1: [iv("15:00", "16:00")]})
    result = run(make_context([candidate], faculty, [make_panel(1, [1, 2])]))
    assert result.assignments[0].slot.start >= iv("15:00", "16:00").start
    assert result.assignments[0].slot.end <= iv("15:00", "16:00").end


def test_candidate_with_no_matching_availability_is_reported_unscheduled():
    faculty = [make_faculty(i, f"Faculty {i}", {DAY1: [iv("09:00", "11:00")]})
               for i in (1, 2)]
    candidate = make_candidate(10, availability={DAY1: [iv("15:00", "16:00")]})
    result = run(make_context([candidate], faculty, [make_panel(1, [1, 2])]))
    assert result.scheduled_count == 0
    reported = result.unscheduled[0]
    assert reported.candidate_id == 10
    assert reported.reason  # every unscheduled candidate carries a reason
    assert reported.details


def test_blocked_period_constraint_keeps_the_slot_empty():
    constraints = default_constraints() + [
        ConstraintSpec(None, "Lunch break", ConstraintType.BLOCKED_PERIOD,
                       ConstraintPriority.HARD,
                       parameters={"date": DAY1.isoformat(), "start_time": "12:00",
                                   "end_time": "13:00"})]
    faculty = [make_faculty(i, f"Faculty {i}", {DAY1: [iv("09:00", "17:00")]})
               for i in (1, 2)]
    candidates = [make_candidate(i) for i in range(10, 18)]
    result = run(make_context(candidates, faculty, [make_panel(1, [1, 2])],
                              constraints=constraints))
    assert result.assignments
    for assignment in result.assignments:
        assert not assignment.slot.overlaps(iv("12:00", "13:00"))


def test_max_interviews_per_faculty_per_day_caps_the_schedule():
    faculty = [make_faculty(i, f"Faculty {i}", {DAY1: [iv("09:00", "17:00")]})
               for i in (1, 2)]
    ctx = make_context([make_candidate(i) for i in range(10, 20)], faculty,
                       [make_panel(1, [1, 2])],
                       options=make_options(max_interviews_per_faculty_per_day=3))
    result = run(ctx)
    assert result.scheduled_count == 3
    assert len(result.unscheduled) == 7
    assert all(u.reason for u in result.unscheduled)


def test_per_faculty_daily_cap_overrides_the_global_default():
    faculty = [make_faculty(1, "Faculty 1", {DAY1: [iv("09:00", "17:00")]},
                            max_per_day=2),
               make_faculty(2, "Faculty 2", {DAY1: [iv("09:00", "17:00")]})]
    ctx = make_context([make_candidate(i) for i in range(10, 16)], faculty,
                       [make_panel(1, [1, 2], minimum=2)])
    result = run(ctx)
    assert result.scheduled_count == 2


# --------------------------------------------------------------- existing bookings
def test_existing_bookings_are_respected():
    """A locked interview at 09:00-09:30 (plus a 10 min break) blocks 09:00-09:40."""
    faculty = [make_faculty(i, f"Faculty {i}", {DAY1: [iv("09:00", "11:00")]})
               for i in (1, 2)]
    existing = [ExistingBooking(interview_id=1, candidate_id=99, panel_id=1,
                                faculty_ids=[1, 2], day=DAY1,
                                slot=iv("09:00", "09:30"))]
    ctx = make_context([make_candidate(10)], faculty, [make_panel(1, [1, 2])],
                       existing=existing)
    result = run(ctx)
    assert result.scheduled_count == 1
    assert result.assignments[0].slot.start >= iv("09:40", "10:00").start
    assert result.conflicts == []


def test_existing_booking_can_make_a_candidate_unschedulable():
    """No room is left after the locked interview, and the reason says so."""
    faculty = [make_faculty(i, f"Faculty {i}", {DAY1: [iv("09:00", "10:00")]})
               for i in (1, 2)]
    existing = [ExistingBooking(interview_id=1, candidate_id=99, panel_id=1,
                                faculty_ids=[1, 2], day=DAY1,
                                slot=iv("09:00", "09:30"))]
    ctx = make_context([make_candidate(10)], faculty, [make_panel(1, [1, 2])],
                       existing=existing)
    result = run(ctx)
    assert result.scheduled_count == 0
    assert result.unscheduled[0].details


# ------------------------------------------------------------------ optimisation
def test_backtracking_is_at_least_as_good_as_greedy():
    """Scarce slots: the search must not do worse than the greedy baseline."""
    faculty = [make_faculty(1, "F1", {DAY1: [iv("09:00", "10:00")]}),
               make_faculty(2, "F2", {DAY1: [iv("09:00", "10:00")]}),
               make_faculty(3, "F3", {DAY1: [iv("09:30", "10:00")]}),
               make_faculty(4, "F4", {DAY1: [iv("09:30", "10:00")]})]
    panels = [make_panel(1, [1, 2]), make_panel(2, [3, 4])]
    candidates = [make_candidate(10, preferred_time=__import__("datetime").time(9, 0)),
                  make_candidate(11), make_candidate(12)]
    ctx = make_context(candidates, faculty, panels)
    greedy = run(ctx, "greedy")
    search = run(ctx, "backtracking")
    assert search.scheduled_count >= greedy.scheduled_count
    assert search.total_score >= greedy.total_score - 1e-6


def test_scheduling_is_deterministic():
    faculty = [make_faculty(i, f"Faculty {i}", {DAY1: [iv("09:00", "12:00")]})
               for i in (1, 2, 3)]
    ctx = make_context([make_candidate(i) for i in (10, 11)], faculty,
                       [make_panel(1, [1, 2, 3])])
    first = run(ctx).to_dict()["assignments"]
    second = run(ctx).to_dict()["assignments"]
    assert first == second


def test_faculty_workload_is_spread_across_available_members():
    faculty = [make_faculty(i, f"Faculty {i}", {DAY1: [iv("09:00", "17:00")]})
               for i in (1, 2, 3, 4)]
    ctx = make_context([make_candidate(i) for i in range(10, 16)], faculty,
                       [make_panel(1, [1, 2, 3, 4], minimum=2, maximum=2)])
    result = run(ctx, "greedy")
    loads: dict[int, int] = {}
    for assignment in result.assignments:
        for fid in assignment.faculty_ids:
            loads[fid] = loads.get(fid, 0) + 1
    assert len(loads) == 4, "every panel member should take part of the load"
    assert max(loads.values()) - min(loads.values()) <= 1


def test_result_reports_reason_for_every_unscheduled_candidate():
    faculty = [make_faculty(i, f"Faculty {i}", {DAY1: [iv("09:00", "09:30")]})
               for i in (1, 2)]
    candidates = [make_candidate(i) for i in range(10, 15)]
    result = run(make_context(candidates, faculty, [make_panel(1, [1, 2])]))
    assert result.scheduled_count == 1
    assert len(result.unscheduled) == 4
    for entry in result.unscheduled:
        assert entry.reason.strip()


def test_empty_input_produces_an_empty_schedule():
    result = run(make_context([], [], []))
    assert result.scheduled_count == 0
    assert result.unscheduled == []
    assert result.conflicts == []


def test_domain_generation_reports_combination_counts():
    faculty = [make_faculty(i, f"Faculty {i}", {DAY1: [iv("09:00", "10:00")]})
               for i in (1, 2)]
    ctx = make_context([make_candidate(10)], faculty, [make_panel(1, [1, 2])])
    options, blocked = generate_options(ctx)
    assert blocked == {}
    assert len(options[10]) == 3  # 09:00, 09:15, 09:30 starts for a 30 min interview


def test_conflict_detector_flags_a_manually_broken_schedule():
    """Directly verifies the independent conflict checker."""
    faculty = [make_faculty(i, f"Faculty {i}", {DAY1: [iv("09:00", "12:00")]})
               for i in (1, 2)]
    ctx = make_context([make_candidate(10), make_candidate(11)], faculty,
                       [make_panel(1, [1, 2])])
    result = run(ctx)
    broken = result.assignments[1]
    clashing = type(broken)(candidate_id=broken.candidate_id, panel_id=broken.panel_id,
                            faculty_ids=broken.faculty_ids,
                            day=result.assignments[0].day,
                            slot=result.assignments[0].slot, score=0.0)
    conflicts = detect_conflicts(ctx, [result.assignments[0], clashing])
    kinds = {c.kind for c in conflicts}
    assert "FACULTY_DOUBLE_BOOKED" in kinds
    assert "PANEL_DOUBLE_BOOKED" in kinds


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_larger_instance_stays_conflict_free(algorithm):
    faculty = [make_faculty(i, f"Faculty {i}",
                            {DAY1: [iv("09:00", "13:00")], DAY2: [iv("09:00", "13:00")]})
               for i in range(1, 13)]
    panels = [make_panel(p, [1 + (p - 1) * 3, 2 + (p - 1) * 3, 3 + (p - 1) * 3])
              for p in range(1, 5)]
    candidates = [make_candidate(i, preferred_date=DAY1 if i % 2 else DAY2)
                  for i in range(100, 140)]
    ctx = make_context(candidates, faculty, panels,
                       options=make_options(dates=[DAY1, DAY2]))
    result = run(ctx, algorithm)
    assert result.conflicts == []
    assert result.scheduled_count >= 30
    assert result.duration_ms < 20000
