from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Query

from app.api.deps import CurrentScope, DbSession, ManagerUser
from app.core.exceptions import PermissionError_
from app.schemas.faculty import (FacultyTimelineDay, FreeSlotGroup, FreeSlotRead,
                                 FreeSlotRecalculateRequest,
                                 FreeSlotRecalculateResponse)
from app.services.free_slot_service import FreeSlotService

router = APIRouter(prefix="/free-slots", tags=["Free Slots"])


def _scoped_faculty(scope, faculty_id: int | None) -> int | None:
    """Faculty see their own diary; students have none to see."""
    if scope.candidate_id is not None:
        raise PermissionError_("Faculty availability is not visible to candidates.")
    return scope.faculty_id if scope.faculty_id is not None else faculty_id


@router.get("", response_model=list[FreeSlotRead], summary="List calculated free slots")
def list_free_slots(db: DbSession, scope: CurrentScope,
                    faculty_id: int | None = None,
                    start_date: date | None = None, end_date: date | None = None,
                    min_minutes: int = Query(default=0, ge=0)):
    faculty_id = _scoped_faculty(scope, faculty_id)
    rows = FreeSlotService(db).free_repo.in_range(
        faculty_ids=[faculty_id] if faculty_id else None,
        start=start_date, end=end_date)
    return [FreeSlotRead.model_validate(row) for row in rows
            if row.duration_minutes >= min_minutes]


@router.get("/grouped", response_model=list[FreeSlotGroup],
            summary="Free slots grouped by faculty and day")
def grouped_free_slots(db: DbSession, scope: CurrentScope,
                       faculty_id: int | None = None,
                       start_date: date | None = None, end_date: date | None = None):
    faculty_id = _scoped_faculty(scope, faculty_id)
    return FreeSlotService(db).grouped(
        faculty_ids=[faculty_id] if faculty_id else None,
        start=start_date, end=end_date)


@router.get("/timeline", response_model=list[FacultyTimelineDay],
            summary="Booked / busy / free segments per faculty day")
def timeline(db: DbSession, scope: CurrentScope, faculty_id: int | None = None,
             start_date: date | None = None, end_date: date | None = None):
    """Drives the colour-coded availability view."""
    faculty_id = _scoped_faculty(scope, faculty_id)
    return FreeSlotService(db).timeline(
        faculty_ids=[faculty_id] if faculty_id else None,
        start=start_date, end=end_date)


@router.post("/recalculate", response_model=FreeSlotRecalculateResponse,
             summary="Recalculate free slots from availability and bookings")
def recalculate(payload: FreeSlotRecalculateRequest, db: DbSession,
                user: ManagerUser):
    stats = FreeSlotService(db).recalculate(faculty_ids=payload.faculty_ids,
                                            start=payload.start_date,
                                            end=payload.end_date)
    return FreeSlotRecalculateResponse(**stats, start_date=payload.start_date,
                                       end_date=payload.end_date)
