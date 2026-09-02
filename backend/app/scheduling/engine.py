"""Scheduling engine orchestration.

    load context -> generate domains -> drop hard violations -> score ->
    solve -> verify conflicts -> report scheduled + unscheduled (with reasons)

The engine is deliberately independent of the database and the web layer; it
takes a `SchedulingContext` and returns a `SchedulingResult`.
"""
from __future__ import annotations

import time as _time

from app.core.logging_config import get_logger
from app.scheduling.algorithms import available_algorithms, get_algorithm
from app.scheduling.conflicts import detect_conflicts
from app.scheduling.domain import generate_options
from app.scheduling.types import SchedulingContext, SchedulingResult

logger = get_logger(__name__)


class SchedulingEngine:
    """Runs one scheduling pass with the configured algorithm."""

    def __init__(self, algorithm: str | None = None) -> None:
        self.algorithm_name = (algorithm or "backtracking").strip().lower()

    def run(self, ctx: SchedulingContext) -> SchedulingResult:
        started = _time.perf_counter()
        algorithm = get_algorithm(self.algorithm_name)

        options, blocked = generate_options(ctx)
        combinations = sum(len(v) for v in options.values())
        logger.info(
            "Scheduling %s candidate(s) over %s date(s) with %s panel(s): "
            "%s feasible combinations, %s candidate(s) with an empty domain",
            len(ctx.candidates), len(ctx.options.dates), len(ctx.panels),
            combinations, len(blocked),
        )

        solution = algorithm.solve(ctx, options, blocked)
        conflicts = detect_conflicts(ctx, solution.assignments)
        elapsed_ms = int((_time.perf_counter() - started) * 1000)
        satisfaction = _constraint_summary(solution.assignments)

        result = SchedulingResult(
            algorithm=algorithm.name,
            assignments=solution.assignments,
            unscheduled=solution.unscheduled,
            conflicts=conflicts,
            total_score=solution.total_score,
            duration_ms=elapsed_ms,
            statistics={
                **solution.statistics,
                "feasible_combinations": combinations,
                "candidates_total": len(ctx.candidates),
                "panels_total": len(ctx.panels),
                "dates_total": len(ctx.options.dates),
                "empty_domain_candidates": len(blocked),
                "duration_minutes": ctx.options.duration_minutes,
                "break_minutes": ctx.options.break_minutes,
                "constraint_satisfaction": satisfaction,
            },
        )
        logger.info("Scheduling finished in %sms: %s scheduled, %s unscheduled, "
                    "%s conflict(s), score %.1f", elapsed_ms, result.scheduled_count,
                    len(result.unscheduled), len(conflicts), result.total_score)
        return result


def _constraint_summary(assignments) -> list[dict[str, object]]:
    """Per constraint type: how often it was satisfied and what it cost.

    Makes a schedule defensible - "why did we end up here" is answered by which
    soft constraints were traded away and how much score that forfeited.
    """
    # Best achieved score per constraint type, computed once - "forgone" is
    # measured against the best any placement actually managed.
    best_by_type: dict[str, float] = {}
    for assignment in assignments:
        for outcome in assignment.outcomes:
            if outcome.score > best_by_type.get(outcome.constraint_type, 0.0):
                best_by_type[outcome.constraint_type] = outcome.score

    tally: dict[str, dict[str, object]] = {}
    for assignment in assignments:
        for outcome in assignment.outcomes:
            row = tally.setdefault(outcome.constraint_type, {
                "type": outcome.constraint_type,
                "priority": outcome.priority,
                "satisfied": 0, "violated": 0,
                "score_awarded": 0.0, "score_forgone": 0.0,
            })
            best = best_by_type.get(outcome.constraint_type, 0.0)
            if outcome.satisfied:
                row["satisfied"] += 1
            else:
                row["violated"] += 1
            row["score_awarded"] += outcome.score
            row["score_forgone"] += max(0.0, best - outcome.score)
    summary = []
    for row in tally.values():
        total = row["satisfied"] + row["violated"]
        summary.append({
            **row,
            "score_awarded": round(row["score_awarded"], 2),
            "score_forgone": round(row["score_forgone"], 2),
            "satisfaction_rate": round(100.0 * row["satisfied"] / total, 1) if total else 0.0,
        })
    summary.sort(key=lambda r: -r["score_forgone"])
    return summary


def list_algorithms() -> list[dict[str, str]]:
    return available_algorithms()
