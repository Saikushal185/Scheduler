"""Concrete repositories with the queries each aggregate needs."""
from __future__ import annotations

from datetime import date
from typing import Sequence

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import selectinload

from app.models import (Candidate, Evaluation, EvaluationMetric, EvaluationScore,
                        Faculty, FacultyAvailability, FacultyBusySlot,
                        FacultyFreeSlot, Interview, InterviewPanelMember,
                        InterviewScheduleHistory, InterviewSettings, PanelGroup,
                        PanelMember, SchedulingConstraint, SchedulingRun,
                        UploadedFile, User)
from app.models.enums import InterviewStatus
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    def by_email(self, email: str) -> User | None:
        return self.get_by(email=email.lower().strip())


class CandidateRepository(BaseRepository[Candidate]):
    model = Candidate

    def by_code(self, code: str) -> Candidate | None:
        return self.get_by(candidate_code=code)

    def search(self, *, query: str | None = None, status: str | None = None,
               department: str | None = None, skip: int = 0,
               limit: int | None = 100) -> list[Candidate]:
        stmt = select(Candidate)
        if query:
            like = f"%{query.lower()}%"
            stmt = stmt.where(or_(func.lower(Candidate.candidate_name).like(like),
                                  func.lower(Candidate.candidate_code).like(like),
                                  func.lower(Candidate.email).like(like)))
        if status:
            stmt = stmt.where(Candidate.status == status)
        if department:
            stmt = stmt.where(Candidate.department == department)
        stmt = stmt.order_by(Candidate.candidate_code).offset(skip)
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def schedulable(self) -> list[Candidate]:
        stmt = select(Candidate).where(Candidate.is_active.is_(True)).order_by(
            Candidate.priority.desc(), Candidate.id)
        return list(self.db.execute(stmt).scalars().all())


class FacultyRepository(BaseRepository[Faculty]):
    model = Faculty

    def by_code(self, code: str) -> Faculty | None:
        return self.get_by(faculty_code=code)

    def active(self) -> list[Faculty]:
        return list(self.db.execute(
            select(Faculty).where(Faculty.is_active.is_(True))
            .order_by(Faculty.faculty_code)).scalars().all())

    def search(self, *, query: str | None = None, department: str | None = None,
               skip: int = 0, limit: int | None = 100) -> list[Faculty]:
        stmt = select(Faculty)
        if query:
            like = f"%{query.lower()}%"
            stmt = stmt.where(or_(func.lower(Faculty.faculty_name).like(like),
                                  func.lower(Faculty.faculty_code).like(like),
                                  func.lower(Faculty.email).like(like)))
        if department:
            stmt = stmt.where(Faculty.department == department)
        stmt = stmt.order_by(Faculty.faculty_code).offset(skip)
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def departments(self) -> list[str]:
        rows = self.db.execute(
            select(Faculty.department).where(Faculty.department.isnot(None)).distinct()
        ).scalars().all()
        return sorted(r for r in rows if r)


class AvailabilityRepository(BaseRepository[FacultyAvailability]):
    model = FacultyAvailability

    def for_faculty(self, faculty_id: int, *, start: date | None = None,
                    end: date | None = None) -> list[FacultyAvailability]:
        stmt = select(FacultyAvailability).where(
            FacultyAvailability.faculty_id == faculty_id)
        if start:
            stmt = stmt.where(FacultyAvailability.date >= start)
        if end:
            stmt = stmt.where(FacultyAvailability.date <= end)
        return list(self.db.execute(
            stmt.order_by(FacultyAvailability.date,
                          FacultyAvailability.start_time)).scalars().all())

    def in_range(self, start: date | None = None,
                 end: date | None = None) -> list[FacultyAvailability]:
        stmt = select(FacultyAvailability)
        if start:
            stmt = stmt.where(FacultyAvailability.date >= start)
        if end:
            stmt = stmt.where(FacultyAvailability.date <= end)
        return list(self.db.execute(
            stmt.order_by(FacultyAvailability.faculty_id,
                          FacultyAvailability.date)).scalars().all())


class BusySlotRepository(BaseRepository[FacultyBusySlot]):
    model = FacultyBusySlot

    def for_faculty(self, faculty_id: int, day: date | None = None
                    ) -> list[FacultyBusySlot]:
        stmt = select(FacultyBusySlot).where(FacultyBusySlot.faculty_id == faculty_id)
        if day:
            stmt = stmt.where(FacultyBusySlot.date == day)
        return list(self.db.execute(stmt).scalars().all())

    def in_range(self, start: date | None = None,
                 end: date | None = None) -> list[FacultyBusySlot]:
        stmt = select(FacultyBusySlot)
        if start:
            stmt = stmt.where(FacultyBusySlot.date >= start)
        if end:
            stmt = stmt.where(FacultyBusySlot.date <= end)
        return list(self.db.execute(stmt).scalars().all())

    def delete_for_interview(self, interview_id: int) -> None:
        for row in self.db.execute(
            select(FacultyBusySlot).where(
                FacultyBusySlot.interview_id == interview_id)).scalars().all():
            self.db.delete(row)
        self.db.flush()


class FreeSlotRepository(BaseRepository[FacultyFreeSlot]):
    model = FacultyFreeSlot

    def in_range(self, *, faculty_ids: Sequence[int] | None = None,
                 start: date | None = None,
                 end: date | None = None) -> list[FacultyFreeSlot]:
        stmt = select(FacultyFreeSlot)
        if faculty_ids:
            stmt = stmt.where(FacultyFreeSlot.faculty_id.in_(list(faculty_ids)))
        if start:
            stmt = stmt.where(FacultyFreeSlot.date >= start)
        if end:
            stmt = stmt.where(FacultyFreeSlot.date <= end)
        return list(self.db.execute(
            stmt.order_by(FacultyFreeSlot.faculty_id, FacultyFreeSlot.date,
                          FacultyFreeSlot.start_time)).scalars().all())

    def clear(self, *, faculty_ids: Sequence[int] | None = None,
              start: date | None = None, end: date | None = None) -> int:
        rows = self.in_range(faculty_ids=faculty_ids, start=start, end=end)
        for row in rows:
            self.db.delete(row)
        self.db.flush()
        return len(rows)


class PanelRepository(BaseRepository[PanelGroup]):
    model = PanelGroup

    def by_code(self, code: str) -> PanelGroup | None:
        return self.get_by(panel_code=code)

    def with_members(self) -> list[PanelGroup]:
        stmt = (select(PanelGroup)
                .options(selectinload(PanelGroup.members).selectinload(PanelMember.faculty))
                .order_by(PanelGroup.panel_code))
        return list(self.db.execute(stmt).scalars().unique().all())

    def active_with_members(self) -> list[PanelGroup]:
        return [p for p in self.with_members() if p.is_active]

    def panels_for_faculty(self, faculty_id: int) -> list[PanelGroup]:
        stmt = (select(PanelGroup).join(PanelMember)
                .where(PanelMember.faculty_id == faculty_id))
        return list(self.db.execute(stmt).scalars().unique().all())


class PanelMemberRepository(BaseRepository[PanelMember]):
    model = PanelMember

    def for_panel(self, panel_id: int) -> list[PanelMember]:
        return self.all(panel_id=panel_id)

    def clear_panel(self, panel_id: int) -> None:
        for row in self.all(panel_id=panel_id):
            self.db.delete(row)
        self.db.flush()


class InterviewRepository(BaseRepository[Interview]):
    model = Interview

    ACTIVE_STATUSES = (InterviewStatus.SCHEDULED, InterviewStatus.RESCHEDULED,
                       InterviewStatus.PENDING, InterviewStatus.CONFLICT,
                       InterviewStatus.COMPLETED)

    def _base(self):
        return select(Interview).options(
            selectinload(Interview.candidate),
            selectinload(Interview.panel).selectinload(PanelGroup.members),
            selectinload(Interview.panel_members).selectinload(
                InterviewPanelMember.faculty),
        )

    def get_full(self, interview_id: int) -> Interview | None:
        return self.db.execute(
            self._base().where(Interview.id == interview_id)).scalars().unique().first()

    def search(self, *, status: str | None = None, candidate_id: int | None = None,
               panel_id: int | None = None, faculty_id: int | None = None,
               department: str | None = None, start: date | None = None,
               end: date | None = None, run_id: int | None = None,
               skip: int = 0, limit: int | None = 200) -> list[Interview]:
        stmt = self._base()
        if status:
            stmt = stmt.where(Interview.status == status)
        if candidate_id:
            stmt = stmt.where(Interview.candidate_id == candidate_id)
        if panel_id:
            stmt = stmt.where(Interview.panel_id == panel_id)
        if run_id:
            stmt = stmt.where(Interview.run_id == run_id)
        if faculty_id:
            stmt = stmt.where(Interview.id.in_(
                select(InterviewPanelMember.interview_id).where(
                    InterviewPanelMember.faculty_id == faculty_id)))
        if department:
            stmt = stmt.where(Interview.candidate_id.in_(
                select(Candidate.id).where(Candidate.department == department)))
        if start:
            stmt = stmt.where(Interview.date >= start)
        if end:
            stmt = stmt.where(Interview.date <= end)
        stmt = stmt.order_by(Interview.date, Interview.start_time,
                             Interview.id).offset(skip)
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.db.execute(stmt).scalars().unique().all())

    def active(self, *, start: date | None = None,
               end: date | None = None) -> list[Interview]:
        stmt = self._base().where(Interview.status.in_(list(self.ACTIVE_STATUSES)),
                                  Interview.date.isnot(None))
        if start:
            stmt = stmt.where(Interview.date >= start)
        if end:
            stmt = stmt.where(Interview.date <= end)
        return list(self.db.execute(stmt).scalars().unique().all())

    def locked(self) -> list[Interview]:
        stmt = self._base().where(Interview.is_locked.is_(True),
                                  Interview.status.in_(list(self.ACTIVE_STATUSES)))
        return list(self.db.execute(stmt).scalars().unique().all())

    def count_by_status(self) -> dict[str, int]:
        rows = self.db.execute(
            select(Interview.status, func.count()).group_by(Interview.status)).all()
        return {str(status): int(count) for status, count in rows}

    def upcoming(self, today: date, limit: int = 10) -> list[Interview]:
        stmt = (self._base()
                .where(Interview.date >= today,
                       Interview.status.in_([InterviewStatus.SCHEDULED,
                                             InterviewStatus.RESCHEDULED,
                                             InterviewStatus.PENDING]))
                .order_by(Interview.date, Interview.start_time).limit(limit))
        return list(self.db.execute(stmt).scalars().unique().all())

    def delete_unlocked_scheduled(self) -> int:
        rows = self.db.execute(
            select(Interview).where(Interview.is_locked.is_(False))).scalars().all()
        removed = 0
        for row in rows:
            if row.status in (InterviewStatus.COMPLETED, InterviewStatus.CANCELLED):
                continue
            self.db.delete(row)
            removed += 1
        self.db.flush()
        return removed


class InterviewMemberRepository(BaseRepository[InterviewPanelMember]):
    model = InterviewPanelMember

    def clear(self, interview_id: int) -> None:
        for row in self.all(interview_id=interview_id):
            self.db.delete(row)
        self.db.flush()

    def workload(self) -> list[tuple[int, int]]:
        rows = self.db.execute(
            select(InterviewPanelMember.faculty_id, func.count())
            .join(Interview, Interview.id == InterviewPanelMember.interview_id)
            .where(Interview.status.in_([InterviewStatus.SCHEDULED,
                                         InterviewStatus.RESCHEDULED,
                                         InterviewStatus.COMPLETED]))
            .group_by(InterviewPanelMember.faculty_id)).all()
        return [(int(fid), int(count)) for fid, count in rows]


class HistoryRepository(BaseRepository[InterviewScheduleHistory]):
    model = InterviewScheduleHistory

    def recent(self, limit: int = 20) -> list[InterviewScheduleHistory]:
        stmt = (select(InterviewScheduleHistory)
                .order_by(InterviewScheduleHistory.id.desc()).limit(limit))
        return list(self.db.execute(stmt).scalars().all())

    def for_interview(self, interview_id: int) -> list[InterviewScheduleHistory]:
        stmt = (select(InterviewScheduleHistory)
                .where(InterviewScheduleHistory.interview_id == interview_id)
                .order_by(InterviewScheduleHistory.id.desc()))
        return list(self.db.execute(stmt).scalars().all())


class RunRepository(BaseRepository[SchedulingRun]):
    model = SchedulingRun

    def latest(self, limit: int = 10) -> list[SchedulingRun]:
        stmt = select(SchedulingRun).order_by(SchedulingRun.id.desc()).limit(limit)
        return list(self.db.execute(stmt).scalars().all())


class MetricRepository(BaseRepository[EvaluationMetric]):
    model = EvaluationMetric

    def active(self) -> list[EvaluationMetric]:
        stmt = (select(EvaluationMetric).where(EvaluationMetric.is_active.is_(True))
                .order_by(EvaluationMetric.display_order, EvaluationMetric.id))
        return list(self.db.execute(stmt).scalars().all())

    def ordered(self) -> list[EvaluationMetric]:
        stmt = select(EvaluationMetric).order_by(EvaluationMetric.display_order,
                                                 EvaluationMetric.id)
        return list(self.db.execute(stmt).scalars().all())

    def by_key(self, key: str) -> EvaluationMetric | None:
        return self.get_by(metric_key=key)


class EvaluationRepository(BaseRepository[Evaluation]):
    model = Evaluation

    def _base(self):
        return select(Evaluation).options(
            selectinload(Evaluation.candidate),
            selectinload(Evaluation.scores).selectinload(EvaluationScore.metric),
            selectinload(Evaluation.panel), selectinload(Evaluation.evaluator))

    def get_full(self, evaluation_id: int) -> Evaluation | None:
        return self.db.execute(
            self._base().where(Evaluation.id == evaluation_id)).scalars().unique().first()

    def all_full(self, *, candidate_id: int | None = None, panel_id: int | None = None,
                 skip: int = 0, limit: int | None = None) -> list[Evaluation]:
        stmt = self._base()
        if candidate_id:
            stmt = stmt.where(Evaluation.candidate_id == candidate_id)
        if panel_id:
            stmt = stmt.where(Evaluation.panel_id == panel_id)
        stmt = stmt.order_by(Evaluation.overall_score.desc(), Evaluation.id).offset(skip)
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.db.execute(stmt).scalars().unique().all())

    def for_candidate_interview(self, candidate_id: int, interview_id: int | None,
                                evaluator_id: int | None) -> Evaluation | None:
        stmt = select(Evaluation).where(
            Evaluation.candidate_id == candidate_id,
            Evaluation.interview_id.is_(None) if interview_id is None
            else Evaluation.interview_id == interview_id,
            Evaluation.evaluator_faculty_id.is_(None) if evaluator_id is None
            else Evaluation.evaluator_faculty_id == evaluator_id)
        return self.db.execute(stmt).scalars().first()


class ScoreRepository(BaseRepository[EvaluationScore]):
    model = EvaluationScore

    def clear(self, evaluation_id: int) -> None:
        for row in self.all(evaluation_id=evaluation_id):
            self.db.delete(row)
        self.db.flush()

    def metric_averages(self) -> list[tuple[int, float, int]]:
        rows = self.db.execute(
            select(EvaluationScore.metric_id, func.avg(EvaluationScore.raw_score),
                   func.count()).group_by(EvaluationScore.metric_id)).all()
        return [(int(mid), float(avg or 0), int(count)) for mid, avg, count in rows]


class ConstraintRepository(BaseRepository[SchedulingConstraint]):
    model = SchedulingConstraint

    def active(self) -> list[SchedulingConstraint]:
        stmt = (select(SchedulingConstraint)
                .where(SchedulingConstraint.is_active.is_(True))
                .order_by(SchedulingConstraint.display_order, SchedulingConstraint.id))
        return list(self.db.execute(stmt).scalars().all())

    def ordered(self) -> list[SchedulingConstraint]:
        stmt = select(SchedulingConstraint).order_by(
            SchedulingConstraint.display_order, SchedulingConstraint.id)
        return list(self.db.execute(stmt).scalars().all())


class UploadRepository(BaseRepository[UploadedFile]):
    model = UploadedFile

    def recent(self, limit: int = 25) -> list[UploadedFile]:
        stmt = select(UploadedFile).order_by(UploadedFile.id.desc()).limit(limit)
        return list(self.db.execute(stmt).scalars().all())


class SettingsRepository(BaseRepository[InterviewSettings]):
    model = InterviewSettings

    def singleton(self) -> InterviewSettings | None:
        return self.db.get(InterviewSettings, 1)
