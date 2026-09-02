from __future__ import annotations

import datetime as _dt
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.common import ORMModel


class MetricBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    weight: float = Field(default=0.0, ge=0.0)
    min_score: float = 0.0
    max_score: float = Field(default=10.0, gt=0.0)
    display_order: int = 0
    is_active: bool = True
    column_aliases: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_range(self):
        if self.max_score <= self.min_score:
            raise ValueError("max_score must be greater than min_score")
        return self


class MetricCreate(MetricBase):
    metric_key: str = Field(min_length=1, max_length=64)


class MetricUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    description: str | None = None
    weight: float | None = None
    min_score: float | None = None
    max_score: float | None = None
    display_order: int | None = None
    is_active: bool | None = None
    column_aliases: list[str] | None = None


class MetricRead(ORMModel, MetricBase):
    id: int
    metric_key: str


class MetricWeightUpdate(BaseModel):
    metric_id: int
    weight: float = Field(ge=0.0)


class MetricWeightsRequest(BaseModel):
    weights: list[MetricWeightUpdate]
    normalise: bool = Field(default=False,
                            description="Rescale the weights so they sum to 1.0")


class ScoreInput(BaseModel):
    metric_id: int | None = None
    metric_key: str | None = None
    raw_score: float
    comment: str | None = None

    @model_validator(mode="after")
    def _need_identifier(self):
        if self.metric_id is None and not self.metric_key:
            raise ValueError("metric_id or metric_key is required")
        return self


class ScoreRead(ORMModel):
    id: int
    metric_id: int
    raw_score: float
    normalized_score: float
    weighted_score: float
    comment: str | None = None
    metric: MetricRead | None = None


class EvaluationCreate(BaseModel):
    candidate_id: int
    interview_id: int | None = None
    panel_id: int | None = None
    evaluator_faculty_id: int | None = None
    evaluation_date: _dt.date | None = None
    scores: list[ScoreInput]
    recommendation: str | None = None
    remarks: str | None = None


class EvaluationUpdate(BaseModel):
    panel_id: int | None = None
    evaluator_faculty_id: int | None = None
    evaluation_date: _dt.date | None = None
    scores: list[ScoreInput] | None = None
    recommendation: str | None = None
    remarks: str | None = None


class EvaluationRead(ORMModel):
    id: int
    candidate_id: int
    interview_id: int | None = None
    panel_id: int | None = None
    evaluator_faculty_id: int | None = None
    evaluation_date: _dt.date | None = None
    overall_score: float
    normalized_score: float
    max_possible_score: float
    strongest_metric_id: int | None = None
    weakest_metric_id: int | None = None
    recommendation: str | None = None
    remarks: str | None = None
    scores: list[ScoreRead] = Field(default_factory=list)
    candidate_code: str | None = None
    candidate_name: str | None = None


class RankingRow(BaseModel):
    rank: int
    candidate_id: int
    candidate_code: str
    candidate_name: str
    department: str | None = None
    overall_score: float
    normalized_score: float
    metric_scores: dict[str, float] = Field(default_factory=dict)
    strongest_metric: str | None = None
    weakest_metric: str | None = None
    recommendation: str | None = None


class CandidateMetricProfile(BaseModel):
    candidate_id: int
    candidate_code: str
    candidate_name: str
    overall_score: float
    normalized_score: float
    rank: int | None = None
    metrics: list[dict[str, Any]] = Field(default_factory=list)
    strongest_metric: str | None = None
    weakest_metric: str | None = None
