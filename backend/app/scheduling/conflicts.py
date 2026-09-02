"""Verification pass over a produced schedule.

Even though the solver refuses illegal placements, the finished schedule is
re-checked independently.  The same routine is reused to validate manual
administrator overrides.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date

from app.scheduling.types import Assignment, Conflict, SchedulingContext
from app.utils.timeutils import Interval


def _pairs_overlap(a: Interval, b: Interval, buffer_minutes: int = 0) -> bool:
    left = Interval(a.start, a.end + buffer_minutes)
    right = Interval(b.start, b.end + buffer_minutes)
    return left.overlaps(right)


def detect_conflicts(ctx: SchedulingContext,
                     assignments: list[Assignment]) -> list[Conflict]:
    conflicts: list[Conflict] = []
    by_candidate: dict[tuple[int, date], list[Assignment]] = defaultdict(list)
    by_faculty: dict[tuple[int, date], list[Assignment]] = defaultdict(list)
    by_panel: dict[tuple[int, date], list[Assignment]] = defaultdict(list)

    for booking in ctx.existing:
        pseudo = Assignment(booking.candidate_id, booking.panel_id or -1,
                            booking.faculty_ids, booking.day, booking.slot, 0.0)
        by_candidate[(booking.candidate_id, booking.day)].append(pseudo)
        for fid in booking.faculty_ids:
            by_faculty[(fid, booking.day)].append(pseudo)
        if booking.panel_id is not None:
            by_panel[(booking.panel_id, booking.day)].append(pseudo)

    for assignment in assignments:
        by_candidate[(assignment.candidate_id, assignment.day)].append(assignment)
        for fid in assignment.faculty_ids:
            by_faculty[(fid, assignment.day)].append(assignment)
        by_panel[(assignment.panel_id, assignment.day)].append(assignment)

    break_minutes = ctx.options.break_minutes

    for (candidate_id, day), items in by_candidate.items():
        for first, second in _overlapping_pairs(items):
            conflicts.append(Conflict(
                kind="CANDIDATE_DOUBLE_BOOKED",
                message=(f"Candidate {candidate_id} has overlapping interviews on "
                         f"{day}: {first.slot} and {second.slot}"),
                candidate_ids=[candidate_id]))

    for (faculty_id, day), items in by_faculty.items():
        for first, second in _overlapping_pairs(items, break_minutes):
            kind = ("FACULTY_DOUBLE_BOOKED"
                    if _pairs_overlap(first.slot, second.slot) else "BREAK_VIOLATION")
            conflicts.append(Conflict(
                kind=kind,
                message=(f"Faculty {faculty_id} on {day}: {first.slot} and "
                         f"{second.slot} leave less than {break_minutes} min between "
                         "interviews" if kind == "BREAK_VIOLATION" else
                         f"Faculty {faculty_id} has overlapping interviews on {day}: "
                         f"{first.slot} and {second.slot}"),
                faculty_ids=[faculty_id],
                candidate_ids=[first.candidate_id, second.candidate_id]))

    for (panel_id, day), items in by_panel.items():
        for first, second in _overlapping_pairs(items):
            conflicts.append(Conflict(
                kind="PANEL_DOUBLE_BOOKED",
                message=(f"Panel {panel_id} is booked twice on {day}: "
                         f"{first.slot} and {second.slot}"),
                panel_ids=[panel_id],
                candidate_ids=[first.candidate_id, second.candidate_id]))

    for assignment in assignments:
        for fid in assignment.faculty_ids:
            spec = ctx.faculty.get(fid)
            if spec and not spec.is_free(assignment.day, assignment.slot):
                conflicts.append(Conflict(
                    kind="OUTSIDE_FREE_SLOT",
                    message=(f"Faculty {fid} is not free on {assignment.day} "
                             f"at {assignment.slot}"),
                    faculty_ids=[fid], candidate_ids=[assignment.candidate_id]))
        if assignment.slot.duration != ctx.options.duration_minutes:
            conflicts.append(Conflict(
                kind="DURATION_MISMATCH",
                message=(f"Interview for candidate {assignment.candidate_id} lasts "
                         f"{assignment.slot.duration} min, expected "
                         f"{ctx.options.duration_minutes} min"),
                candidate_ids=[assignment.candidate_id]))
    return conflicts


def _overlapping_pairs(items: list[Assignment], buffer_minutes: int = 0):
    ordered = sorted(items, key=lambda a: a.slot.start)
    for i in range(len(ordered)):
        for j in range(i + 1, len(ordered)):
            if ordered[j].slot.start >= ordered[i].slot.end + buffer_minutes:
                break
            if ordered[i] is ordered[j]:
                continue
            if _pairs_overlap(ordered[i].slot, ordered[j].slot, buffer_minutes):
                yield ordered[i], ordered[j]
