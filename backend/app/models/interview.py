from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from sqlalchemy import (JSON, Boolean, Date, DateTime, Enum, Float, ForeignKey,
                        Index, Integer, String, Text, Time, UniqueConstraint, func)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import HistoryAction, InterviewStatus, ScheduleRunStatus


class SchedulingRun(Base, TimestampMixin):
    """One execution of the scheduling engine (preview or confirmed)."""

    __tablename__ = "scheduling_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    algorithm: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[ScheduleRunStatus] = mapped_column(
        Enum(ScheduleRunStatus, native_enum=False, length=32,
             values_callable=lambda e: [m.value for m in e]),
        default=ScheduleRunStatus.PREVIEW, nullable=False, index=True,
    )
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    total_candidates: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    scheduled_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unscheduled_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    interviews = relationship("Interview", back_populates="run")


class Interview(Base, TimestampMixin):
    __tablename__ = "interviews"
    __table_args__ = (
        Index("ix_interviews_date_time", "date", "start_time"),
        Index("ix_interviews_status_date", "status", "date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    schedule_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    panel_id: Mapped[int | None] = mapped_column(
        ForeignKey("panel_groups.id", ondelete="SET NULL"), index=True)
    run_id: Mapped[int | None] = mapped_column(
        ForeignKey("scheduling_runs.id", ondelete="SET NULL"), index=True)

    date: Mapped[date | None] = mapped_column(Date, index=True)
    start_time: Mapped[time | None] = mapped_column(Time)
    end_time: Mapped[time | None] = mapped_column(Time)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)

    status: Mapped[InterviewStatus] = mapped_column(
        Enum(InterviewStatus, native_enum=False, length=32,
             values_callable=lambda e: [m.value for m in e]),
        default=InterviewStatus.SCHEDULED, nullable=False, index=True,
    )
    scheduling_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    # Per-constraint outcome, e.g. [{"type": "CANDIDATE_PREFERRED_DATE",
    #   "priority": "HIGH", "satisfied": true, "score": 100.0}]
    priority_info: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    unscheduled_reason: Mapped[str | None] = mapped_column(Text)

    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_manual: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    round_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    location: Mapped[str | None] = mapped_column(String(128))
    notes: Mapped[str | None] = mapped_column(Text)

    candidate = relationship("Candidate", back_populates="interviews", lazy="selectin")
    panel = relationship("PanelGroup", back_populates="interviews", lazy="selectin")
    run = relationship("SchedulingRun", back_populates="interviews")
    panel_members = relationship("InterviewPanelMember", back_populates="interview",
                                 cascade="all, delete-orphan", lazy="selectin")
    history = relationship("InterviewScheduleHistory", back_populates="interview",
                           cascade="all, delete-orphan",
                           order_by="desc(InterviewScheduleHistory.id)")
    evaluations = relationship("Evaluation", back_populates="interview")


class InterviewPanelMember(Base):
    """Faculty actually assigned to an interview (may be a subset of the panel)."""

    __tablename__ = "interview_panel_members"
    __table_args__ = (
        UniqueConstraint("interview_id", "faculty_id", name="uq_interview_faculty"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    interview_id: Mapped[int] = mapped_column(
        ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False, index=True)
    faculty_id: Mapped[int] = mapped_column(
        ForeignKey("faculty.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(64), default="MEMBER", nullable=False)

    interview = relationship("Interview", back_populates="panel_members")
    faculty = relationship("Faculty", lazy="selectin")


class InterviewScheduleHistory(Base):
    __tablename__ = "interview_schedule_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    interview_id: Mapped[int] = mapped_column(
        ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False, index=True)
    action: Mapped[HistoryAction] = mapped_column(
        Enum(HistoryAction, native_enum=False, length=32,
             values_callable=lambda e: [m.value for m in e]), nullable=False,
    )
    previous_state: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    new_state: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    performed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False)

    interview = relationship("Interview", back_populates="history")
