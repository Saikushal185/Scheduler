from __future__ import annotations

from datetime import date, time

from fastapi import APIRouter, Query, status
from pydantic import BaseModel

from app.api.deps import CurrentScope, DbSession, ManagerUser, StaffUser
from app.core.exceptions import NotFoundError, PermissionError_
from app.core.permissions import Scope, assert_faculty_owns
from app.models import Interview
from app.models.enums import InterviewStatus
from app.repositories import InterviewRepository
from app.schemas.common import Message
from app.schemas.interview import (AvailableSlot, CalendarEvent,
                                   ChangeRequestDecision, ChangeRequestCreate,
                                   ChangeRequestRead, HistoryRead, InterviewCreate,
                                   InterviewRead, LockRequest,
                                   ManualChangeResponse, RescheduleRequest,
                                   StatusChangeRequest)
from app.services.history_service import HistoryService
from app.services.interview_service import InterviewService

router = APIRouter(prefix="/interviews", tags=["Interview Schedule"])
requests_router = APIRouter(prefix="/interview-requests",
                            tags=["Interview Schedule"])


class FacultyUnavailableRequest(BaseModel):
    faculty_id: int
    date: date
    start_time: time
    end_time: time
    reason: str | None = None


def _assert_can_view(scope: Scope, interview: Interview) -> None:
    """Students see only their own interview; faculty only ones they sit on."""
    if scope.candidate_id is not None:
        if interview.candidate_id != scope.candidate_id:
            raise PermissionError_("You can only view your own interview.")
    elif scope.faculty_id is not None:
        panel_ids = {m.faculty_id for m in interview.panel_members}
        if scope.faculty_id not in panel_ids:
            raise PermissionError_(
                "You can only view interviews you are on the panel for.")


@router.get("", response_model=list[InterviewRead], summary="List/filter interviews")
def list_interviews(db: DbSession, scope: CurrentScope,
                    status_filter: InterviewStatus | None = Query(default=None,
                                                                  alias="status"),
                    candidate_id: int | None = None, panel_id: int | None = None,
                    faculty_id: int | None = None, department: str | None = None,
                    start_date: date | None = None, end_date: date | None = None,
                    skip: int = 0, limit: int | None = Query(default=500, le=2000)):
    # Narrow to the caller rather than refusing: the same page serves every role.
    if scope.faculty_id is not None:
        faculty_id = scope.faculty_id
    if scope.candidate_id is not None:
        candidate_id = scope.candidate_id
    rows = InterviewRepository(db).search(
        status=status_filter.value if status_filter else None,
        candidate_id=candidate_id, panel_id=panel_id, faculty_id=faculty_id,
        department=department, start=start_date, end=end_date, skip=skip, limit=limit)
    return [InterviewRead.model_validate(row) for row in rows]


@router.get("/calendar", response_model=list[CalendarEvent],
            summary="Calendar events for the day/week/table views")
def calendar(db: DbSession, scope: CurrentScope, start_date: date | None = None,
             end_date: date | None = None, panel_id: int | None = None,
             faculty_id: int | None = None, department: str | None = None,
             status_filter: InterviewStatus | None = Query(default=None, alias="status")):
    filters: dict = {}
    if scope.faculty_id is not None:
        faculty_id = scope.faculty_id
    if scope.candidate_id is not None:
        filters["candidate_id"] = scope.candidate_id
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
def conflicts(db: DbSession, user: StaffUser):
    return InterviewService(db).detect_all_conflicts()


@router.get("/available-slots", response_model=list[AvailableSlot],
            summary="Bookable slots for a candidate and panel")
def available_slots(db: DbSession, user: ManagerUser, candidate_id: int, panel_id: int,
                    date_: date | None = Query(default=None, alias="date"),
                    start_date: date | None = None, end_date: date | None = None,
                    duration_minutes: int | None = None,
                    limit: int = Query(default=100, ge=1, le=500)):
    """Slots a manual booking may legally use - a clash is impossible by choice."""
    return InterviewService(db).available_slots(
        candidate_id=candidate_id, panel_id=panel_id, day=date_,
        start=start_date, end=end_date, duration_minutes=duration_minutes,
        limit=limit)


@router.get("/{interview_id}", response_model=InterviewRead, summary="Get an interview")
def get_interview(interview_id: int, db: DbSession, scope: CurrentScope):
    row = InterviewRepository(db).get_full(interview_id)
    if row is None:
        raise NotFoundError(f"Interview {interview_id} was not found")
    _assert_can_view(scope, row)
    return InterviewRead.model_validate(row)


@router.get("/{interview_id}/history", response_model=list[HistoryRead],
            summary="Change history for an interview")
def history(interview_id: int, db: DbSession, scope: CurrentScope):
    row = InterviewRepository(db).get_full(interview_id)
    if row is None:
        raise NotFoundError(f"Interview {interview_id} was not found")
    _assert_can_view(scope, row)
    return [HistoryRead.model_validate(h)
            for h in HistoryService(db).for_interview(interview_id)]


@router.post("", response_model=ManualChangeResponse,
             status_code=status.HTTP_201_CREATED,
             summary="Create an interview manually")
def create_interview(payload: InterviewCreate, db: DbSession, user: ManagerUser):
    return InterviewService(db).create_manual(payload, user.id)


@router.put("/{interview_id}/reschedule", response_model=ManualChangeResponse,
            summary="Manually change time, panel or faculty")
def reschedule(interview_id: int, payload: RescheduleRequest, db: DbSession,
               user: ManagerUser):
    return InterviewService(db).reschedule(interview_id, payload, user.id)


@router.put("/{interview_id}/status", response_model=ManualChangeResponse,
            summary="Change the interview status")
def change_status(interview_id: int, payload: StatusChangeRequest, db: DbSession,
                  user: ManagerUser):
    return InterviewService(db).change_status(interview_id, payload.status,
                                              payload.reason, user.id)


@router.put("/{interview_id}/lock", response_model=ManualChangeResponse,
            summary="Lock or unlock an interview")
def set_lock(interview_id: int, payload: LockRequest, db: DbSession, user: ManagerUser):
    return InterviewService(db).set_lock(interview_id, payload.is_locked,
                                         payload.reason, user.id)


@router.post("/{interview_id}/cancel", response_model=ManualChangeResponse,
             summary="Cancel an interview")
def cancel(interview_id: int, db: DbSession, user: ManagerUser,
           reason: str | None = None):
    return InterviewService(db).cancel(interview_id, reason, user.id)


@router.delete("/{interview_id}", response_model=Message, summary="Delete an interview")
def delete_interview(interview_id: int, db: DbSession, user: ManagerUser):
    InterviewService(db).delete(interview_id)
    return Message(message=f"Interview {interview_id} deleted")


@router.post("/faculty-unavailable", summary="Mark a faculty member unavailable")
def faculty_unavailable(payload: FacultyUnavailableRequest, db: DbSession,
                        scope: CurrentScope):
    # A faculty member may block their own diary, nobody else's.
    if scope.candidate_id is not None:
        raise PermissionError_("Students cannot change faculty availability.")
    assert_faculty_owns(scope, payload.faculty_id, "availability")
    return InterviewService(db).mark_faculty_unavailable(
        faculty_id=payload.faculty_id, day=payload.date, start=payload.start_time,
        end=payload.end_time, reason=payload.reason, user_id=scope.user.id)


# ------------------------------------------------- candidate self-service
@router.post("/{interview_id}/confirm", response_model=ManualChangeResponse,
             summary="Confirm attendance (candidate)")
def confirm_attendance(interview_id: int, db: DbSession, scope: CurrentScope):
    return InterviewService(db).confirm_attendance(interview_id, scope)


@router.post("/{interview_id}/change-request", response_model=ChangeRequestRead,
             status_code=status.HTTP_201_CREATED,
             summary="Ask for a different slot (candidate)")
def request_change(interview_id: int, payload: ChangeRequestCreate, db: DbSession,
                   scope: CurrentScope):
    return InterviewService(db).create_change_request(interview_id, payload, scope)


# ------------------------------------------------------- administrator queue
@requests_router.get("", response_model=list[ChangeRequestRead],
                     summary="Reschedule requests from candidates")
def list_change_requests(db: DbSession, scope: CurrentScope,
                         status_filter: str | None = Query(default=None,
                                                           alias="status")):
    return InterviewService(db).list_change_requests(scope, status=status_filter)


@requests_router.post("/{request_id}/decide", response_model=ChangeRequestRead,
                      summary="Approve or reject a reschedule request")
def decide_change_request(request_id: int, payload: ChangeRequestDecision,
                          db: DbSession, user: ManagerUser):
    return InterviewService(db).decide_change_request(request_id, payload, user.id)
