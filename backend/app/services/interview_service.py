"""Interview lifecycle and manual administrator overrides.

Automation never removes control: an administrator can move an interview, swap
the panel or its members, lock, reschedule, cancel or complete it, and mark a
faculty member unavailable.  After every change the system re-checks conflicts,
recalculates the affected free slots, raises warnings and records history.
"""
from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import Any, Sequence

from sqlalchemy.orm import Session

from app.core.config import settings as app_settings
from app.core.exceptions import (ConflictError, NotFoundError,
                                 PermissionError_, ValidationError)
from app.core.logging_config import get_logger
from app.models import Interview, InterviewChangeRequest
from app.models.enums import (AvailabilityStatus, BusySlotSource, CandidateStatus,
                              ChangeRequestStatus, HistoryAction, InterviewStatus)
from app.repositories import (AvailabilityRepository, BusySlotRepository,
                              CandidateRepository, FacultyRepository,
                              InterviewMemberRepository, InterviewRepository,
                              PanelRepository)
from app.scheduling.conflicts import detect_conflicts
from app.scheduling.types import (Assignment, CandidateSpec, ConstraintSpec,
                                  FacultySpec, PanelSpec, SchedulingContext,
                                  SchedulingOptions)
from app.core.permissions import Scope, assert_candidate_owns
from app.scheduling.constraints import evaluate_static
from app.scheduling.domain import _panel_candidate_slots
from app.scheduling.state import SolutionState
from app.schemas.interview import (ChangeRequestCreate, ChangeRequestDecision,
                                   InterviewCreate, RescheduleRequest)
from app.services.free_slot_service import FreeSlotService
from app.services.history_service import HistoryService
from app.services.settings_service import SettingsService
from app.utils.timeutils import (Interval, parse_date, parse_time,
                                 subtract_intervals, to_minutes)

logger = get_logger(__name__)

ACTIVE = (InterviewStatus.SCHEDULED, InterviewStatus.RESCHEDULED,
          InterviewStatus.PENDING, InterviewStatus.CONFLICT)


class InterviewService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.interviews = InterviewRepository(db)
        self.members = InterviewMemberRepository(db)
        self.candidates = CandidateRepository(db)
        self.faculty = FacultyRepository(db)
        self.panels = PanelRepository(db)
        self.availability = AvailabilityRepository(db)
        self.busy = BusySlotRepository(db)
        self.settings = SettingsService(db)
        self.free_slots = FreeSlotService(db)
        self.history = HistoryService(db)

    # ------------------------------------------------------- conflict checking
    def _bookable_map(self) -> dict[int, dict[date, list[Interval]]]:
        """Where each faculty member *may* be booked.

        Declared availability minus commitments that are not interviews - so an
        interview does not appear to conflict with the busy slot it created.
        """
        windows: dict[tuple[int, date], list[Interval]] = defaultdict(list)
        blocks: dict[tuple[int, date], list[Interval]] = defaultdict(list)
        for row in self.availability.in_range():
            key = (row.faculty_id, row.date)
            interval = Interval.from_times(row.start_time, row.end_time)
            if row.availability_status == AvailabilityStatus.AVAILABLE:
                windows[key].append(interval)
            else:
                blocks[key].append(interval)
        for row in self.busy.in_range():
            if row.interview_id is None:
                blocks[(row.faculty_id, row.date)].append(
                    Interval.from_times(row.start_time, row.end_time))
        result: dict[int, dict[date, list[Interval]]] = defaultdict(dict)
        for (faculty_id, day), available in windows.items():
            result[faculty_id][day] = subtract_intervals(
                available, blocks.get((faculty_id, day), []))
        return {k: dict(v) for k, v in result.items()}

    def _context(self, *, ignore_interview_id: int | None = None
                 ) -> tuple[SchedulingContext, list[Assignment]]:
        config = self.settings.get()
        bookable = self._bookable_map()
        faculty = {
            member.id: FacultySpec(
                id=member.id, code=member.faculty_code, name=member.faculty_name,
                department=member.department,
                max_per_day=member.max_interviews_per_day,
                free_slots=bookable.get(member.id, {}))
            for member in self.faculty.all()}
        panels = [PanelSpec(id=p.id, code=p.panel_code, name=p.panel_name,
                            member_ids=[m.faculty_id for m in p.members],
                            mandatory_ids={m.faculty_id for m in p.members
                                           if m.is_mandatory},
                            department=p.department,
                            minimum_panel_size=p.minimum_panel_size,
                            maximum_panel_size=p.maximum_panel_size)
                  for p in self.panels.with_members()]
        candidates = [CandidateSpec(id=c.id, code=c.candidate_code,
                                    name=c.candidate_name, department=c.department)
                      for c in self.candidates.all()]
        assignments: list[Assignment] = []
        durations: set[int] = set()
        for interview in self.interviews.active():
            if interview.id == ignore_interview_id:
                continue
            if not (interview.date and interview.start_time and interview.end_time):
                continue
            slot = Interval.from_times(interview.start_time, interview.end_time)
            durations.add(slot.duration)
            assignments.append(Assignment(
                candidate_id=interview.candidate_id,
                panel_id=interview.panel_id or -1,
                faculty_ids=[m.faculty_id for m in interview.panel_members],
                day=interview.date, slot=slot,
                score=interview.scheduling_score))
        options = SchedulingOptions(
            dates=sorted({a.day for a in assignments}),
            duration_minutes=(durations.pop() if len(durations) == 1
                              else config.interview_duration_minutes),
            break_minutes=config.break_duration_minutes,
            granularity_minutes=config.slot_granularity_minutes,
            day_start=config.day_start_time, day_end=config.day_end_time,
            max_interviews_per_faculty_per_day=(
                config.max_interviews_per_faculty_per_day),
            priority_weights=dict(app_settings.PRIORITY_WEIGHTS))
        ctx = SchedulingContext(candidates=candidates, faculty=faculty, panels=panels,
                                constraints=[], options=options)
        return ctx, assignments

    def detect_all_conflicts(self) -> list[dict[str, Any]]:
        ctx, assignments = self._context()
        return [c.to_dict() for c in detect_conflicts(ctx, assignments)]

    def _check_placement(self, *, interview_id: int | None, candidate_id: int,
                         panel_id: int | None, faculty_ids: Sequence[int],
                         day: date, slot: Interval) -> list[str]:
        """Warnings for a proposed placement (empty list == clean)."""
        ctx, others = self._context(ignore_interview_id=interview_id)
        proposed = Assignment(candidate_id=candidate_id, panel_id=panel_id or -1,
                              faculty_ids=list(faculty_ids), day=day, slot=slot,
                              score=0.0)
        ctx.options.dates = sorted({*(a.day for a in others), day})
        ctx.options.duration_minutes = slot.duration
        conflicts = detect_conflicts(ctx, others + [proposed])
        involved = []
        for conflict in conflicts:
            if (candidate_id in conflict.candidate_ids
                    or set(faculty_ids) & set(conflict.faculty_ids)
                    or (panel_id and panel_id in conflict.panel_ids)):
                involved.append(conflict.message)
        return involved

    # ------------------------------------------------------------------ create
    def create_manual(self, payload: InterviewCreate,
                      user_id: int | None = None) -> dict[str, Any]:
        candidate = self.candidates.get(payload.candidate_id)
        if candidate is None:
            raise NotFoundError(f"Candidate {payload.candidate_id} was not found")
        panel = self.panels.get(payload.panel_id)
        if panel is None:
            raise NotFoundError(f"Panel {payload.panel_id} was not found")
        config = self.settings.get()
        duration = payload.duration_minutes or config.interview_duration_minutes
        start_minute = to_minutes(payload.start_time)
        slot = Interval(start_minute, start_minute + duration)
        faculty_ids = list(payload.faculty_ids or
                           [m.faculty_id for m in panel.members][:panel.minimum_panel_size])
        if not faculty_ids:
            raise ValidationError("Select at least one faculty member for the interview")

        warnings = self._check_placement(
            interview_id=None, candidate_id=candidate.id, panel_id=panel.id,
            faculty_ids=faculty_ids, day=payload.date, slot=slot)
        if warnings and not payload.force:
            raise ConflictError("The interview conflicts with the current schedule",
                                details=warnings)

        interview = self.interviews.create(
            schedule_code=f"INT-{uuid.uuid4().hex[:8].upper()}",
            candidate_id=candidate.id, panel_id=panel.id, date=payload.date,
            start_time=slot.start_time, end_time=slot.end_time,
            duration_minutes=duration,
            status=InterviewStatus.CONFLICT if warnings else InterviewStatus.SCHEDULED,
            is_manual=True, location=payload.location, notes=payload.notes)
        for faculty_id in faculty_ids:
            self.members.create(interview_id=interview.id, faculty_id=faculty_id)
        candidate.status = CandidateStatus.SCHEDULED
        self.db.flush()
        self.history.record(interview, HistoryAction.CREATED, {},
                            self.history.snapshot(interview),
                            reason="Created manually", warnings=warnings,
                            user_id=user_id)
        stats = self.free_slots.recalculate_for_faculty(faculty_ids)
        return self._response(interview, warnings, stats["slots_created"])

    # -------------------------------------------------------------- reschedule
    def reschedule(self, interview_id: int, payload: RescheduleRequest,
                   user_id: int | None = None) -> dict[str, Any]:
        interview = self.interviews.get_full(interview_id)
        if interview is None:
            raise NotFoundError(f"Interview {interview_id} was not found")
        if interview.is_locked and not payload.force:
            raise ConflictError(
                "This interview is locked. Unlock it first or pass force=true.")

        previous = self.history.snapshot(interview)
        previous_faculty = [m.faculty_id for m in interview.panel_members]

        panel = interview.panel
        if payload.panel_id and payload.panel_id != interview.panel_id:
            panel = self.panels.get(payload.panel_id)
            if panel is None:
                raise NotFoundError(f"Panel {payload.panel_id} was not found")

        faculty_ids = list(payload.faculty_ids) if payload.faculty_ids is not None \
            else previous_faculty
        if payload.panel_id and payload.faculty_ids is None and panel:
            faculty_ids = [m.faculty_id for m in panel.members][:panel.minimum_panel_size]
        if panel:
            allowed = {m.faculty_id for m in panel.members}
            unknown = [f for f in faculty_ids if f not in allowed]
            if unknown:
                raise ValidationError(
                    f"Faculty {unknown} are not members of panel {panel.panel_code}")
            if len(faculty_ids) < panel.minimum_panel_size:
                raise ValidationError(
                    f"Panel {panel.panel_code} requires at least "
                    f"{panel.minimum_panel_size} faculty members")

        day = payload.date or interview.date
        start = payload.start_time or interview.start_time
        duration = payload.duration_minutes or interview.duration_minutes
        if not (day and start):
            raise ValidationError("A date and a start time are required")
        start_minute = to_minutes(start)
        slot = Interval(start_minute, start_minute + duration)

        warnings = self._check_placement(
            interview_id=interview.id, candidate_id=interview.candidate_id,
            panel_id=panel.id if panel else None, faculty_ids=faculty_ids,
            day=day, slot=slot)
        if warnings and not payload.force:
            raise ConflictError("The requested change conflicts with the schedule",
                                details=warnings)

        interview.date = day
        interview.start_time = slot.start_time
        interview.end_time = slot.end_time
        interview.duration_minutes = duration
        interview.panel_id = panel.id if panel else None
        interview.is_manual = True
        if payload.location is not None:
            interview.location = payload.location
        if payload.notes is not None:
            interview.notes = payload.notes
        interview.status = (InterviewStatus.CONFLICT if warnings
                            else InterviewStatus.RESCHEDULED)
        self.members.clear(interview.id)
        interview.panel_members.clear()
        for faculty_id in faculty_ids:
            self.members.create(interview_id=interview.id, faculty_id=faculty_id)
        self.db.flush()
        self.db.refresh(interview)

        action = (HistoryAction.PANEL_CHANGED
                  if payload.panel_id or payload.faculty_ids is not None
                  else HistoryAction.RESCHEDULED)
        self.history.record(interview, action, previous,
                            self.history.snapshot(interview),
                            reason=payload.reason or "Manual reschedule",
                            warnings=warnings, user_id=user_id)
        stats = self.free_slots.recalculate_for_faculty(
            set(previous_faculty) | set(faculty_ids))
        return self._response(interview, warnings, stats["slots_created"])

    # ------------------------------------------------------------ status/locks
    def change_status(self, interview_id: int, status: InterviewStatus,
                      reason: str | None = None,
                      user_id: int | None = None) -> dict[str, Any]:
        interview = self.interviews.get_full(interview_id)
        if interview is None:
            raise NotFoundError(f"Interview {interview_id} was not found")
        previous = self.history.snapshot(interview)
        interview.status = status
        candidate = interview.candidate
        if candidate:
            if status == InterviewStatus.COMPLETED:
                candidate.status = CandidateStatus.COMPLETED
            elif status == InterviewStatus.CANCELLED:
                candidate.status = CandidateStatus.UNSCHEDULED
        self.db.flush()
        action = {InterviewStatus.CANCELLED: HistoryAction.CANCELLED,
                  InterviewStatus.COMPLETED: HistoryAction.COMPLETED}.get(
                      status, HistoryAction.STATUS_CHANGED)
        self.history.record(interview, action, previous,
                            self.history.snapshot(interview), reason=reason,
                            user_id=user_id)
        # Cancelling frees the faculty again.
        stats = self.free_slots.recalculate_for_faculty(
            [m.faculty_id for m in interview.panel_members])
        warnings = self._check_placement(
            interview_id=interview.id, candidate_id=interview.candidate_id,
            panel_id=interview.panel_id,
            faculty_ids=[m.faculty_id for m in interview.panel_members],
            day=interview.date, slot=Interval.from_times(interview.start_time,
                                                         interview.end_time)
        ) if status in ACTIVE and interview.date and interview.start_time else []
        return self._response(interview, warnings, stats["slots_created"])

    def set_lock(self, interview_id: int, locked: bool, reason: str | None = None,
                 user_id: int | None = None) -> dict[str, Any]:
        interview = self.interviews.get_full(interview_id)
        if interview is None:
            raise NotFoundError(f"Interview {interview_id} was not found")
        previous = self.history.snapshot(interview)
        interview.is_locked = locked
        self.db.flush()
        self.history.record(
            interview, HistoryAction.LOCKED if locked else HistoryAction.UNLOCKED,
            previous, self.history.snapshot(interview), reason=reason, user_id=user_id)
        return self._response(interview, [], 0)

    def cancel(self, interview_id: int, reason: str | None = None,
               user_id: int | None = None) -> dict[str, Any]:
        return self.change_status(interview_id, InterviewStatus.CANCELLED, reason,
                                  user_id)

    def delete(self, interview_id: int) -> None:
        interview = self.interviews.get_full(interview_id)
        if interview is None:
            raise NotFoundError(f"Interview {interview_id} was not found")
        faculty_ids = [m.faculty_id for m in interview.panel_members]
        self.interviews.delete(interview)
        self.free_slots.recalculate_for_faculty(faculty_ids)

    # -------------------------------------------------- faculty unavailability
    def mark_faculty_unavailable(self, *, faculty_id: int, day: date, start: time,
                                 end: time, reason: str | None = None,
                                 user_id: int | None = None) -> dict[str, Any]:
        """Block time for a faculty member and flag the interviews it breaks."""
        member = self.faculty.get(faculty_id)
        if member is None:
            raise NotFoundError(f"Faculty {faculty_id} was not found")
        if end <= start:
            raise ValidationError("end_time must be after start_time")
        self.busy.create(faculty_id=faculty_id, date=day, start_time=start,
                         end_time=end, source=BusySlotSource.MANUAL,
                         reason=reason or "Marked unavailable")
        blocked = Interval.from_times(start, end)
        affected: list[dict[str, Any]] = []
        for interview in self.interviews.active(start=day, end=day):
            if faculty_id not in {m.faculty_id for m in interview.panel_members}:
                continue
            if not (interview.start_time and interview.end_time):
                continue
            if not Interval.from_times(interview.start_time,
                                       interview.end_time).overlaps(blocked):
                continue
            previous = self.history.snapshot(interview)
            interview.status = InterviewStatus.CONFLICT
            self.db.flush()
            message = (f"{member.faculty_name} is unavailable "
                       f"{start:%H:%M}-{end:%H:%M} on {day}")
            self.history.record(interview, HistoryAction.MANUAL_OVERRIDE, previous,
                                self.history.snapshot(interview), reason=message,
                                warnings=[message], user_id=user_id)
            affected.append({"interview_id": interview.id,
                             "schedule_code": interview.schedule_code,
                             "candidate_name": interview.candidate.candidate_name
                             if interview.candidate else None,
                             "message": message})
        stats = self.free_slots.recalculate_for_faculty([faculty_id])
        return {"faculty_id": faculty_id, "affected_interviews": affected,
                "free_slots_recalculated": stats["slots_created"],
                "warnings": [item["message"] for item in affected]}

    # ---------------------------------------------------------------- calendar
    def calendar_events(self, *, start: date | None = None, end: date | None = None,
                        **filters: Any) -> list[dict[str, Any]]:
        conflicts = self.detect_all_conflicts()
        flagged: set[int] = set()
        for conflict in conflicts:
            flagged.update(conflict.get("candidate_ids", []))
        events = []
        for interview in self.interviews.search(start=start, end=end, limit=None,
                                                **filters):
            if not (interview.date and interview.start_time and interview.end_time):
                continue
            candidate = interview.candidate
            events.append({
                "id": interview.id,
                "title": (f"{candidate.candidate_name} "
                          f"({interview.panel.panel_code})" if candidate and
                          interview.panel else interview.schedule_code),
                "start": datetime.combine(interview.date, interview.start_time),
                "end": datetime.combine(interview.date, interview.end_time),
                "status": interview.status,
                "candidate_name": candidate.candidate_name if candidate else "",
                "candidate_code": candidate.candidate_code if candidate else "",
                "panel_name": interview.panel.panel_name if interview.panel else None,
                "faculty_names": [m.faculty.faculty_name for m in interview.panel_members
                                  if m.faculty],
                "is_locked": interview.is_locked,
                "has_conflict": (interview.status == InterviewStatus.CONFLICT
                                 or interview.candidate_id in flagged),
                "department": candidate.department if candidate else None,
            })
        return events

    # ------------------------------------------------------- bookable slots
    def available_slots(self, *, candidate_id: int, panel_id: int,
                        day: date | None = None, start: date | None = None,
                        end: date | None = None, duration_minutes: int | None = None,
                        limit: int = 100) -> list[dict[str, Any]]:
        """Slots this candidate could legally be booked into with this panel.

        Reuses the scheduling engine rather than reimplementing availability, so
        a manually picked slot is validated and scored exactly the way the
        automated scheduler would score it.
        """
        candidate = self.candidates.get(candidate_id)
        if candidate is None:
            raise NotFoundError(f"Candidate {candidate_id} was not found")
        panel = self.panels.get(panel_id)
        if panel is None:
            raise NotFoundError(f"Panel {panel_id} was not found")

        config = self.settings.get()
        duration = duration_minutes or config.interview_duration_minutes
        if day is not None:
            days = [day]
        else:
            first = start or config.schedule_start_date or date.today()
            last = end or config.schedule_end_date or first
            if last < first:
                raise ValidationError("end_date must not be before start_date")
            days = [first + timedelta(days=i) for i in range((last - first).days + 1)]
            if not config.allow_weekends:
                days = [d for d in days if d.weekday() < 5]
        if not days:
            return []

        ctx, assignments = self._context()
        ctx.options.dates = sorted(set(days))
        ctx.options.duration_minutes = duration
        # `_context()` builds a bare context for conflict detection.  Scoring a
        # suggestion the way the auto-scheduler would needs the live constraint
        # rows and the candidate's real preferences, so load both.
        ctx.constraints = self._active_constraints()
        panel_spec = next((p for p in ctx.panels if p.id == panel_id), None)
        candidate_spec = self._candidate_spec(candidate)
        if panel_spec is None:
            return []
        ctx.candidates = [candidate_spec]

        # Seed the solver state with what is already booked so taken slots drop out.
        state = SolutionState(ctx)
        for assignment in assignments:
            state.commit(assignment)

        window = Interval(to_minutes(config.day_start_time),
                          to_minutes(config.day_end_time))
        faculty_names = {f.id: f.faculty_name for f in self.faculty.all()}
        results: list[dict[str, Any]] = []
        for current in ctx.options.dates:
            for slot in _panel_candidate_slots(ctx, panel_spec, current, window):
                if not candidate_spec.is_available(current, slot):
                    continue
                if not state.candidate_free(candidate_id, current, slot):
                    continue
                if not state.panel_free(panel_id, current, slot):
                    continue
                faculty_ids = state.select_faculty(panel_spec, current, slot)
                if not faculty_ids:
                    continue
                feasible, outcomes, _ = evaluate_static(
                    ctx, candidate_spec, panel_spec, current, slot, faculty_ids)
                if not feasible:
                    continue
                results.append({
                    "date": current,
                    "start_time": slot.start_time,
                    "end_time": slot.end_time,
                    "duration_minutes": slot.duration,
                    "panel_id": panel_id,
                    "faculty_ids": faculty_ids,
                    "faculty_names": [faculty_names.get(f, str(f)) for f in faculty_ids],
                    "score": round(sum(o.score for o in outcomes), 3),
                    "reasons": [o.to_dict() for o in outcomes],
                })
        results.sort(key=lambda r: (-r["score"], r["date"], r["start_time"]))
        return results[:limit]

    def _active_constraints(self) -> list[ConstraintSpec]:
        from app.repositories import ConstraintRepository

        return [
            ConstraintSpec(id=row.id, name=row.name,
                           constraint_type=row.constraint_type, priority=row.priority,
                           scope=row.scope or {}, parameters=row.parameters or {},
                           weight_multiplier=row.weight_multiplier)
            for row in ConstraintRepository(self.db).active()]

    def _candidate_spec(self, candidate) -> CandidateSpec:
        """Full spec including declared availability and stated preferences."""
        availability: dict[date, list[Interval]] = defaultdict(list)
        for window in candidate.availability or []:
            day = parse_date(window.get("date"))
            start = parse_time(window.get("start_time"))
            end = parse_time(window.get("end_time"))
            if day and start and end and end > start:
                availability[day].append(Interval.from_times(start, end))
        return CandidateSpec(
            id=candidate.id, code=candidate.candidate_code,
            name=candidate.candidate_name, department=candidate.department,
            preferred_date=candidate.preferred_date,
            preferred_time=candidate.preferred_time,
            preferred_panel_code=candidate.preferred_panel_code,
            availability=dict(availability),
            required_panel_code=(candidate.constraints or {}).get("required_panel"),
            priority=candidate.priority or 0)

    # -------------------------------------------------- candidate self-service
    def _own_interview(self, interview_id: int, scope: Scope) -> Interview:
        interview = self.interviews.get_full(interview_id)
        if interview is None:
            raise NotFoundError(f"Interview {interview_id} was not found")
        assert_candidate_owns(scope, interview.candidate_id, "interview")
        return interview

    def confirm_attendance(self, interview_id: int, scope: Scope) -> dict[str, Any]:
        interview = self._own_interview(interview_id, scope)
        if interview.status in (InterviewStatus.CANCELLED, InterviewStatus.UNSCHEDULED):
            raise ValidationError(
                "This interview is not active, so attendance cannot be confirmed.")
        interview.candidate_confirmed_at = datetime.now()
        self.db.flush()
        self.history.record(interview, HistoryAction.CONFIRMED, {},
                            self.history.snapshot(interview),
                            reason="Attendance confirmed by the candidate",
                            user_id=scope.user.id)
        return self._response(interview, [], 0)

    def create_change_request(self, interview_id: int, payload: ChangeRequestCreate,
                              scope: Scope) -> dict[str, Any]:
        interview = self._own_interview(interview_id, scope)
        existing = self.db.query(InterviewChangeRequest).filter(
            InterviewChangeRequest.interview_id == interview_id,
            InterviewChangeRequest.status == ChangeRequestStatus.PENDING).first()
        if existing is not None:
            raise ValidationError(
                "You already have a pending request for this interview.")
        request = InterviewChangeRequest(
            interview_id=interview.id, candidate_id=interview.candidate_id,
            requested_date=payload.requested_date,
            requested_start_time=payload.requested_start_time,
            reason=payload.reason, status=ChangeRequestStatus.PENDING)
        self.db.add(request)
        self.db.flush()
        self.history.record(interview, HistoryAction.CHANGE_REQUESTED, {},
                            {"requested_date": str(payload.requested_date),
                             "requested_start_time": str(payload.requested_start_time)},
                            reason=payload.reason, user_id=scope.user.id)
        return self._change_request_dict(request)

    def list_change_requests(self, scope: Scope, *, status: str | None = None
                             ) -> list[dict[str, Any]]:
        query = self.db.query(InterviewChangeRequest)
        if scope.candidate_id is not None:
            query = query.filter(
                InterviewChangeRequest.candidate_id == scope.candidate_id)
        elif scope.faculty_id is not None:
            raise PermissionError_(
                "Reschedule requests are handled by the scheduling administrators.")
        if status:
            query = query.filter(InterviewChangeRequest.status == status.upper())
        rows = query.order_by(InterviewChangeRequest.id.desc()).all()
        return [self._change_request_dict(r) for r in rows]

    def decide_change_request(self, request_id: int, payload: ChangeRequestDecision,
                              user_id: int | None = None) -> dict[str, Any]:
        request = self.db.get(InterviewChangeRequest, request_id)
        if request is None:
            raise NotFoundError(f"Change request {request_id} was not found")
        if request.status != ChangeRequestStatus.PENDING:
            raise ValidationError(
                f"This request was already {request.status.value.lower()}.")
        if payload.approve:
            # Route through the normal reschedule so history, conflict detection
            # and free-slot recalculation behave exactly as an admin edit would.
            self.reschedule(
                request.interview_id,
                RescheduleRequest(
                    date=payload.date or request.requested_date,
                    start_time=payload.start_time or request.requested_start_time,
                    reason=f"Approved candidate request #{request.id}"),
                user_id)
        request.status = (ChangeRequestStatus.APPROVED if payload.approve
                          else ChangeRequestStatus.REJECTED)
        request.decision_note = payload.decision_note
        request.decided_by = user_id
        request.decided_at = datetime.now()
        self.db.flush()
        return self._change_request_dict(request)

    def _change_request_dict(self, request: InterviewChangeRequest) -> dict[str, Any]:
        candidate = request.candidate
        interview = request.interview
        return {
            "id": request.id,
            "interview_id": request.interview_id,
            "candidate_id": request.candidate_id,
            "requested_date": request.requested_date,
            "requested_start_time": request.requested_start_time,
            "reason": request.reason,
            "status": request.status,
            "decision_note": request.decision_note,
            "decided_by": request.decided_by,
            "decided_at": request.decided_at,
            "created_at": request.created_at,
            "candidate_name": candidate.candidate_name if candidate else None,
            "candidate_code": candidate.candidate_code if candidate else None,
            "current_date": interview.date if interview else None,
            "current_start_time": interview.start_time if interview else None,
        }

    # ----------------------------------------------------------------- helpers
    def _response(self, interview: Interview, warnings: list[str],
                  recalculated: int) -> dict[str, Any]:
        self.db.refresh(interview)
        return {"interview": interview, "warnings": warnings,
                "conflicts": [{"kind": "PLACEMENT", "message": w} for w in warnings],
                "free_slots_recalculated": recalculated}
