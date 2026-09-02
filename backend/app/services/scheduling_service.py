"""Bridge between the database and the (database-free) scheduling engine.

    build context -> run engine -> persist a PREVIEW run
                                -> confirm -> interviews + history + free slots
"""
from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Sequence

from sqlalchemy.orm import Session

from app.core.config import settings as app_settings
from app.core.exceptions import NotFoundError, SchedulingError
from app.core.logging_config import get_logger
from app.models import Interview, InterviewPanelMember, SchedulingRun
from app.models.enums import (CandidateStatus, ConstraintPriority, ConstraintType,
                              HistoryAction, InterviewStatus, ScheduleRunStatus)
from app.repositories import (CandidateRepository, ConstraintRepository,
                              FacultyRepository, InterviewMemberRepository,
                              InterviewRepository, PanelRepository, RunRepository)
from app.scheduling import (CandidateSpec, ConstraintSpec, ExistingBooking,
                            FacultySpec, PanelSpec, SchedulingContext,
                            SchedulingEngine, SchedulingOptions, SchedulingResult)
from app.schemas.scheduling import GenerateScheduleRequest
from app.services.free_slot_service import FreeSlotService
from app.services.history_service import HistoryService
from app.services.settings_service import SettingsService
from app.utils.timeutils import Interval, date_range, parse_date, parse_time

logger = get_logger(__name__)

DEFAULT_CONSTRAINTS: tuple[dict[str, Any], ...] = (
    {"name": "Candidate must be available", "type": ConstraintType.CANDIDATE_UNAVAILABLE,
     "priority": ConstraintPriority.HARD,
     "description": "An interview may only be placed inside the candidate's "
                    "declared availability."},
    {"name": "Faculty must be free", "type": ConstraintType.FACULTY_UNAVAILABLE,
     "priority": ConstraintPriority.HARD,
     "description": "Assigned faculty must have a free slot covering the interview."},
    {"name": "Panel must reach its minimum size",
     "type": ConstraintType.PANEL_SIZE, "priority": ConstraintPriority.HARD,
     "description": "Every interview needs the configured number of panel members."},
    {"name": "Respect the break between interviews",
     "type": ConstraintType.BREAK_BETWEEN_INTERVIEWS, "priority": ConstraintPriority.HARD,
     "description": "Faculty get the configured break between two interviews."},
    {"name": "Candidate preferred date",
     "type": ConstraintType.CANDIDATE_PREFERRED_DATE, "priority": ConstraintPriority.HIGH,
     "parameters": {"tolerance_days": 5},
     "description": "Schedule on the requested date when possible."},
    {"name": "Candidate preferred time",
     "type": ConstraintType.CANDIDATE_PREFERRED_TIME,
     "priority": ConstraintPriority.MEDIUM, "parameters": {"tolerance_minutes": 120},
     "description": "Start close to the requested time."},
    {"name": "Preferred panel", "type": ConstraintType.PREFERRED_PANEL,
     "priority": ConstraintPriority.LOW,
     "description": "Use the requested panel when it is available."},
    {"name": "Match candidate department", "type": ConstraintType.DEPARTMENT_MATCH,
     "priority": ConstraintPriority.LOW,
     "description": "Prefer a panel from the candidate's department."},
    {"name": "Keep the schedule compact", "type": ConstraintType.EARLIEST_SLOT,
     "priority": ConstraintPriority.FLEXIBLE,
     "description": "Prefer earlier days and earlier slots."},
    {"name": "Balance faculty workload", "type": ConstraintType.LOAD_BALANCE,
     "priority": ConstraintPriority.FLEXIBLE, "parameters": {"target_max": 8},
     "description": "Spread interviews across the available faculty."},
    {"name": "Faculty daily interview cap",
     "type": ConstraintType.MAX_INTERVIEWS_PER_FACULTY, "priority": ConstraintPriority.HARD,
     "description": "Never exceed the configured interviews per faculty per day."},
)


class SchedulingService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.candidates = CandidateRepository(db)
        self.faculty = FacultyRepository(db)
        self.panels = PanelRepository(db)
        self.interviews = InterviewRepository(db)
        self.members = InterviewMemberRepository(db)
        self.constraints = ConstraintRepository(db)
        self.runs = RunRepository(db)
        self.settings = SettingsService(db)
        self.free_slots = FreeSlotService(db)
        self.history = HistoryService(db)

    # ------------------------------------------------------------- constraints
    def ensure_constraints(self) -> list:
        rows = self.constraints.ordered()
        if rows:
            return rows
        for order, item in enumerate(DEFAULT_CONSTRAINTS):
            self.constraints.create(
                name=item["name"], constraint_type=item["type"],
                priority=item["priority"], description=item.get("description"),
                parameters=item.get("parameters", {}), display_order=order)
        self.db.flush()
        logger.info("Seeded %s default scheduling constraints", len(DEFAULT_CONSTRAINTS))
        return self.constraints.ordered()

    # ----------------------------------------------------------------- context
    def resolve_dates(self, request: GenerateScheduleRequest) -> list[date]:
        config = self.settings.get()
        start = request.start_date or config.schedule_start_date
        end = request.end_date or config.schedule_end_date
        if not start or not end:
            days = sorted({row.date for row in
                           FreeSlotService(self.db).free_repo.in_range()})
            if days:
                start = start or days[0]
                end = end or days[-1]
        if not start:
            start = date.today()
        if not end:
            end = start + timedelta(days=6)
        allow_weekends = (request.allow_weekends if request.allow_weekends is not None
                          else config.allow_weekends)
        return date_range(start, end, include_weekends=allow_weekends)

    def build_context(self, request: GenerateScheduleRequest) -> SchedulingContext:
        config = self.settings.get()
        self.ensure_constraints()
        dates = self.resolve_dates(request)
        if not dates:
            raise SchedulingError(
                "The scheduling window is empty. Set a date range in Settings or "
                "pass start_date/end_date.")

        # Free slots are derived data - refresh them before reading.
        self.free_slots.recalculate(start=dates[0], end=dates[-1])

        options = SchedulingOptions(
            dates=dates,
            duration_minutes=(request.interview_duration_minutes
                              or config.interview_duration_minutes),
            break_minutes=(request.break_duration_minutes
                           if request.break_duration_minutes is not None
                           else config.break_duration_minutes),
            granularity_minutes=(request.slot_granularity_minutes
                                 or config.slot_granularity_minutes),
            day_start=request.day_start_time or config.day_start_time,
            day_end=request.day_end_time or config.day_end_time,
            max_interviews_per_faculty_per_day=(
                request.max_interviews_per_faculty_per_day
                or config.max_interviews_per_faculty_per_day),
            algorithm=request.algorithm or config.default_algorithm,
            allow_weekends=(request.allow_weekends if request.allow_weekends is not None
                            else config.allow_weekends),
            priority_weights=dict(app_settings.PRIORITY_WEIGHTS),
        )

        free_map = self.free_slots.load_free_map(start=dates[0], end=dates[-1])
        faculty_specs: dict[int, FacultySpec] = {}
        for member in self.faculty.active():
            faculty_specs[member.id] = FacultySpec(
                id=member.id, code=member.faculty_code, name=member.faculty_name,
                department=member.department,
                max_per_day=member.max_interviews_per_day,
                free_slots={day: list(slots) for day, slots
                            in free_map.get(member.id, {}).items()})

        panel_specs: list[PanelSpec] = []
        wanted_panels = set(request.panel_ids or [])
        for panel in self.panels.active_with_members():
            if wanted_panels and panel.id not in wanted_panels:
                continue
            member_ids = [m.faculty_id for m in panel.members
                          if m.faculty_id in faculty_specs]
            if not member_ids:
                continue
            panel_specs.append(PanelSpec(
                id=panel.id, code=panel.panel_code, name=panel.panel_name,
                member_ids=member_ids,
                mandatory_ids={m.faculty_id for m in panel.members if m.is_mandatory},
                department=panel.department,
                minimum_panel_size=max(1, min(panel.minimum_panel_size,
                                              len(member_ids))),
                maximum_panel_size=max(panel.minimum_panel_size,
                                       panel.maximum_panel_size)))

        existing: list[ExistingBooking] = []
        excluded_candidates: set[int] = set()
        if request.keep_locked_interviews:
            for interview in self.interviews.locked():
                if not (interview.date and interview.start_time and interview.end_time):
                    continue
                existing.append(ExistingBooking(
                    interview_id=interview.id, candidate_id=interview.candidate_id,
                    panel_id=interview.panel_id,
                    faculty_ids=[m.faculty_id for m in interview.panel_members],
                    day=interview.date,
                    slot=Interval.from_times(interview.start_time, interview.end_time)))
                excluded_candidates.add(interview.candidate_id)
        for interview in self.interviews.search(status=InterviewStatus.COMPLETED,
                                                limit=None):
            excluded_candidates.add(interview.candidate_id)
            if interview.date and interview.start_time and interview.end_time:
                existing.append(ExistingBooking(
                    interview_id=interview.id, candidate_id=interview.candidate_id,
                    panel_id=interview.panel_id,
                    faculty_ids=[m.faculty_id for m in interview.panel_members],
                    day=interview.date,
                    slot=Interval.from_times(interview.start_time, interview.end_time)))

        wanted_candidates = set(request.candidate_ids or [])
        candidate_specs: list[CandidateSpec] = []
        for candidate in self.candidates.schedulable():
            if wanted_candidates and candidate.id not in wanted_candidates:
                continue
            if candidate.id in excluded_candidates:
                continue
            availability: dict[date, list[Interval]] = defaultdict(list)
            for window in candidate.availability or []:
                day = parse_date(window.get("date"))
                start = parse_time(window.get("start_time"))
                end = parse_time(window.get("end_time"))
                if day and start and end and end > start:
                    availability[day].append(Interval.from_times(start, end))
            candidate_specs.append(CandidateSpec(
                id=candidate.id, code=candidate.candidate_code,
                name=candidate.candidate_name, department=candidate.department,
                preferred_date=candidate.preferred_date,
                preferred_time=candidate.preferred_time,
                preferred_panel_code=candidate.preferred_panel_code,
                availability=dict(availability),
                required_panel_code=(candidate.constraints or {}).get("required_panel"),
                priority=candidate.priority or 0))

        constraint_specs = [
            ConstraintSpec(id=row.id, name=row.name, constraint_type=row.constraint_type,
                           priority=row.priority, scope=row.scope or {},
                           parameters=row.parameters or {},
                           weight_multiplier=row.weight_multiplier)
            for row in self.constraints.active()]

        return SchedulingContext(
            candidates=candidate_specs, faculty=faculty_specs, panels=panel_specs,
            constraints=constraint_specs, options=options, existing=existing)

    # ------------------------------------------------------------------ preview
    def generate_preview(self, request: GenerateScheduleRequest,
                         user_id: int | None = None) -> dict[str, Any]:
        ctx = self.build_context(request)
        if not ctx.panels:
            raise SchedulingError("No active panel group has available faculty members. "
                                  "Create a panel before scheduling.")
        if not ctx.candidates:
            raise SchedulingError("There are no candidates left to schedule.")

        engine = SchedulingEngine(ctx.options.algorithm)
        result = engine.run(ctx)

        run = self.runs.create(
            run_code=f"RUN-{uuid.uuid4().hex[:8].upper()}",
            algorithm=result.algorithm, status=ScheduleRunStatus.PREVIEW,
            parameters={**request.model_dump(mode="json"),
                        "dates": [d.isoformat() for d in ctx.options.dates],
                        "duration_minutes": ctx.options.duration_minutes,
                        "break_minutes": ctx.options.break_minutes},
            result=result.to_dict(),
            total_candidates=len(ctx.candidates),
            scheduled_count=result.scheduled_count,
            unscheduled_count=len(result.unscheduled),
            total_score=result.total_score, duration_ms=result.duration_ms,
            created_by=user_id)
        self.db.flush()
        return self.serialise_preview(run, result, ctx)

    def serialise_preview(self, run: SchedulingRun, result: SchedulingResult,
                          ctx: SchedulingContext) -> dict[str, Any]:
        candidates = {c.id: c for c in ctx.candidates}
        panels = {p.id: p for p in ctx.panels}
        faculty = ctx.faculty
        scheduled = []
        for assignment in result.assignments:
            candidate = candidates.get(assignment.candidate_id)
            panel = panels.get(assignment.panel_id)
            scheduled.append({
                "candidate_id": assignment.candidate_id,
                "candidate_code": candidate.code if candidate else "",
                "candidate_name": candidate.name if candidate else "",
                "panel_id": assignment.panel_id,
                "panel_code": panel.code if panel else "",
                "panel_name": panel.name if panel else "",
                "faculty_ids": assignment.faculty_ids,
                "faculty_names": [faculty[f].name for f in assignment.faculty_ids
                                  if f in faculty],
                "date": assignment.day,
                "start_time": assignment.slot.start_time,
                "end_time": assignment.slot.end_time,
                "scheduling_score": round(assignment.score, 3),
                "priority_info": [o.to_dict() for o in assignment.outcomes],
            })
        unscheduled = []
        for item in result.unscheduled:
            candidate = candidates.get(item.candidate_id)
            unscheduled.append({
                "candidate_id": item.candidate_id,
                "candidate_code": candidate.code if candidate else "",
                "candidate_name": candidate.name if candidate else "",
                "reason": item.reason, "details": item.details})
        return {
            "run_id": run.id, "run_code": run.run_code, "algorithm": result.algorithm,
            "status": run.status, "scheduled": scheduled, "unscheduled": unscheduled,
            "conflicts": [c.to_dict() for c in result.conflicts],
            "total_score": round(result.total_score, 3),
            "success_rate": result.success_rate, "duration_ms": result.duration_ms,
            "statistics": result.statistics, "parameters": run.parameters,
        }

    def get_preview(self, run_id: int) -> dict[str, Any]:
        run = self.runs.get(run_id)
        if run is None:
            raise NotFoundError(f"Scheduling run {run_id} was not found")
        stored = run.result or {}
        candidates = {c.id: c for c in self.candidates.all()}
        panels = {p.id: p for p in self.panels.all()}
        faculty = {f.id: f for f in self.faculty.all()}
        scheduled = []
        for item in stored.get("assignments", []):
            candidate = candidates.get(item["candidate_id"])
            panel = panels.get(item["panel_id"])
            scheduled.append({
                "candidate_id": item["candidate_id"],
                "candidate_code": candidate.candidate_code if candidate else "",
                "candidate_name": candidate.candidate_name if candidate else "",
                "panel_id": item["panel_id"],
                "panel_code": panel.panel_code if panel else "",
                "panel_name": panel.panel_name if panel else "",
                "faculty_ids": item["faculty_ids"],
                "faculty_names": [faculty[f].faculty_name for f in item["faculty_ids"]
                                  if f in faculty],
                "date": parse_date(item["date"]),
                "start_time": parse_time(item["start_time"]),
                "end_time": parse_time(item["end_time"]),
                "scheduling_score": item["score"],
                "priority_info": item.get("priority_info", []),
            })
        unscheduled = []
        for item in stored.get("unscheduled", []):
            candidate = candidates.get(item["candidate_id"])
            unscheduled.append({
                "candidate_id": item["candidate_id"],
                "candidate_code": candidate.candidate_code if candidate else "",
                "candidate_name": candidate.candidate_name if candidate else "",
                "reason": item["reason"], "details": item.get("details", [])})
        return {
            "run_id": run.id, "run_code": run.run_code, "algorithm": run.algorithm,
            "status": run.status, "scheduled": scheduled, "unscheduled": unscheduled,
            "conflicts": stored.get("conflicts", []),
            "total_score": run.total_score,
            "success_rate": stored.get("success_rate", 0.0),
            "duration_ms": run.duration_ms,
            "statistics": stored.get("statistics", {}), "parameters": run.parameters,
        }

    # ------------------------------------------------------------------ confirm
    def confirm(self, run_id: int, *, replace_existing: bool = True,
                user_id: int | None = None) -> dict[str, Any]:
        run = self.runs.get(run_id)
        if run is None:
            raise NotFoundError(f"Scheduling run {run_id} was not found")
        if run.status == ScheduleRunStatus.CONFIRMED:
            raise SchedulingError(f"Run {run.run_code} has already been confirmed")
        if run.status == ScheduleRunStatus.DISCARDED:
            raise SchedulingError(f"Run {run.run_code} was discarded")

        assignments = (run.result or {}).get("assignments", [])
        replaced = self.interviews.delete_unlocked_scheduled() if replace_existing else 0

        created = 0
        for item in assignments:
            day = parse_date(item["date"])
            start = parse_time(item["start_time"])
            end = parse_time(item["end_time"])
            if not (day and start and end):
                continue
            interview = self.interviews.create(
                schedule_code=f"INT-{uuid.uuid4().hex[:8].upper()}",
                candidate_id=item["candidate_id"], panel_id=item["panel_id"],
                run_id=run.id, date=day, start_time=start, end_time=end,
                duration_minutes=Interval.from_times(start, end).duration,
                status=InterviewStatus.SCHEDULED,
                scheduling_score=item.get("score", 0.0),
                priority_info=item.get("priority_info", []))
            for faculty_id in item["faculty_ids"]:
                self.members.create(interview_id=interview.id, faculty_id=faculty_id)
            self.history.record(interview, HistoryAction.AUTO_SCHEDULED, {},
                                self.history.snapshot(interview),
                                reason=f"Generated by run {run.run_code}",
                                user_id=user_id)
            created += 1

        scheduled_ids = {item["candidate_id"] for item in assignments}
        for candidate in self.candidates.all():
            if candidate.id in scheduled_ids:
                candidate.status = CandidateStatus.SCHEDULED
            elif candidate.status == CandidateStatus.SCHEDULED:
                candidate.status = CandidateStatus.PENDING
        for item in (run.result or {}).get("unscheduled", []):
            candidate = self.candidates.get(item["candidate_id"])
            if candidate and candidate.status != CandidateStatus.COMPLETED:
                candidate.status = CandidateStatus.UNSCHEDULED

        run.status = ScheduleRunStatus.CONFIRMED
        self.db.flush()
        stats = self.free_slots.recalculate()
        logger.info("Confirmed run %s: %s interview(s) created, %s replaced",
                    run.run_code, created, replaced)
        return {"run_id": run.id, "interviews_created": created,
                "interviews_replaced": replaced,
                "free_slots_recalculated": stats["slots_created"],
                "conflicts": (run.result or {}).get("conflicts", [])}

    def discard(self, run_id: int) -> SchedulingRun:
        run = self.runs.get(run_id)
        if run is None:
            raise NotFoundError(f"Scheduling run {run_id} was not found")
        if run.status == ScheduleRunStatus.CONFIRMED:
            raise SchedulingError("A confirmed run cannot be discarded")
        run.status = ScheduleRunStatus.DISCARDED
        self.db.flush()
        return run

    def generate_and_confirm(self, request: GenerateScheduleRequest,
                             user_id: int | None = None) -> dict[str, Any]:
        preview = self.generate_preview(request, user_id)
        confirmation = self.confirm(preview["run_id"],
                                    replace_existing=request.replace_existing,
                                    user_id=user_id)
        return {**preview, **confirmation}
