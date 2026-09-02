from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentScope, DbSession, ManagerUser, StaffUser
from app.core.exceptions import NotFoundError, ValidationError
from app.core.permissions import assert_candidate_owns
from app.models.enums import CandidateStatus
from app.repositories import CandidateRepository
from app.schemas.candidate import CandidateCreate, CandidateRead, CandidateUpdate
from app.schemas.common import Message

router = APIRouter(prefix="/candidates", tags=["Candidates"])


@router.get("", response_model=list[CandidateRead], summary="List/search candidates")
def list_candidates(db: DbSession, scope: CurrentScope,
                    q: str | None = Query(default=None, description="Free-text search"),
                    status_filter: CandidateStatus | None = Query(default=None,
                                                                  alias="status"),
                    department: str | None = None,
                    skip: int = 0, limit: int | None = Query(default=200, le=1000)):
    repo = CandidateRepository(db)
    # A student's "list" is just themselves.
    if scope.candidate_id is not None:
        row = repo.get(scope.candidate_id)
        return [CandidateRead.model_validate(row)] if row else []
    rows = repo.search(query=q,
                       status=status_filter.value if status_filter else None,
                       department=department, skip=skip, limit=limit)
    return [CandidateRead.model_validate(row) for row in rows]


@router.get("/{candidate_id}", response_model=CandidateRead, summary="Get a candidate")
def get_candidate(candidate_id: int, db: DbSession, scope: CurrentScope):
    assert_candidate_owns(scope, candidate_id, "record")
    row = CandidateRepository(db).get(candidate_id)
    if row is None:
        raise NotFoundError(f"Candidate {candidate_id} was not found")
    return CandidateRead.model_validate(row)


@router.post("", response_model=CandidateRead, status_code=status.HTTP_201_CREATED,
             summary="Create a candidate")
def create_candidate(payload: CandidateCreate, db: DbSession, user: ManagerUser):
    repo = CandidateRepository(db)
    if repo.by_code(payload.candidate_code):
        raise ValidationError(
            f"Candidate code '{payload.candidate_code}' already exists")
    data = payload.model_dump()
    data["availability"] = [w if isinstance(w, dict) else w.model_dump(mode="json")
                            for w in payload.availability]
    return CandidateRead.model_validate(repo.create(**data))


@router.put("/{candidate_id}", response_model=CandidateRead, summary="Update a candidate")
def update_candidate(candidate_id: int, payload: CandidateUpdate, db: DbSession,
                     user: ManagerUser):
    repo = CandidateRepository(db)
    row = repo.get(candidate_id)
    if row is None:
        raise NotFoundError(f"Candidate {candidate_id} was not found")
    data = payload.model_dump(exclude_unset=True)
    if payload.availability is not None:
        data["availability"] = [w.model_dump(mode="json") for w in payload.availability]
    for key, value in data.items():
        if value is not None:
            setattr(row, key, value)
    db.flush()
    return CandidateRead.model_validate(row)


@router.delete("/{candidate_id}", response_model=Message, summary="Delete a candidate")
def delete_candidate(candidate_id: int, db: DbSession, user: ManagerUser):
    repo = CandidateRepository(db)
    row = repo.get(candidate_id)
    if row is None:
        raise NotFoundError(f"Candidate {candidate_id} was not found")
    repo.delete(row)
    return Message(message=f"Candidate {candidate_id} deleted")
