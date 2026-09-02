"""Algorithm registry - importing this package registers every strategy."""
from app.scheduling.algorithms.backtracking import BacktrackingScheduler
from app.scheduling.algorithms.base import (SchedulerAlgorithm, Solution,
                                            available_algorithms, get_algorithm,
                                            register_algorithm)
from app.scheduling.algorithms.greedy import GreedyScheduler

__all__ = [
    "SchedulerAlgorithm", "Solution", "get_algorithm", "available_algorithms",
    "register_algorithm", "GreedyScheduler", "BacktrackingScheduler",
]
