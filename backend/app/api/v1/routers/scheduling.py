from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import DbSession, ManagerUser
from app.core.exceptions import NotFoundError
from app.repositories import ConstraintRepository, RunRepository
from app.schemas.common import Message
from app.schemas.scheduling import (AlgorithmInfo, ConfirmScheduleResponse,
                                    ConstraintCreate, ConstraintRead,
                                    ConstraintUpdate, GenerateScheduleRequest,
                                    RunRead, SchedulePreview)
from app.scheduling import list_algorithms
from app.services.scheduling_service import SchedulingService

router = APIRouter(prefix="/scheduling", tags=["Automated Scheduler"])


@router.get("/algorithms", response_model=list[AlgorithmInfo],
            summary="Available scheduling algorithms")
def algorithms(user: ManagerUser):
    return list_algorithms()


@router.post("/generate", response_model=SchedulePreview,
             status_code=status.HTTP_201_CREATED,
             summary="Run the scheduling engine and return a preview")
def generate(payload: GenerateScheduleRequest, db: DbSession, user: ManagerUser):
    return SchedulingService(db).generate_preview(payload, user.id)


@router.post("/generate-and-confirm", summary="Run the engine and apply the result")
def generate_and_confirm(payload: GenerateScheduleRequest, db: DbSession,
                         user: ManagerUser):
    return SchedulingService(db).generate_and_confirm(payload, user.id)


@router.get("/runs", response_model=list[RunRead], summary="Recent scheduling runs")
def runs(db: DbSession, user: ManagerUser, limit: int = 10):
    return [RunRead.model_validate(run) for run in RunRepository(db).latest(limit)]


@router.get("/runs/{run_id}", response_model=SchedulePreview,
            summary="Preview of a stored run")
def get_run(run_id: int, db: DbSession, user: ManagerUser):
    return SchedulingService(db).get_preview(run_id)


@router.post("/runs/{run_id}/confirm", response_model=ConfirmScheduleResponse,
             summary="Turn a preview into real interviews")
def confirm(run_id: int, db: DbSession, user: ManagerUser,
            replace_existing: bool = True):
    return SchedulingService(db).confirm(run_id, replace_existing=replace_existing,
                                         user_id=user.id)


@router.post("/runs/{run_id}/discard", response_model=Message,
             summary="Discard a preview")
def discard(run_id: int, db: DbSession, user: ManagerUser):
    run = SchedulingService(db).discard(run_id)
    return Message(message=f"Run {run.run_code} discarded")


# ---------------------------------------------------------------- constraints
constraints_router = APIRouter(prefix="/constraints", tags=["Scheduling Constraints"])


@constraints_router.get("", response_model=list[ConstraintRead],
                        summary="List scheduling constraints")
def list_constraints(db: DbSession, user: ManagerUser):
    service = SchedulingService(db)
    service.ensure_constraints()
    return [ConstraintRead.model_validate(row)
            for row in ConstraintRepository(db).ordered()]


@constraints_router.post("", response_model=ConstraintRead,
                         status_code=status.HTTP_201_CREATED,
                         summary="Create a scheduling constraint")
def create_constraint(payload: ConstraintCreate, db: DbSession, user: ManagerUser):
    return ConstraintRead.model_validate(
        ConstraintRepository(db).create(**payload.model_dump()))


@constraints_router.put("/{constraint_id}", response_model=ConstraintRead,
                        summary="Update a scheduling constraint")
def update_constraint(constraint_id: int, payload: ConstraintUpdate, db: DbSession,
                      user: ManagerUser):
    repo = ConstraintRepository(db)
    row = repo.get(constraint_id)
    if row is None:
        raise NotFoundError(f"Constraint {constraint_id} was not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(row, key, value)
    db.flush()
    return ConstraintRead.model_validate(row)


@constraints_router.delete("/{constraint_id}", response_model=Message,
                           summary="Delete a scheduling constraint")
def delete_constraint(constraint_id: int, db: DbSession, user: ManagerUser):
    repo = ConstraintRepository(db)
    row = repo.get(constraint_id)
    if row is None:
        raise NotFoundError(f"Constraint {constraint_id} was not found")
    repo.delete(row)
    return Message(message=f"Constraint {constraint_id} deleted")
