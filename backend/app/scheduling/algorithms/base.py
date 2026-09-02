"""Pluggable scheduling algorithms.

`SchedulerAlgorithm` is the seam that lets the solving strategy be swapped
(greedy, backtracking, constraint programming, integer optimisation, ...)
without touching data loading, constraint evaluation or persistence.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable

from app.scheduling.types import (Assignment, SchedulingContext, SlotOption,
                                  UnscheduledCandidate)


class Solution:
    """Result of one algorithm run, before conflict verification."""

    def __init__(self) -> None:
        self.assignments: list[Assignment] = []
        self.unscheduled: list[UnscheduledCandidate] = []
        self.statistics: dict[str, float | int | str] = {}

    @property
    def total_score(self) -> float:
        return sum(a.score for a in self.assignments)


class SchedulerAlgorithm(ABC):
    """Base class for every solving strategy."""

    name: str = "base"
    description: str = ""

    @abstractmethod
    def solve(self, ctx: SchedulingContext, options: dict[int, list[SlotOption]],
              blocked: dict[int, UnscheduledCandidate]) -> Solution:
        """Assign candidates to slots, maximising satisfied soft constraints."""


_REGISTRY: dict[str, Callable[[], SchedulerAlgorithm]] = {}


def register_algorithm(name: str) -> Callable[[type[SchedulerAlgorithm]],
                                              type[SchedulerAlgorithm]]:
    def decorator(cls: type[SchedulerAlgorithm]) -> type[SchedulerAlgorithm]:
        cls.name = name
        _REGISTRY[name] = cls
        return cls
    return decorator


def get_algorithm(name: str) -> SchedulerAlgorithm:
    key = (name or "").strip().lower()
    if key not in _REGISTRY:
        raise KeyError(f"Unknown scheduling algorithm '{name}'. "
                       f"Available: {', '.join(sorted(_REGISTRY))}")
    return _REGISTRY[key]()


def available_algorithms() -> list[dict[str, str]]:
    return [{"name": name, "description": cls.description}
            for name, cls in sorted(_REGISTRY.items())]
