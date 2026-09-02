from __future__ import annotations

from datetime import date, time
from typing import Any

from sqlalchemy import JSON, Boolean, Date, Enum, Index, Integer, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import CandidateStatus


class Candidate(Base, TimestampMixin):
    __tablename__ = "candidates"
    __table_args__ = (
        Index("ix_candidates_status_date", "status", "preferred_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    candidate_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), index=True)
    phone: Mapped[str | None] = mapped_column(String(64))
    department: Mapped[str | None] = mapped_column(String(128), index=True)
    position: Mapped[str | None] = mapped_column(String(128))

    preferred_date: Mapped[date | None] = mapped_column(Date, index=True)
    preferred_time: Mapped[time | None] = mapped_column(Time)
    preferred_panel_code: Mapped[str | None] = mapped_column(String(64))

    # Parsed availability windows: [{"date": "2026-01-05", "start_time": "09:00",
    #                                "end_time": "12:00"}, ...]
    availability: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    # Free-form constraints captured from the sheet, e.g. {"no_friday": true}
    constraints: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[CandidateStatus] = mapped_column(
        Enum(CandidateStatus, native_enum=False, length=32,
             values_callable=lambda e: [m.value for m in e]),
        default=CandidateStatus.PENDING, nullable=False, index=True,
    )
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    interviews = relationship("Interview", back_populates="candidate",
                              cascade="all, delete-orphan")
    evaluations = relationship("Evaluation", back_populates="candidate",
                               cascade="all, delete-orphan")
