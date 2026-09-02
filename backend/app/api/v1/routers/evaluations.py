from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import (CurrentScope, DbSession, ManagerUser,
                          ReportUser, StaffUser)
from app.core.exceptions import NotFoundError, PermissionError_
from app.core.permissions import assert_faculty_owns
from app.repositories import EvaluationRepository
from app.schemas.common import Message
from app.schemas.evaluation import (CandidateMetricProfile, EvaluationCreate,
                                    EvaluationRead, EvaluationUpdate, MetricCreate,
                                    MetricRead, MetricUpdate, MetricWeightsRequest,
                                    RankingRow)
from app.services.evaluation_service import EvaluationService

router = APIRouter(prefix="/evaluations", tags=["Evaluation Management"])
metrics_router = APIRouter(prefix="/evaluation-metrics", tags=["Evaluation Metrics"])


# ------------------------------------------------------------------- metrics
@metrics_router.get("", response_model=list[MetricRead],
                    summary="List the configurable evaluation metrics")
def list_metrics(db: DbSession, user: StaffUser, active_only: bool = False):
    return [MetricRead.model_validate(m)
            for m in EvaluationService(db).list_metrics(active_only=active_only)]


@metrics_router.post("", response_model=MetricRead, status_code=status.HTTP_201_CREATED,
                     summary="Add an evaluation metric")
def create_metric(payload: MetricCreate, db: DbSession, user: ManagerUser):
    return MetricRead.model_validate(EvaluationService(db).create_metric(payload))


@metrics_router.put("/{metric_id}", response_model=MetricRead,
                    summary="Update a metric (name, weight, range)")
def update_metric(metric_id: int, payload: MetricUpdate, db: DbSession,
                  user: ManagerUser):
    return MetricRead.model_validate(
        EvaluationService(db).update_metric(metric_id, payload))


@metrics_router.put("", response_model=list[MetricRead], summary="Set metric weights")
def set_weights(payload: MetricWeightsRequest, db: DbSession, user: ManagerUser):
    return [MetricRead.model_validate(m)
            for m in EvaluationService(db).set_weights(payload)]


@metrics_router.delete("/{metric_id}", response_model=Message,
                       summary="Delete a metric")
def delete_metric(metric_id: int, db: DbSession, user: ManagerUser):
    EvaluationService(db).delete_metric(metric_id)
    return Message(message=f"Metric {metric_id} deleted")


# --------------------------------------------------------------- evaluations
@router.get("", response_model=list[EvaluationRead], summary="List evaluations")
def list_evaluations(db: DbSession, scope: CurrentScope,
                     candidate_id: int | None = None,
                     panel_id: int | None = None, skip: int = 0,
                     limit: int | None = 500):
    if scope.candidate_id is not None:
        raise PermissionError_(
            "Use /evaluations/my-result to see your own marks.")
    service = EvaluationService(db)
    rows = EvaluationRepository(db).all_full(candidate_id=candidate_id,
                                             panel_id=panel_id, skip=skip, limit=limit)
    return [EvaluationRead.model_validate(service.serialise(row)) for row in rows]


@router.get("/rankings", response_model=list[RankingRow], summary="Candidate ranking")
def rankings(db: DbSession, user: ReportUser, limit: int | None = None):
    return EvaluationService(db).rankings(limit=limit)


@router.get("/candidate/{candidate_id}/profile", response_model=CandidateMetricProfile,
            summary="Metric profile for one candidate (radar chart data)")
def profile(candidate_id: int, db: DbSession, user: ReportUser):
    return EvaluationService(db).candidate_profile(candidate_id)


@router.get("/my-result", summary="Your own compiled result (candidate)")
def my_result(db: DbSession, scope: CurrentScope):
    return EvaluationService(db).my_result(scope)


@router.get("/{evaluation_id}", response_model=EvaluationRead,
            summary="Get one evaluation")
def get_evaluation(evaluation_id: int, db: DbSession, user: StaffUser):
    service = EvaluationService(db)
    row = EvaluationRepository(db).get_full(evaluation_id)
    if row is None:
        raise NotFoundError(f"Evaluation {evaluation_id} was not found")
    return EvaluationRead.model_validate(service.serialise(row))


@router.post("", response_model=EvaluationRead, status_code=status.HTTP_201_CREATED,
             summary="Record an evaluation")
def create_evaluation(payload: EvaluationCreate, db: DbSession,
                      scope: CurrentScope):
    if scope.candidate_id is not None:
        raise PermissionError_("Candidates cannot record evaluations.")
    service = EvaluationService(db)
    return EvaluationRead.model_validate(
        service.serialise(service.create(payload, scope)))


@router.put("/{evaluation_id}", response_model=EvaluationRead,
            summary="Update an evaluation")
def update_evaluation(evaluation_id: int, payload: EvaluationUpdate, db: DbSession,
                      scope: CurrentScope):
    if scope.candidate_id is not None:
        raise PermissionError_("Candidates cannot record evaluations.")
    service = EvaluationService(db)
    return EvaluationRead.model_validate(
        service.serialise(service.update(evaluation_id, payload, scope)))


@router.delete("/{evaluation_id}", response_model=Message,
               summary="Delete an evaluation")
def delete_evaluation(evaluation_id: int, db: DbSession, scope: CurrentScope):
    if scope.candidate_id is not None:
        raise PermissionError_("Candidates cannot delete evaluations.")
    EvaluationService(db).delete(evaluation_id, scope)
    return Message(message=f"Evaluation {evaluation_id} deleted")
