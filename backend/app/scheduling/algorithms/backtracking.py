"""Backtracking CSP solver with MRV ordering and a greedy incumbent bound.

The problem is a constraint satisfaction / optimisation problem:

    variables : candidates
    domains   : feasible (panel, date, time-slot) combinations
    objective : maximise scheduled candidates first, then the soft-constraint
                score of the placements

A greedy pass provides the initial incumbent so the search always returns a
usable schedule even when the node budget is exhausted on a large instance.
"""
from __future__ import annotations

from app.scheduling.algorithms.base import (SchedulerAlgorithm, Solution,
                                            register_algorithm)
from app.scheduling.algorithms.greedy import GreedyScheduler
from app.scheduling.placement import try_build_assignment
from app.scheduling.state import SolutionState
from app.scheduling.types import (Assignment, CandidateSpec, SchedulingContext,
                                  SlotOption, UnscheduledCandidate)

# How many of the best-scoring slots are explored per candidate.  Wider search
# finds better schedules; narrower search keeps large instances fast.
BRANCHING_FACTOR = 6


@register_algorithm("backtracking")
class BacktrackingScheduler(SchedulerAlgorithm):
    description = ("Constraint-satisfaction search with most-constrained-variable "
                   "ordering, greedy incumbent and bounded backtracking.")

    def solve(self, ctx: SchedulingContext, options: dict[int, list[SlotOption]],
              blocked: dict[int, UnscheduledCandidate]) -> Solution:
        panels = {p.id: p for p in ctx.panels}
        order: list[CandidateSpec] = sorted(
            (c for c in ctx.candidates if c.id not in blocked),
            key=lambda c: (len(options.get(c.id, ())), -c.priority, c.id),
        )

        # ---- incumbent from the greedy pass ------------------------------
        seed = GreedyScheduler().solve(ctx, options, {})
        best: list[Assignment] = list(seed.assignments)
        best_key = (len(best), round(seed.total_score, 6))
        failures: dict[int, list[str]] = {}

        state = SolutionState(ctx)
        nodes = 0
        budget = max(1000, ctx.options.backtrack_limit)
        current: list[Assignment] = []

        def record() -> None:
            nonlocal best, best_key
            key = (len(current), round(sum(a.score for a in current), 6))
            if key > best_key:
                best_key = key
                best = list(current)

        def search(index: int) -> None:
            nonlocal nodes
            if nodes >= budget:
                return
            if index >= len(order):
                record()
                return
            # Bound: even placing every remaining candidate cannot beat the
            # incumbent's count, and the score bound is already unreachable.
            remaining = len(order) - index
            if len(current) + remaining < best_key[0]:
                return

            candidate = order[index]
            branches: list[Assignment] = []
            reasons: list[str] = []
            for option in options.get(candidate.id, ()):
                nodes += 1
                if nodes >= budget:
                    break
                assignment, reason = try_build_assignment(
                    ctx, state, candidate, option, panels)
                if assignment is None:
                    if reason and reason not in reasons:
                        reasons.append(reason)
                    continue
                branches.append(assignment)
                if len(branches) >= BRANCHING_FACTOR:
                    break
            branches.sort(key=lambda a: -a.score)
            if not branches:
                failures[candidate.id] = reasons[:5]

            for assignment in branches:
                state.commit(assignment)
                current.append(assignment)
                search(index + 1)
                current.pop()
                state.rollback(assignment)
                if nodes >= budget:
                    return
            # Leaving this candidate unscheduled is also a valid branch - it may
            # free a scarce slot for two candidates further down the order.
            search(index + 1)

        search(0)

        solution = Solution()
        solution.assignments = best
        placed_ids = {a.candidate_id for a in best}
        for candidate in order:
            if candidate.id in placed_ids:
                continue
            solution.unscheduled.append(UnscheduledCandidate(
                candidate_id=candidate.id,
                reason=("All feasible slots were needed by other candidates"
                        if options.get(candidate.id) else
                        "No feasible slot in the scheduling window"),
                details=failures.get(candidate.id, [])[:5],
            ))
        solution.unscheduled.extend(blocked.values())
        solution.statistics = {
            "nodes_explored": nodes,
            "node_budget": budget,
            "search_exhausted": nodes < budget,
            "greedy_baseline": len(seed.assignments),
            "branching_factor": BRANCHING_FACTOR,
        }
        return solution
