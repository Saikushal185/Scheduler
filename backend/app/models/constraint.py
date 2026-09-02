from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Boolean, Enum, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.enums import ConstraintPriority, ConstraintType


class SchedulingConstraint(Base, TimestampMixin):
    """A configurable scheduling rule with a priority band.

    HARD rules filter candidate x panel x slot combinations; every other band
    contributes to the optimisation score using the band weight.
    """

    __tablename__ = "scheduling_constraints"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    constraint_type: Mapped[ConstraintType] = mapped_column(
        Enum(ConstraintType, native_enum=False, length=64,
             values_callable=lambda e: [m.value for m in e]), nullable=False, index=True)
    priority: Mapped[ConstraintPriority] = mapped_column(
        Enum(ConstraintPriority, native_enum=False, length=32,
             values_callable=lambda e: [m.value for m in e]),
        default=ConstraintPriority.MEDIUM, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    # Optional narrowing of the rule, e.g. {"candidate_id": 3} or {"faculty_id": 7}
    scope: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    # Rule specific payload, e.g. {"max_per_day": 6}
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    weight_multiplier: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
