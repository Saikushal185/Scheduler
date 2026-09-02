"""SQLAlchemy models.

Importing this package registers every mapper on `Base.metadata`.
"""
from app.models.base import Base, TimestampMixin
from app.models.candidate import Candidate
from app.models.constraint import SchedulingConstraint
from app.models.evaluation import Evaluation, EvaluationMetric, EvaluationScore
from app.models.faculty import (Faculty, FacultyAvailability, FacultyBusySlot,
                                FacultyFreeSlot)
from app.models.interview import (Interview, InterviewPanelMember,
                                  InterviewScheduleHistory, SchedulingRun)
from app.models.panel import PanelGroup, PanelMember
from app.models.settings import InterviewSettings
from app.models.upload import UploadedFile
from app.models.user import User

__all__ = [
    "Base", "TimestampMixin", "User", "Candidate", "Faculty", "FacultyAvailability",
    "FacultyBusySlot", "FacultyFreeSlot", "PanelGroup", "PanelMember", "Interview",
    "InterviewPanelMember", "InterviewScheduleHistory", "SchedulingRun",
    "EvaluationMetric", "Evaluation", "EvaluationScore", "UploadedFile",
    "SchedulingConstraint", "InterviewSettings",
]
