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
            },
        )
        logger.info("Scheduling finished in %sms: %s scheduled, %s unscheduled, "
                    "%s conflict(s), score %.1f", elapsed_ms, result.scheduled_count,
                    len(result.unscheduled), len(conflicts), result.total_score)
        return result


def list_algorithms() -> list[dict[str, str]]:
    return available_algorithms()
