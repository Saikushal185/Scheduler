"""Turning a pre-scored option into a committed assignment.

Placement is where the state-dependent rules run: the actual panel members are
picked, overlaps against the partial solution are re-checked, and the final
optimisation score is computed.
"""
from __future__ import annotations

from app.scheduling.constraints import evaluate_static
from app.scheduling.state import SolutionState
from app.scheduling.types import (Assignment, CandidateSpec, PanelSpec,
                                  SchedulingContext, SlotOption)


def try_build_assignment(ctx: SchedulingContext, state: SolutionState,
                         candidate: CandidateSpec, option: SlotOption,
                         panels: dict[int, PanelSpec]) -> tuple[Assignment | None, str]:
    panel = panels[option.panel_id]
    if not state.candidate_free(candidate.id, option.day, option.slot):
        return None, "Candidate already has an interview overlapping this slot"
    if not state.panel_free(panel.id, option.day, option.slot):
        return None, f"Panel {panel.code} is already booked for this slot"

    faculty_ids = state.select_faculty(panel, option.day, option.slot)
    if not faculty_ids:
        return None, (f"Panel {panel.code} could not field "
                      f"{panel.minimum_panel_size} free faculty for this slot")

    violation = state.hard_dynamic_violation(faculty_ids, option.day)
    if violation:
        return None, violation

    feasible, outcomes, reason = evaluate_static(
        ctx, candidate, panel, option.day, option.slot, faculty_ids)
    if not feasible:
        return None, reason or "Hard constraint violated"

    outcomes = outcomes + state.dynamic_outcomes(faculty_ids, panel.id, option.day)
    return Assignment(
        candidate_id=candidate.id,
        panel_id=panel.id,
        faculty_ids=faculty_ids,
        day=option.day,
        slot=option.slot,
        score=sum(o.score for o in outcomes),
        outcomes=outcomes,
    ), ""
