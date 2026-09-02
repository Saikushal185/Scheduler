"""Greedy solver: most-constrained candidate first, best-scoring slot first."""
from __future__ import annotations

from app.scheduling.algorithms.base import (SchedulerAlgorithm, Solution,
                                            register_algorithm)
from app.scheduling.placement import try_build_assignment
from app.scheduling.state import SolutionState
from app.scheduling.types import (SchedulingContext, SlotOption,
                                  UnscheduledCandidate)


@register_algorithm("greedy")
class GreedyScheduler(SchedulerAlgorithm):
    description = ("Single pass: candidates with the fewest feasible slots are "
                   "placed first, each into its highest scoring free slot.")

    def solve(self, ctx: SchedulingContext, options: dict[int, list[SlotOption]],
              blocked: dict[int, UnscheduledCandidate]) -> Solution:
        state = SolutionState(ctx)
        solution = Solution()
        panels = {p.id: p for p in ctx.panels}
        by_id = {c.id: c for c in ctx.candidates}

        order = sorted(
            (c for c in ctx.candidates if c.id not in blocked),
            key=lambda c: (len(options.get(c.id, ())), -c.priority, c.id),
        )
        attempts = 0
        for candidate in order:
            placed = False
            failures: list[str] = []
            for option in options.get(candidate.id, ()):
                attempts += 1
                assignment, reason = try_build_assignment(
                    ctx, state, candidate, option, panels)
                if assignment is None:
                    if reason and reason not in failures:
                        failures.append(reason)
                    continue
                state.commit(assignment)
                solution.assignments.append(assignment)
                placed = True
                break
            if not placed:
                solution.unscheduled.append(UnscheduledCandidate(
                    candidate_id=candidate.id,
                    reason=("Every feasible slot was taken by an earlier interview"
                            if options.get(candidate.id) else
                            "No feasible slot in the scheduling window"),
                    details=failures[:5],
                ))
        solution.unscheduled.extend(blocked.values())
        solution.statistics = {
            "placement_attempts": attempts,
            "candidates_considered": len(order),
            "unused_candidates": len(by_id) - len(order),
        }
        return solution
