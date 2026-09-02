"""Hybrid solver: construct a schedule, then keep improving it.

The existing solvers stop at the first complete assignment they find.  That is
fine for feasibility but leaves value on the table: a candidate placed early
takes the slot a later, more constrained candidate needed, and nothing ever
revisits that decision.

This algorithm adds the missing third phase:

    greedy seed  ->  bounded backtracking  ->  local search

The local search repeatedly applies three moves and keeps only strict
improvements on the same lexicographic objective the rest of the engine uses -
`(number scheduled, total score)`:

    insertion   place an unscheduled candidate, evicting a blocker and
                re-placing it elsewhere when the swap nets a gain
    relocation  move one assignment to a better-scoring slot
    swap        exchange two candidates' slots

Every move is applied through `SolutionState.commit`/`rollback`, so the state
invariants (no overlaps, break periods, per-day caps) are enforced by the same
code that enforces them during construction - a move can never produce a
schedule the constructor would have rejected.
"""
from __future__ import annotations

import time as _time

from app.core.logging_config import get_logger
from app.scheduling.algorithms.backtracking import BacktrackingScheduler
from app.scheduling.algorithms.base import (SchedulerAlgorithm, Solution,
                                            register_algorithm)
from app.scheduling.placement import try_build_assignment
from app.scheduling.state import SolutionState
from app.scheduling.types import (Assignment, CandidateSpec, SchedulingContext,
                                  SlotOption, UnscheduledCandidate)

logger = get_logger(__name__)

# Guard rails so a large instance cannot spend unbounded time improving.
MAX_PASSES = 8
TIME_BUDGET_SECONDS = 5.0
# How many better-scoring options to actually rebuild per relocation attempt.
RELOCATION_CANDIDATES = 12


@register_algorithm("optimized")
class OptimizedScheduler(SchedulerAlgorithm):
    description = ("Backtracking search followed by a local-search improvement "
                   "pass (insertion, relocation and swap moves) that keeps only "
                   "strict gains in scheduled count then total score.")

    def solve(self, ctx: SchedulingContext, options: dict[int, list[SlotOption]],
              blocked: dict[int, UnscheduledCandidate]) -> Solution:
        started = _time.perf_counter()
        seed = BacktrackingScheduler().solve(ctx, options, blocked)
        seed_count = len(seed.assignments)
        seed_score = seed.total_score

        candidates = {c.id: c for c in ctx.candidates}
        panels = {p.id: p for p in ctx.panels}

        # Rebuild the state that produced the seed so moves start from it.
        state = SolutionState(ctx)
        for assignment in seed.assignments:
            state.commit(assignment)

        stats = {"insertions": 0, "relocations": 0, "swaps": 0, "passes": 0}
        deadline = started + TIME_BUDGET_SECONDS

        for _ in range(MAX_PASSES):
            if _time.perf_counter() > deadline:
                break
            stats["passes"] += 1
            improved = False
            improved |= self._try_insertions(ctx, state, options, candidates,
                                             panels, blocked, stats, deadline)
            improved |= self._try_relocations(ctx, state, options, candidates,
                                              panels, stats, deadline)
            improved |= self._try_swaps(ctx, state, options, candidates,
                                        panels, stats, deadline)
            if not improved:
                break  # local optimum for these moves

        final = list(state.assignments.values())
        # Never return worse than the seed: the moves only accept strict gains,
        # but this makes that guarantee explicit rather than implied.
        if (len(final), round(sum(a.score for a in final), 6)) < (
                seed_count, round(seed_score, 6)):
            final = list(seed.assignments)

        solution = Solution()
        solution.assignments = sorted(final, key=lambda a: (a.day, a.slot.start))
        placed = {a.candidate_id for a in solution.assignments}
        seed_reasons = {u.candidate_id: u for u in seed.unscheduled}
        for candidate in ctx.candidates:
            if candidate.id in placed:
                continue
            existing = seed_reasons.get(candidate.id)
            solution.unscheduled.append(existing or UnscheduledCandidate(
                candidate_id=candidate.id,
                reason="No feasible slot remained after optimisation",
                details=[]))

        elapsed_ms = int((_time.perf_counter() - started) * 1000)
        solution.statistics = {
            **seed.statistics,
            "seed_scheduled": seed_count,
            "seed_score": round(seed_score, 3),
            "final_scheduled": len(solution.assignments),
            "final_score": round(solution.total_score, 3),
            "scheduled_gain": len(solution.assignments) - seed_count,
            "score_gain": round(solution.total_score - seed_score, 3),
            "improvement_passes": stats["passes"],
            "insertion_moves": stats["insertions"],
            "relocation_moves": stats["relocations"],
            "swap_moves": stats["swaps"],
            "optimise_ms": elapsed_ms,
        }
        logger.info("Optimised schedule: %s -> %s scheduled, score %.1f -> %.1f "
                    "(%s insertions, %s relocations, %s swaps in %s pass(es))",
                    seed_count, len(solution.assignments), seed_score,
                    solution.total_score, stats["insertions"],
                    stats["relocations"], stats["swaps"], stats["passes"])
        return solution

    # ------------------------------------------------------------------ moves
    def _try_insertions(self, ctx, state, options, candidates, panels, blocked,
                        stats, deadline) -> bool:
        """Place an unscheduled candidate, evicting one blocker if that helps."""
        improved = False
        unplaced = [c for c in ctx.candidates
                    if c.id not in state.assignments and c.id not in blocked
                    and options.get(c.id)]
        for candidate in unplaced:
            if _time.perf_counter() > deadline:
                break
            # Cheapest case: a slot opened up since the constructor ran.
            if self._place_directly(ctx, state, candidate, options, panels):
                stats["insertions"] += 1
                improved = True
                continue
            if self._place_by_eviction(ctx, state, candidate, options,
                                       candidates, panels):
                stats["insertions"] += 1
                improved = True
        return improved

    def _place_directly(self, ctx, state, candidate: CandidateSpec, options,
                        panels) -> bool:
        for option in options.get(candidate.id, ()):
            assignment, _ = try_build_assignment(ctx, state, candidate, option, panels)
            if assignment is not None:
                state.commit(assignment)
                return True
        return False

    def _place_by_eviction(self, ctx, state, candidate: CandidateSpec, options,
                           candidates, panels) -> bool:
        """Evict one assignment, place this candidate, then re-place the evictee.

        Accepted only when the schedule ends up with more interviews, or the same
        number at a strictly better score - so an eviction can never quietly
        trade one candidate for another.
        """
        before = (len(state.assignments), round(state.total_score, 6))
        for victim in list(state.assignments.values()):
            victim_candidate = candidates.get(victim.candidate_id)
            if victim_candidate is None:
                continue
            state.rollback(victim)
            if not self._place_directly(ctx, state, candidate, options, panels):
                state.commit(victim)
                continue
            # Try to find the evicted candidate a new home.
            self._place_directly(ctx, state, victim_candidate, options, panels)
            after = (len(state.assignments), round(state.total_score, 6))
            if after > before:
                return True
            # Undo: drop whatever we just added and restore the victim.
            for cid in (candidate.id, victim.candidate_id):
                current = state.assignments.get(cid)
                if current is not None:
                    state.rollback(current)
            state.commit(victim)
        return False

    def _try_relocations(self, ctx, state, options, candidates, panels, stats,
                         deadline) -> bool:
        """Move an assignment to a higher-scoring slot that is free."""
        improved = False
        for candidate_id, assignment in list(state.assignments.items()):
            if _time.perf_counter() > deadline:
                break
            candidate = candidates.get(candidate_id)
            if candidate is None:
                continue
            state.rollback(assignment)
            # Compare like with like: an option carries only the static score,
            # while an Assignment score also includes the dynamic outcomes worth
            # ~1000 points.  Ranking options against the current option's static
            # score is what makes this move able to fire at all.
            current_static = self._static_score(options, candidate_id, assignment)
            best = assignment
            tried = 0
            for option in options.get(candidate_id, ()):
                if option.score <= current_static:
                    break  # options are score-ordered: nothing better remains
                if tried >= RELOCATION_CANDIDATES:
                    break
                tried += 1
                replacement, _ = try_build_assignment(ctx, state, candidate,
                                                      option, panels)
                if replacement is not None and replacement.score > best.score:
                    best = replacement
                    break
            state.commit(best)
            if best is not assignment:
                stats["relocations"] += 1
                improved = True
        return improved

    def _try_swaps(self, ctx, state, options, candidates, panels, stats,
                   deadline) -> bool:
        """Exchange two candidates' slots when the pair scores better."""
        improved = False
        assignments = list(state.assignments.values())
        for i, first in enumerate(assignments):
            if _time.perf_counter() > deadline:
                break
            for second in assignments[i + 1:]:
                if first.candidate_id not in state.assignments:
                    break
                if second.candidate_id not in state.assignments:
                    continue
                current_first = state.assignments[first.candidate_id]
                current_second = state.assignments[second.candidate_id]
                if self._swap_pair(ctx, state, current_first, current_second,
                                   options, candidates, panels):
                    stats["swaps"] += 1
                    improved = True
        return improved

    def _swap_pair(self, ctx, state, first: Assignment, second: Assignment,
                   options, candidates, panels) -> bool:
        candidate_a = candidates.get(first.candidate_id)
        candidate_b = candidates.get(second.candidate_id)
        if candidate_a is None or candidate_b is None:
            return False
        before = round(first.score + second.score, 6)

        state.rollback(first)
        state.rollback(second)
        option_a = self._option_for(options, candidate_a.id, second)
        option_b = self._option_for(options, candidate_b.id, first)
        if option_a is not None and option_b is not None:
            new_a, _ = try_build_assignment(ctx, state, candidate_a, option_a, panels)
            if new_a is not None:
                state.commit(new_a)
                new_b, _ = try_build_assignment(ctx, state, candidate_b, option_b,
                                                panels)
                if new_b is not None and round(new_a.score + new_b.score, 6) > before:
                    state.commit(new_b)
                    return True
                state.rollback(new_a)
        state.commit(first)
        state.commit(second)
        return False

    @staticmethod
    def _static_score(options, candidate_id: int, assignment: Assignment) -> float:
        """The static score of the option this assignment came from."""
        option = OptimizedScheduler._option_for(options, candidate_id, assignment)
        return option.score if option is not None else float("-inf")

    @staticmethod
    def _option_for(options, candidate_id: int,
                    target: Assignment) -> SlotOption | None:
        """The candidate's own option matching another candidate's placement."""
        for option in options.get(candidate_id, ()):
            if (option.day == target.day and option.slot.start == target.slot.start
                    and option.panel_id == target.panel_id):
                return option
        return None
