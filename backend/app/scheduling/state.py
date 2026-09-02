"""Mutable solver state: who is booked when, and whether a placement is legal.

The state enforces the rules that depend on *other* assignments and therefore
cannot be pre-computed: no overlapping candidate interviews, no overlapping
faculty interviews, no double-booked panel, break periods, and per-day caps.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date

from app.models.enums import ConstraintPriority, ConstraintType
from app.scheduling.types import (Assignment, ConstraintOutcome, PanelSpec,
                                  SchedulingContext)
from app.utils.timeutils import Interval


class SolutionState:
    def __init__(self, ctx: SchedulingContext) -> None:
        self.ctx = ctx
        self.break_minutes = max(0, ctx.options.break_minutes)
        self.faculty_busy: dict[tuple[int, date], list[Interval]] = defaultdict(list)
        self.panel_busy: dict[tuple[int, date], list[Interval]] = defaultdict(list)
        self.candidate_busy: dict[tuple[int, date], list[Interval]] = defaultdict(list)
        self.faculty_day_count: dict[tuple[int, date], int] = defaultdict(int)
        self.faculty_total: dict[int, int] = defaultdict(int)
        self.panel_total: dict[int, int] = defaultdict(int)
        self.assignments: dict[int, Assignment] = {}

        for booking in ctx.existing:
            self._occupy(booking.candidate_id, booking.panel_id, booking.faculty_ids,
                         booking.day, booking.slot, +1)

    # ------------------------------------------------------------------ helpers
    def blocking(self, slot: Interval) -> Interval:
        """The slot plus the mandatory break that must follow it."""
        return Interval(slot.start, min(24 * 60 - 1, slot.end + self.break_minutes))

    def _occupy(self, candidate_id: int, panel_id: int | None, faculty_ids: list[int],
                day: date, slot: Interval, sign: int) -> None:
        block = self.blocking(slot)
        targets: list[tuple[dict, tuple]] = [
            (self.candidate_busy, (candidate_id, day)),
        ]
        if panel_id is not None:
            targets.append((self.panel_busy, (panel_id, day)))
        for fid in faculty_ids:
            targets.append((self.faculty_busy, (fid, day)))
        for store, key in targets:
            if sign > 0:
                store[key].append(block)
            else:
                bucket = store.get(key)
                if bucket and block in bucket:
                    bucket.remove(block)
        for fid in faculty_ids:
            self.faculty_day_count[(fid, day)] += sign
            self.faculty_total[fid] += sign
        if panel_id is not None:
            self.panel_total[panel_id] += sign

    def _free(self, store: dict, key: tuple, block: Interval) -> bool:
        return not any(existing.overlaps(block) for existing in store.get(key, ()))

    def faculty_cap(self, faculty_id: int) -> int:
        spec = self.ctx.faculty.get(faculty_id)
        if spec and spec.max_per_day:
            return int(spec.max_per_day)
        return int(self.ctx.options.max_interviews_per_faculty_per_day)

    # -------------------------------------------------------------- availability
    def faculty_can_take(self, faculty_id: int, day: date, slot: Interval) -> bool:
        spec = self.ctx.faculty.get(faculty_id)
        if spec is None or not spec.is_free(day, slot):
            return False
        if self.faculty_day_count[(faculty_id, day)] >= self.faculty_cap(faculty_id):
            return False
        return self._free(self.faculty_busy, (faculty_id, day), self.blocking(slot))

    def candidate_free(self, candidate_id: int, day: date, slot: Interval) -> bool:
        return self._free(self.candidate_busy, (candidate_id, day), self.blocking(slot))

    def panel_free(self, panel_id: int, day: date, slot: Interval) -> bool:
        return self._free(self.panel_busy, (panel_id, day), self.blocking(slot))

    def select_faculty(self, panel: PanelSpec, day: date,
                       slot: Interval) -> list[int] | None:
        """Pick the required number of panel members for a slot.

        Mandatory members must be available.  Remaining seats go to the least
        loaded available members, which spreads the workload across faculty.
        """
        available = [fid for fid in panel.member_ids
                     if self.faculty_can_take(fid, day, slot)]
        available_set = set(available)
        if not panel.mandatory_ids.issubset(available_set):
            return None
        required = max(1, panel.minimum_panel_size)
        if len(available) < required:
            return None
        chosen = [fid for fid in available if fid in panel.mandatory_ids]
        rest = sorted((fid for fid in available if fid not in panel.mandatory_ids),
                      key=lambda f: (self.faculty_total[f],
                                     self.faculty_day_count[(f, day)], f))
        for fid in rest:
            if len(chosen) >= required:
                break
            chosen.append(fid)
        if len(chosen) < required:
            return None
        return sorted(chosen[:max(required, min(len(chosen), panel.maximum_panel_size))])

    # -------------------------------------------------------------- dynamic rules
    def dynamic_outcomes(self, faculty_ids: list[int], panel_id: int,
                         day: date) -> list[ConstraintOutcome]:
        """Rules whose value depends on the current partial solution."""
        outcomes: list[ConstraintOutcome] = []
        for constraint in self.ctx.constraints:
            weight = (self.ctx.options.weight_for(constraint.priority)
                      * constraint.weight_multiplier)
            if constraint.constraint_type == ConstraintType.MAX_INTERVIEWS_PER_FACULTY:
                cap = int(constraint.parameters.get(
                    "max_per_day", self.ctx.options.max_interviews_per_faculty_per_day))
                worst = max((self.faculty_day_count[(f, day)] for f in faculty_ids),
                            default=0)
                ok = worst < cap
                outcomes.append(ConstraintOutcome(
                    constraint.constraint_type.value, constraint.priority.value, ok,
                    weight if ok else 0.0,
                    f"Highest faculty load on {day} is {worst}/{cap}"))
            elif constraint.constraint_type == ConstraintType.LOAD_BALANCE:
                loads = [self.faculty_total[f] for f in faculty_ids] or [0]
                avg = sum(loads) / len(loads)
                cap = max(1.0, float(constraint.parameters.get("target_max", 8)))
                ratio = max(0.0, 1.0 - min(1.0, avg / cap))
                outcomes.append(ConstraintOutcome(
                    constraint.constraint_type.value, constraint.priority.value, True,
                    weight * ratio, f"Average faculty load {avg:.1f}"))
            elif constraint.constraint_type == ConstraintType.BREAK_BETWEEN_INTERVIEWS:
                outcomes.append(ConstraintOutcome(
                    constraint.constraint_type.value, constraint.priority.value, True,
                    weight, f"{self.break_minutes} min break preserved"))
        return outcomes

    def hard_dynamic_violation(self, faculty_ids: list[int], day: date) -> str | None:
        for constraint in self.ctx.constraints:
            if (constraint.constraint_type == ConstraintType.MAX_INTERVIEWS_PER_FACULTY
                    and constraint.priority == ConstraintPriority.HARD):
                cap = int(constraint.parameters.get(
                    "max_per_day", self.ctx.options.max_interviews_per_faculty_per_day))
                for fid in faculty_ids:
                    if self.faculty_day_count[(fid, day)] >= cap:
                        return (f"{constraint.name}: faculty {fid} already has "
                                f"{cap} interview(s) on {day}")
        return None

    # -------------------------------------------------------------------- commit
    def commit(self, assignment: Assignment) -> None:
        self._occupy(assignment.candidate_id, assignment.panel_id,
                     assignment.faculty_ids, assignment.day, assignment.slot, +1)
        self.assignments[assignment.candidate_id] = assignment

    def rollback(self, assignment: Assignment) -> None:
        self._occupy(assignment.candidate_id, assignment.panel_id,
                     assignment.faculty_ids, assignment.day, assignment.slot, -1)
        self.assignments.pop(assignment.candidate_id, None)

    @property
    def total_score(self) -> float:
        return sum(a.score for a in self.assignments.values())
