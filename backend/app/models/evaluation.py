from __future__ import annotations

from datetime import date

from sqlalchemy import (JSON, Boolean, Date, Float, ForeignKey, Integer, String,
                        Text, UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class EvaluationMetric(Base, TimestampMixin):
    """One configurable evaluation metric.

    The system ships with seven seeded rows, but the count, the names, the
    weights and the score range are all editable at runtime; no metric name is
    referenced literally anywhere in the code.
    """

    __tablename__ = "evaluation_metrics"

    id: Mapped[int] = mapped_column(primary_key=True)
    metric_key: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    weight: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    min_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    max_score: Mapped[float] = mapped_column(Float, default=10.0, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Alternative column headers accepted when importing an evaluation sheet.
    column_aliases: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)

    scores = relationship("EvaluationScore", back_populates="metric",
                          cascade="all, delete-orphan")


class Evaluation(Base, TimestampMixin):
    __tablename__ = "evaluations"
    __table_args__ = (
        UniqueConstraint("candidate_id", "interview_id", "evaluator_faculty_id",
                         name="uq_evaluation_scope"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    interview_id: Mapped[int | None] = mapped_column(
        ForeignKey("interviews.id", ondelete="SET NULL"), index=True)
    panel_id: Mapped[int | None] = mapped_column(
        ForeignKey("panel_groups.id", ondelete="SET NULL"), index=True)
    evaluator_faculty_id: Mapped[int | None] = mapped_column(
        ForeignKey("faculty.id", ondelete="SET NULL"), index=True)

    evaluation_date: Mapped[date | None] = mapped_column(Date, index=True)
    overall_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    normalized_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    max_possible_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    strongest_metric_id: Mapped[int | None] = mapped_column(
        ForeignKey("evaluation_metrics.id", ondelete="SET NULL"))
    weakest_metric_id: Mapped[int | None] = mapped_column(
        ForeignKey("evaluation_metrics.id", ondelete="SET NULL"))
    recommendation: Mapped[str | None] = mapped_column(String(64))
    remarks: Mapped[str | None] = mapped_column(Text)

    candidate = relationship("Candidate", back_populates="evaluations", lazy="selectin")
    interview = relationship("Interview", back_populates="evaluations")
    panel = relationship("PanelGroup", lazy="selectin")
    evaluator = relationship("Faculty", lazy="selectin")
    scores = relationship("EvaluationScore", back_populates="evaluation",
                          cascade="all, delete-orphan", lazy="selectin")


class EvaluationScore(Base, TimestampMixin):
    __tablename__ = "evaluation_scores"
    __table_args__ = (
        UniqueConstraint("evaluation_id", "metric_id", name="uq_evaluation_metric"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    evaluation_id: Mapped[int] = mapped_column(
        ForeignKey("evaluations.id", ondelete="CASCADE"), nullable=False, index=True)
    metric_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation_metrics.id", ondelete="CASCADE"), nullable=False, index=True)
    raw_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    normalized_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    weighted_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)

    evaluation = relationship("Evaluation", back_populates="scores")
    metric = relationship("EvaluationMetric", back_populates="scores", lazy="selectin")
