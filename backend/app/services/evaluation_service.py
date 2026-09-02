"""Evaluation management built on configurable metrics.

The metric set (seven by default), their names, weights and score ranges live in
the `evaluation_metrics` table.  All formulas below read that table, so nothing
here assumes a particular metric name or count:

    normalised(metric) = (raw - min) / (max - min) * SCALE
    overall_score      = sum(raw * weight)
    normalised_score   = sum(normalised * weight) / sum(weight)
"""
from __future__ import annotations

from datetime import date
from typing import Any, Iterable, Sequence

from sqlalchemy.orm import Session

from app.core.config import settings as app_settings
from app.core.exceptions import NotFoundError, ValidationError
from app.core.permissions import Scope, assert_faculty_owns
from app.core.logging_config import get_logger
from app.models import Evaluation, EvaluationMetric, EvaluationScore
from app.repositories import (CandidateRepository, EvaluationRepository,
                              MetricRepository, ScoreRepository)
from app.schemas.evaluation import (EvaluationCreate, EvaluationUpdate, MetricCreate,
                                    MetricUpdate, MetricWeightsRequest, ScoreInput)

logger = get_logger(__name__)


class EvaluationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.metrics = MetricRepository(db)
        self.evaluations = EvaluationRepository(db)
        self.scores = ScoreRepository(db)
        self.candidates = CandidateRepository(db)

    # ------------------------------------------------------------------ metrics
    def ensure_metrics(self) -> list[EvaluationMetric]:
        """Seed the configured default metrics the first time they are needed."""
        existing = self.metrics.ordered()
        if existing:
            return existing
        for item in app_settings.DEFAULT_EVALUATION_METRICS:
            self.metrics.create(
                metric_key=item["key"], name=item["name"], weight=float(item["weight"]),
                max_score=float(item.get("max_score", 10)), min_score=0.0,
                display_order=int(item.get("display_order", 0)),
                column_aliases=[item["key"], item["name"]])
        self.db.flush()
        logger.info("Seeded %s default evaluation metrics",
                    len(app_settings.DEFAULT_EVALUATION_METRICS))
        return self.metrics.ordered()

    def list_metrics(self, *, active_only: bool = False) -> list[EvaluationMetric]:
        self.ensure_metrics()
        return self.metrics.active() if active_only else self.metrics.ordered()

    def create_metric(self, payload: MetricCreate) -> EvaluationMetric:
        if self.metrics.by_key(payload.metric_key):
            raise ValidationError(f"Metric key '{payload.metric_key}' already exists")
        data = payload.model_dump()
        data.setdefault("column_aliases", [])
        data["column_aliases"] = list({*data["column_aliases"], payload.metric_key,
                                       payload.name})
        return self.metrics.create(**data)

    def update_metric(self, metric_id: int, payload: MetricUpdate) -> EvaluationMetric:
        metric = self.metrics.get(metric_id)
        if metric is None:
            raise NotFoundError(f"Evaluation metric {metric_id} was not found")
        for key, value in payload.model_dump(exclude_unset=True).items():
            if value is not None:
                setattr(metric, key, value)
        if metric.max_score <= metric.min_score:
            raise ValidationError("max_score must be greater than min_score")
        self.db.flush()
        self.recalculate_all()
        return metric

    def delete_metric(self, metric_id: int) -> None:
        metric = self.metrics.get(metric_id)
        if metric is None:
            raise NotFoundError(f"Evaluation metric {metric_id} was not found")
        self.metrics.delete(metric)
        self.recalculate_all()

    def set_weights(self, payload: MetricWeightsRequest) -> list[EvaluationMetric]:
        by_id = {m.id: m for m in self.metrics.ordered()}
        for item in payload.weights:
            metric = by_id.get(item.metric_id)
            if metric is None:
                raise NotFoundError(f"Evaluation metric {item.metric_id} was not found")
            metric.weight = float(item.weight)
        if payload.normalise:
            total = sum(m.weight for m in by_id.values())
            if total > 0:
                for metric in by_id.values():
                    metric.weight = round(metric.weight / total, 6)
        self.db.flush()
        self.recalculate_all()
        return self.metrics.ordered()

    # ----------------------------------------------------------------- formulas
    def _compute(self, evaluation: Evaluation,
                 metrics: dict[int, EvaluationMetric]) -> None:
        """Apply the configurable scoring formula to one evaluation."""
        weighted_total = 0.0
        normalised_weighted = 0.0
        weight_total = 0.0
        max_possible = 0.0
        best: tuple[float, int] | None = None
        worst: tuple[float, int] | None = None

        for score in evaluation.scores:
            metric = metrics.get(score.metric_id)
            if metric is None:
                continue
            span = max(1e-9, metric.max_score - metric.min_score)
            clamped = min(max(score.raw_score, metric.min_score), metric.max_score)
            normalised = ((clamped - metric.min_score) / span
                          * app_settings.EVALUATION_NORMALISED_SCALE)
            score.normalized_score = round(normalised, 4)
            score.weighted_score = round(clamped * metric.weight, 4)
            weighted_total += clamped * metric.weight
            normalised_weighted += normalised * metric.weight
            weight_total += metric.weight
            max_possible += metric.max_score * metric.weight
            if best is None or normalised > best[0]:
                best = (normalised, metric.id)
            if worst is None or normalised < worst[0]:
                worst = (normalised, metric.id)

        evaluation.overall_score = round(weighted_total, 4)
        evaluation.max_possible_score = round(max_possible, 4)
        evaluation.normalized_score = round(
            normalised_weighted / weight_total if weight_total else 0.0, 4)
        evaluation.strongest_metric_id = best[1] if best else None
        evaluation.weakest_metric_id = worst[1] if worst else None

    def recalculate(self, evaluation: Evaluation) -> Evaluation:
        metrics = {m.id: m for m in self.metrics.ordered()}
        self._compute(evaluation, metrics)
        self.db.flush()
        return evaluation

    def recalculate_all(self) -> int:
        metrics = {m.id: m for m in self.metrics.ordered()}
        rows = self.evaluations.all_full()
        for evaluation in rows:
            self._compute(evaluation, metrics)
        self.db.flush()
        return len(rows)

    # -------------------------------------------------------------- evaluations
    def _resolve_scores(self, inputs: Sequence[ScoreInput]) -> list[tuple[int, float,
                                                                          str | None]]:
        metrics = self.list_metrics()
        by_id = {m.id: m for m in metrics}
        by_key = {m.metric_key.lower(): m for m in metrics}
        resolved: list[tuple[int, float, str | None]] = []
        for item in inputs:
            metric = (by_id.get(item.metric_id) if item.metric_id
                      else by_key.get((item.metric_key or "").lower()))
            if metric is None:
                raise ValidationError(
                    f"Unknown metric '{item.metric_id or item.metric_key}'")
            if not (metric.min_score <= item.raw_score <= metric.max_score):
                raise ValidationError(
                    f"Score {item.raw_score} for '{metric.name}' must be between "
                    f"{metric.min_score} and {metric.max_score}")
            resolved.append((metric.id, float(item.raw_score), item.comment))
        return resolved

    def create(self, payload: EvaluationCreate,
               scope: Scope | None = None) -> Evaluation:
        if self.candidates.get(payload.candidate_id) is None:
            raise NotFoundError(f"Candidate {payload.candidate_id} was not found")
        payload = self._apply_evaluator_scope(payload, scope)
        scores = self._resolve_scores(payload.scores)
        existing = self.evaluations.for_candidate_interview(
            payload.candidate_id, payload.interview_id, payload.evaluator_faculty_id)
        if existing:
            return self.update(existing.id, EvaluationUpdate(
                panel_id=payload.panel_id,
                evaluator_faculty_id=payload.evaluator_faculty_id,
                evaluation_date=payload.evaluation_date, scores=payload.scores,
                recommendation=payload.recommendation, remarks=payload.remarks),
                scope)
        evaluation = self.evaluations.create(
            candidate_id=payload.candidate_id, interview_id=payload.interview_id,
            panel_id=payload.panel_id,
            evaluator_faculty_id=payload.evaluator_faculty_id,
            evaluation_date=payload.evaluation_date or date.today(),
            recommendation=payload.recommendation, remarks=payload.remarks)
        for metric_id, raw, comment in scores:
            self.scores.create(evaluation_id=evaluation.id, metric_id=metric_id,
                               raw_score=raw, comment=comment)
        self.db.flush()
        self.db.refresh(evaluation)
        return self.recalculate(evaluation)

    def update(self, evaluation_id: int, payload: EvaluationUpdate,
               scope: Scope | None = None) -> Evaluation:
        evaluation = self.evaluations.get_full(evaluation_id)
        if evaluation is None:
            raise NotFoundError(f"Evaluation {evaluation_id} was not found")
        if scope is not None:
            # A teacher may revise their own marks, never a colleague's.
            assert_faculty_owns(scope, evaluation.evaluator_faculty_id,
                                "evaluations")
        data = payload.model_dump(exclude_unset=True)
        for key in ("panel_id", "evaluator_faculty_id", "evaluation_date",
                    "recommendation", "remarks"):
            if key in data and data[key] is not None:
                setattr(evaluation, key, data[key])
        if payload.scores is not None:
            resolved = self._resolve_scores(payload.scores)
            self.scores.clear(evaluation.id)
            evaluation.scores.clear()
            for metric_id, raw, comment in resolved:
                evaluation.scores.append(EvaluationScore(
                    evaluation_id=evaluation.id, metric_id=metric_id,
                    raw_score=raw, comment=comment))
        self.db.flush()
        return self.recalculate(evaluation)

    def delete(self, evaluation_id: int, scope: Scope | None = None) -> None:
        evaluation = self.evaluations.get(evaluation_id)
        if evaluation is None:
            raise NotFoundError(f"Evaluation {evaluation_id} was not found")
        if scope is not None:
            assert_faculty_owns(scope, evaluation.evaluator_faculty_id,
                                "evaluations")
        self.evaluations.delete(evaluation)

    def upsert_from_import(self, *, candidate_id: int, panel_id: int | None,
                           evaluator_faculty_id: int | None,
                           evaluation_date: date | None,
                           scores: Iterable[dict[str, Any]],
                           recommendation: str | None,
                           remarks: str | None) -> bool:
        """Used by the Excel importer; returns True when a new row was created."""
        existing = self.evaluations.for_candidate_interview(
            candidate_id, None, evaluator_faculty_id)
        score_inputs = [ScoreInput(metric_id=s["metric_id"], raw_score=s["raw_score"])
                        for s in scores]
        if existing:
            self.update(existing.id, EvaluationUpdate(
                panel_id=panel_id, evaluator_faculty_id=evaluator_faculty_id,
                evaluation_date=evaluation_date, scores=score_inputs,
                recommendation=recommendation, remarks=remarks))
            return False
        self.create(EvaluationCreate(
            candidate_id=candidate_id, panel_id=panel_id,
            evaluator_faculty_id=evaluator_faculty_id,
            evaluation_date=evaluation_date, scores=score_inputs,
            recommendation=recommendation, remarks=remarks))
        return True

    # ---------------------------------------------------------------- reporting
    def serialise(self, evaluation: Evaluation) -> dict[str, Any]:
        data = {
            "id": evaluation.id,
            "candidate_id": evaluation.candidate_id,
            "interview_id": evaluation.interview_id,
            "panel_id": evaluation.panel_id,
            "evaluator_faculty_id": evaluation.evaluator_faculty_id,
            "evaluation_date": evaluation.evaluation_date,
            "overall_score": evaluation.overall_score,
            "normalized_score": evaluation.normalized_score,
            "max_possible_score": evaluation.max_possible_score,
            "strongest_metric_id": evaluation.strongest_metric_id,
            "weakest_metric_id": evaluation.weakest_metric_id,
            "recommendation": evaluation.recommendation,
            "remarks": evaluation.remarks,
            "scores": evaluation.scores,
            "candidate_code": evaluation.candidate.candidate_code
            if evaluation.candidate else None,
            "candidate_name": evaluation.candidate.candidate_name
            if evaluation.candidate else None,
        }
        return data

    def my_result(self, scope: Scope) -> dict[str, Any]:
        """A candidate's own compiled result, once an administrator releases it.

        Marks stay invisible until published so a teacher's in-progress entry is
        never shown to the person being assessed.
        """
        from app.services.settings_service import SettingsService

        if scope.candidate_id is None:
            raise ValidationError("This view is only available to candidates")
        config = SettingsService(self.db).get()
        if not config.results_published:
            return {"published": False, "profile": None,
                    "message": ("Your results have not been released yet. "
                                "They will appear here once published.")}
        try:
            profile = self.candidate_profile(scope.candidate_id)
        except NotFoundError:
            return {"published": True, "profile": None,
                    "message": "No evaluation has been recorded for you yet."}
        # Rank and per-evaluator breakdown are internal - a candidate sees only
        # their own compiled marks.
        profile.pop("rank", None)
        profile.pop("evaluator_breakdown", None)
        return {"published": True, "profile": profile, "message": None}

    def _apply_evaluator_scope(self, payload: EvaluationCreate,
                               scope: Scope | None) -> EvaluationCreate:
        """Force a faculty submission to be attributed to that faculty member.

        Without this a teacher could file marks under a colleague's name, which
        would then be averaged into the compiled result as if that colleague had
        scored the candidate.
        """
        if scope is None or scope.faculty_id is None:
            return payload
        if (payload.evaluator_faculty_id is not None
                and payload.evaluator_faculty_id != scope.faculty_id):
            assert_faculty_owns(scope, payload.evaluator_faculty_id, "evaluations")
        return payload.model_copy(update={"evaluator_faculty_id": scope.faculty_id})

    # ------------------------------------------------- multi-evaluator compiling
    def _compile_candidate(self, evaluations: Sequence[Evaluation],
                           metrics: dict[int, EvaluationMetric]) -> dict[str, Any]:
        """Combine every evaluator's marks for one candidate into one result.

        Each metric is averaged across the evaluators who scored it, then the
        configured weight formula runs on those compiled averages.  This is the
        "10-11 components from 2 teachers -> automate compiling" requirement: it
        works for one, two or N evaluators and keeps the same scales that a
        single-evaluator result uses.
        """
        raw_by_metric: dict[int, list[float]] = {}
        for evaluation in evaluations:
            for score in evaluation.scores:
                if score.metric_id in metrics:
                    raw_by_metric.setdefault(score.metric_id, []).append(score.raw_score)

        weighted_total = 0.0
        normalised_weighted = 0.0
        weight_total = 0.0
        max_possible = 0.0
        best: tuple[float, int] | None = None
        worst: tuple[float, int] | None = None
        spreads: list[float] = []
        compiled: list[dict[str, Any]] = []

        for metric in sorted(metrics.values(), key=lambda m: m.display_order):
            values = raw_by_metric.get(metric.id)
            if not values:
                continue
            average = sum(values) / len(values)
            span = max(1e-9, metric.max_score - metric.min_score)
            clamped = min(max(average, metric.min_score), metric.max_score)
            normalised = ((clamped - metric.min_score) / span
                          * app_settings.EVALUATION_NORMALISED_SCALE)
            spread = (max(values) - min(values)) if len(values) > 1 else 0.0
            if len(values) > 1:
                spreads.append(spread)

            weighted_total += clamped * metric.weight
            normalised_weighted += normalised * metric.weight
            weight_total += metric.weight
            max_possible += metric.max_score * metric.weight
            if best is None or normalised > best[0]:
                best = (normalised, metric.id)
            if worst is None or normalised < worst[0]:
                worst = (normalised, metric.id)

            compiled.append({
                "metric_id": metric.id,
                "metric_key": metric.metric_key,
                "metric_name": metric.name,
                "raw_score": round(average, 4),
                "normalized_score": round(normalised, 4),
                "weighted_score": round(clamped * metric.weight, 4),
                "max_score": metric.max_score,
                "weight": metric.weight,
                "evaluator_count": len(values),
                "spread": round(spread, 4),
            })

        recommendations = [e.recommendation for e in evaluations if e.recommendation]
        return {
            "overall_score": round(weighted_total, 4),
            "normalized_score": round(
                normalised_weighted / weight_total if weight_total else 0.0, 4),
            "max_possible_score": round(max_possible, 4),
            "metrics": compiled,
            "metric_scores": {m["metric_key"]: m["raw_score"] for m in compiled},
            "strongest_metric": metrics[best[1]].name if best else None,
            "weakest_metric": metrics[worst[1]].name if worst else None,
            "evaluator_count": len(evaluations),
            "agreement_spread": round(sum(spreads) / len(spreads), 4) if spreads else None,
            "recommendation": recommendations[0] if recommendations else None,
        }

    def _grouped_by_candidate(self) -> dict[int, list[Evaluation]]:
        grouped: dict[int, list[Evaluation]] = {}
        for evaluation in self.evaluations.all_full():
            grouped.setdefault(evaluation.candidate_id, []).append(evaluation)
        return grouped

    def rankings(self, *, limit: int | None = None) -> list[dict[str, Any]]:
        """One row per candidate, compiled across every evaluator who scored them."""
        metrics = {m.id: m for m in self.list_metrics()}
        rows: list[dict[str, Any]] = []
        for candidate_id, evaluations in self._grouped_by_candidate().items():
            candidate = evaluations[0].candidate
            compiled = self._compile_candidate(evaluations, metrics)
            rows.append({
                "candidate_id": candidate_id,
                "candidate_code": candidate.candidate_code if candidate else "",
                "candidate_name": candidate.candidate_name if candidate else "",
                "department": candidate.department if candidate else None,
                "overall_score": compiled["overall_score"],
                "normalized_score": compiled["normalized_score"],
                "metric_scores": compiled["metric_scores"],
                "strongest_metric": compiled["strongest_metric"],
                "weakest_metric": compiled["weakest_metric"],
                "recommendation": compiled["recommendation"],
                "evaluator_count": compiled["evaluator_count"],
                "agreement_spread": compiled["agreement_spread"],
            })
        rows.sort(key=lambda r: (-r["overall_score"], r["candidate_code"]))
        for position, row in enumerate(rows, start=1):
            row["rank"] = position
        return rows[:limit] if limit else rows

    def candidate_profile(self, candidate_id: int) -> dict[str, Any]:
        candidate = self.candidates.get(candidate_id)
        if candidate is None:
            raise NotFoundError(f"Candidate {candidate_id} was not found")
        evaluations = self.evaluations.all_full(candidate_id=candidate_id)
        if not evaluations:
            raise NotFoundError(f"No evaluation recorded for candidate {candidate_id}")
        metrics = {m.id: m for m in self.list_metrics()}
        compiled = self._compile_candidate(evaluations, metrics)
        ranking = {row["candidate_id"]: row["rank"] for row in self.rankings()}

        breakdown = []
        for evaluation in evaluations:
            breakdown.append({
                "evaluation_id": evaluation.id,
                "evaluator_faculty_id": evaluation.evaluator_faculty_id,
                "evaluator_name": (evaluation.evaluator.faculty_name
                                   if evaluation.evaluator else None),
                "evaluation_date": (evaluation.evaluation_date.isoformat()
                                    if evaluation.evaluation_date else None),
                "overall_score": evaluation.overall_score,
                "normalized_score": evaluation.normalized_score,
                "recommendation": evaluation.recommendation,
                "scores": {metrics[s.metric_id].metric_key: s.raw_score
                           for s in evaluation.scores if s.metric_id in metrics},
            })

        return {
            "candidate_id": candidate.id,
            "candidate_code": candidate.candidate_code,
            "candidate_name": candidate.candidate_name,
            "overall_score": compiled["overall_score"],
            "normalized_score": compiled["normalized_score"],
            "rank": ranking.get(candidate.id),
            "metrics": compiled["metrics"],
            "strongest_metric": compiled["strongest_metric"],
            "weakest_metric": compiled["weakest_metric"],
            "evaluator_count": compiled["evaluator_count"],
            "evaluator_breakdown": breakdown,
        }
