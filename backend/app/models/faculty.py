from __future__ import annotations

from datetime import date, datetime, time

from sqlalchemy import (Boolean, Date, DateTime, Enum, ForeignKey, Index, Integer,
                        String, Text, Time, UniqueConstraint, func)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import AvailabilityStatus, BusySlotSource


class Faculty(Base, TimestampMixin):
    __tablename__ = "faculty"

    id: Mapped[int] = mapped_column(primary_key=True)
    faculty_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    faculty_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), index=True)
    phone: Mapped[str | None] = mapped_column(String(64))
    department: Mapped[str | None] = mapped_column(String(128), index=True)
    designation: Mapped[str | None] = mapped_column(String(128))
    max_interviews_per_day: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    availability = relationship("FacultyAvailability", back_populates="faculty",
                                cascade="all, delete-orphan")
    busy_slots = relationship("FacultyBusySlot", back_populates="faculty",
                              cascade="all, delete-orphan")
    free_slots = relationship("FacultyFreeSlot", back_populates="faculty",
                              cascade="all, delete-orphan")
    panel_memberships = relationship("PanelMember", back_populates="faculty",
                                     cascade="all, delete-orphan")


class FacultyAvailability(Base, TimestampMixin):
    """A working window declared by (or imported for) a faculty member."""

    __tablename__ = "faculty_availability"
    __table_args__ = (
        Index("ix_faculty_availability_faculty_date", "faculty_id", "date"),
        UniqueConstraint("faculty_id", "date", "start_time", "end_time",
                         name="uq_faculty_availability_window"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    faculty_id: Mapped[int] = mapped_column(
        ForeignKey("faculty.id", ondelete="CASCADE"), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    availability_status: Mapped[AvailabilityStatus] = mapped_column(
        Enum(AvailabilityStatus, native_enum=False, length=32,
             values_callable=lambda e: [m.value for m in e]),
        default=AvailabilityStatus.AVAILABLE, nullable=False,
    )
    note: Mapped[str | None] = mapped_column(String(255))

    faculty = relationship("Faculty", back_populates="availability")


class FacultyBusySlot(Base, TimestampMixin):
    """Time a faculty member cannot be booked (meetings, lectures, interviews)."""

    __tablename__ = "faculty_busy_slots"
    __table_args__ = (
        Index("ix_faculty_busy_faculty_date", "faculty_id", "date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    faculty_id: Mapped[int] = mapped_column(
        ForeignKey("faculty.id", ondelete="CASCADE"), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    source: Mapped[BusySlotSource] = mapped_column(
        Enum(BusySlotSource, native_enum=False, length=32,
             values_callable=lambda e: [m.value for m in e]),
        default=BusySlotSource.MANUAL, nullable=False,
    )
    reason: Mapped[str | None] = mapped_column(String(255))
    interview_id: Mapped[int | None] = mapped_column(
        ForeignKey("interviews.id", ondelete="CASCADE"), index=True)

    faculty = relationship("Faculty", back_populates="busy_slots")


class FacultyFreeSlot(Base):
    """Derived table: availability windows minus busy slots.

    Rows are recomputed by `FreeSlotService`; they are never edited directly.
    """

    __tablename__ = "faculty_free_slots"
    __table_args__ = (
        Index("ix_faculty_free_faculty_date", "faculty_id", "date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    faculty_id: Mapped[int] = mapped_column(
        ForeignKey("faculty.id", ondelete="CASCADE"), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False)

    faculty = relationship("Faculty", back_populates="free_slots")
