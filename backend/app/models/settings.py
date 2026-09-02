from __future__ import annotations

from datetime import date, datetime, time

from sqlalchemy import Boolean, Date, DateTime, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class InterviewSettings(Base, TimestampMixin):
    """Singleton row (id == 1) holding the global scheduling configuration."""

    __tablename__ = "interview_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    interview_duration_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    break_duration_minutes: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    day_start_time: Mapped[time] = mapped_column(Time, nullable=False)
    day_end_time: Mapped[time] = mapped_column(Time, nullable=False)
    schedule_start_date: Mapped[date | None] = mapped_column(Date)
    schedule_end_date: Mapped[date | None] = mapped_column(Date)
    slot_granularity_minutes: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    min_panel_size: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    max_panel_size: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    max_interviews_per_faculty_per_day: Mapped[int] = mapped_column(
        Integer, default=12, nullable=False)
    allow_weekends: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    default_algorithm: Mapped[str] = mapped_column(String(64), default="optimized",
                                                   nullable=False)
    organisation_name: Mapped[str] = mapped_column(String(255), default="Institute",
                                                   nullable=False)
    # Students see their own marks only once an administrator releases them, so a
    # teacher's in-progress entry is never visible.
    results_published: Mapped[bool] = mapped_column(Boolean, default=False,
                                                    nullable=False)
    results_published_at: Mapped[datetime | None] = mapped_column(DateTime)
