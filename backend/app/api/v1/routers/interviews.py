from __future__ import annotations

from datetime import date, time

from fastapi import APIRouter, Query, status
from pydantic import BaseModel

from app.api.deps import CurrentUser, DbSession
from app.core.exceptions import NotFoundError
from app.models.enums import InterviewStatus
from app.repositories import InterviewRepository
from app.schemas.common import Message
from app.schemas.interview import (CalendarEvent, HistoryRead, InterviewCreate,
                                   InterviewRead, LockRequest,
                                   ManualChangeResponse, RescheduleRequest,
                                   StatusChangeRequest)
from app.services.history_service import HistoryService
from app.services.interview_service import InterviewService

router = APIRouter(prefix="/interviews", tags=["Interview Schedule"])


class FacultyUnavailableRequest(BaseModel):
    faculty_id: int
    date: date
    start_time: time
    end_time: time
    reason: str | None = None


@router.get("", response_model=list[InterviewRead], summary="List/filter interviews")
def list_interviews(db: DbSession, user: CurrentUser,
                    status_filter: InterviewStatus | None = Query(default=None,
                                                                  alias="status"),
                    candidate_id: int | None = None, panel_id: int | None = None,
                    faculty_id: int | None = None, department: str | None = None,
                    start_date: date | None = None, end_date: date | None = None,
                    skip: int = 0, limit: int | None = Query(default=500, le=2000)):
    rows = InterviewRepository(db).search(
        status=status_filter.value if status_filter else None,
        candidate_id=candidate_id, panel_id=panel_id, faculty_id=faculty_id,
        department=department, start=start_date, end=end_date, skip=skip, limit=limit)
    return [InterviewRead.model_validate(row) for row in rows]


@router.get("/calendar", response_model=list[CalendarEvent],
            summary="Calendar events for the day/week/table views")
def calendar(db: DbSession, user: CurrentUser, start_date: date | None = None,
             end_date: date | None = None, panel_id: int | None = None,
             faculty_id: int | None = None, department: str | None = None,
             status_filter: InterviewStatus | None = Query(default=None, alias="status")):
    filters: dict = {}
    if panel_id:
        filters["panel_id"] = panel_id
    if faculty_id:
        filters["faculty_id"] = faculty_id
    if department:
        filters["department"] = department
    if status_filter:
        filters["status"] = status_filter.value
    return InterviewService(db).calendar_events(start=start_date, end=end_date,
                                                **filters)


@router.get("/conflicts", summary="Conflicts across the current schedule")
def conflicts(db: DbSession, user: CurrentUser):
    return InterviewService(db).detect_all_conflicts()


@router.get("/{interview_id}", response_model=InterviewRead, summary="Get an interview")
def get_interview(interview_id: int, db: DbSession, user: CurrentUser):
    row = InterviewRepository(db).get_full(interview_id)
    if row is None:
        raise NotFoundError(f"Interview {interview_id} was not found")
    return InterviewRead.model_validate(row)


@router.get("/{interview_id}/history", response_model=list[HistoryRead],
            summary="Change history for an interview")
def history(interview_id: int, db: DbSession, user: CurrentUser):
    return [HistoryRead.model_validate(row)
            for row in HistoryService(db).for_interview(interview_id)]


@router.post("", response_model=ManualChangeResponse,
             status_code=status.HTTP_201_CREATED,
             summary="Create an interview manually")
def create_interview(payload: InterviewCreate, db: DbSession, user: CurrentUser):
    return InterviewService(db).create_manual(payload, user.id)


@router.put("/{interview_id}/reschedule", response_model=ManualChangeResponse,
            summary="Manually change time, panel or faculty")
def reschedule(interview_id: int, payload: RescheduleRequest, db: DbSession,
               user: CurrentUser):
    return InterviewService(db).reschedule(interview_id, payload, user.id)


@router.put("/{interview_id}/status", response_model=ManualChangeResponse,
            summary="Change the interview status")
def change_status(interview_id: int, payload: StatusChangeRequest, db: DbSession,
                  user: CurrentUser):
    return InterviewService(db).change_status(interview_id, payload.status,
                                              payload.reason, user.id)


@router.put("/{interview_id}/lock", response_model=ManualChangeResponse,
            summary="Lock or unlock an interview")
def set_lock(interview_id: int, payload: LockRequest, db: DbSession, user: CurrentUser):
    return InterviewService(db).set_lock(interview_id, payload.is_locked,
                                         payload.reason, user.id)


@router.post("/{interview_id}/cancel", response_model=ManualChangeResponse,
             summary="Cancel an interview")
def cancel(interview_id: int, db: DbSession, user: CurrentUser,
           reason: str | None = None):
    return InterviewService(db).cancel(interview_id, reason, user.id)


@router.delete("/{interview_id}", response_model=Message, summary="Delete an interview")
def delete_interview(interview_id: int, db: DbSession, user: CurrentUser):
    InterviewService(db).delete(interview_id)
    return Message(message=f"Interview {interview_id} deleted")


@router.post("/faculty-unavailable", summary="Mark a faculty member unavailable")
def faculty_unavailable(payload: FacultyUnavailableRequest, db: DbSession,
                        user: CurrentUser):
    return InterviewService(db).mark_faculty_unavailable(
        faculty_id=payload.faculty_id, day=payload.date, start=payload.start_time,
        end=payload.end_time, reason=payload.reason, user_id=user.id)
