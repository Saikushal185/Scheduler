from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, DbSession
from app.core.exceptions import NotFoundError, ValidationError
from app.repositories import (AvailabilityRepository, BusySlotRepository,
                              FacultyRepository)
from app.schemas.common import Message
from app.schemas.faculty import (AvailabilityCreate, AvailabilityRead,
                                 AvailabilityUpdate, BusySlotCreate, BusySlotRead,
                                 FacultyCreate, FacultyRead, FacultyUpdate)
from app.services.free_slot_service import FreeSlotService

router = APIRouter(prefix="/faculty", tags=["Faculty"])


@router.get("", response_model=list[FacultyRead], summary="List/search faculty")
def list_faculty(db: DbSession, user: CurrentUser, q: str | None = None,
                 department: str | None = None, skip: int = 0,
                 limit: int | None = Query(default=200, le=1000)):
    rows = FacultyRepository(db).search(query=q, department=department, skip=skip,
                                        limit=limit)
    return [FacultyRead.model_validate(row) for row in rows]


@router.get("/departments", response_model=list[str], summary="Distinct departments")
def departments(db: DbSession, user: CurrentUser):
    return FacultyRepository(db).departments()


@router.get("/{faculty_id}", response_model=FacultyRead, summary="Get a faculty member")
def get_faculty(faculty_id: int, db: DbSession, user: CurrentUser):
    row = FacultyRepository(db).get(faculty_id)
    if row is None:
        raise NotFoundError(f"Faculty {faculty_id} was not found")
    return FacultyRead.model_validate(row)


@router.post("", response_model=FacultyRead, status_code=status.HTTP_201_CREATED,
             summary="Create a faculty member")
def create_faculty(payload: FacultyCreate, db: DbSession, user: CurrentUser):
    repo = FacultyRepository(db)
    if repo.by_code(payload.faculty_code):
        raise ValidationError(f"Faculty code '{payload.faculty_code}' already exists")
    return FacultyRead.model_validate(repo.create(**payload.model_dump()))


@router.put("/{faculty_id}", response_model=FacultyRead, summary="Update a faculty member")
def update_faculty(faculty_id: int, payload: FacultyUpdate, db: DbSession,
                   user: CurrentUser):
    repo = FacultyRepository(db)
    row = repo.get(faculty_id)
    if row is None:
        raise NotFoundError(f"Faculty {faculty_id} was not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(row, key, value)
    db.flush()
    FreeSlotService(db).recalculate_for_faculty([faculty_id])
    return FacultyRead.model_validate(row)


@router.delete("/{faculty_id}", response_model=Message, summary="Delete a faculty member")
def delete_faculty(faculty_id: int, db: DbSession, user: CurrentUser):
    repo = FacultyRepository(db)
    row = repo.get(faculty_id)
    if row is None:
        raise NotFoundError(f"Faculty {faculty_id} was not found")
    repo.delete(row)
    return Message(message=f"Faculty {faculty_id} deleted")


# --------------------------------------------------------------- availability
availability_router = APIRouter(prefix="/faculty-availability",
                                tags=["Faculty Availability"])


@router.get("/{faculty_id}/availability", response_model=list[AvailabilityRead],
            summary="Availability windows for one faculty member")
def faculty_availability(faculty_id: int, db: DbSession, user: CurrentUser,
                         start_date: date | None = None, end_date: date | None = None):
    rows = AvailabilityRepository(db).for_faculty(faculty_id, start=start_date,
                                                  end=end_date)
    return [AvailabilityRead.model_validate(row) for row in rows]


@availability_router.get("", response_model=list[AvailabilityRead],
                         summary="List availability windows")
def list_availability(db: DbSession, user: CurrentUser, faculty_id: int | None = None,
                      start_date: date | None = None, end_date: date | None = None):
    repo = AvailabilityRepository(db)
    rows = (repo.for_faculty(faculty_id, start=start_date, end=end_date) if faculty_id
            else repo.in_range(start_date, end_date))
    return [AvailabilityRead.model_validate(row) for row in rows]


@availability_router.post("", response_model=AvailabilityRead,
                          status_code=status.HTTP_201_CREATED,
                          summary="Declare availability")
def create_availability(payload: AvailabilityCreate, db: DbSession, user: CurrentUser):
    if FacultyRepository(db).get(payload.faculty_id) is None:
        raise NotFoundError(f"Faculty {payload.faculty_id} was not found")
    repo = AvailabilityRepository(db)
    if repo.get_by(faculty_id=payload.faculty_id, date=payload.date,
                   start_time=payload.start_time, end_time=payload.end_time):
        raise ValidationError("An identical availability window already exists")
    row = repo.create(**payload.model_dump())
    # Availability changed -> free slots must be recalculated.
    FreeSlotService(db).recalculate_for_faculty([payload.faculty_id])
    return AvailabilityRead.model_validate(row)


@availability_router.put("/{availability_id}", response_model=AvailabilityRead,
                         summary="Update an availability window")
def update_availability(availability_id: int, payload: AvailabilityUpdate,
                        db: DbSession, user: CurrentUser):
    repo = AvailabilityRepository(db)
    row = repo.get(availability_id)
    if row is None:
        raise NotFoundError(f"Availability window {availability_id} was not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(row, key, value)
    if row.end_time <= row.start_time:
        raise ValidationError("end_time must be after start_time")
    db.flush()
    FreeSlotService(db).recalculate_for_faculty([row.faculty_id])
    return AvailabilityRead.model_validate(row)


@availability_router.delete("/{availability_id}", response_model=Message,
                            summary="Remove an availability window")
def delete_availability(availability_id: int, db: DbSession, user: CurrentUser):
    repo = AvailabilityRepository(db)
    row = repo.get(availability_id)
    if row is None:
        raise NotFoundError(f"Availability window {availability_id} was not found")
    faculty_id = row.faculty_id
    repo.delete(row)
    FreeSlotService(db).recalculate_for_faculty([faculty_id])
    return Message(message=f"Availability window {availability_id} deleted")


# ----------------------------------------------------------------- busy slots
busy_router = APIRouter(prefix="/faculty-busy-slots", tags=["Faculty Availability"])


@busy_router.get("", response_model=list[BusySlotRead], summary="List busy slots")
def list_busy(db: DbSession, user: CurrentUser, faculty_id: int | None = None,
              start_date: date | None = None, end_date: date | None = None):
    repo = BusySlotRepository(db)
    rows = (repo.for_faculty(faculty_id) if faculty_id
            else repo.in_range(start_date, end_date))
    return [BusySlotRead.model_validate(row) for row in rows]


@busy_router.post("", response_model=BusySlotRead, status_code=status.HTTP_201_CREATED,
                  summary="Block time for a faculty member")
def create_busy(payload: BusySlotCreate, db: DbSession, user: CurrentUser):
    if FacultyRepository(db).get(payload.faculty_id) is None:
        raise NotFoundError(f"Faculty {payload.faculty_id} was not found")
    row = BusySlotRepository(db).create(**payload.model_dump())
    FreeSlotService(db).recalculate_for_faculty([payload.faculty_id])
    return BusySlotRead.model_validate(row)


@busy_router.delete("/{busy_id}", response_model=Message, summary="Remove a busy slot")
def delete_busy(busy_id: int, db: DbSession, user: CurrentUser):
    repo = BusySlotRepository(db)
    row = repo.get(busy_id)
    if row is None:
        raise NotFoundError(f"Busy slot {busy_id} was not found")
    if row.interview_id is not None:
        raise ValidationError(
            "This block belongs to a scheduled interview; cancel the interview instead")
    faculty_id = row.faculty_id
    repo.delete(row)
    FreeSlotService(db).recalculate_for_faculty([faculty_id])
    return Message(message=f"Busy slot {busy_id} deleted")
