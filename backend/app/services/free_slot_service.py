"""Faculty free-slot calculation.

    free slots = declared availability - (busy slots + booked interviews)

Free slots are a derived table.  They are recalculated whenever availability
changes or an interview is scheduled, rescheduled or cancelled, so the
scheduling engine always reads an up-to-date picture.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Iterable, Sequence

from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.models import FacultyFreeSlot
from app.models.enums import AvailabilityStatus, BusySlotSource, InterviewStatus
from app.repositories import (AvailabilityRepository, BusySlotRepository,
                              FacultyRepository, FreeSlotRepository,
                              InterviewRepository)
from app.utils.timeutils import (Interval, merge_intervals,
                                 subtract_intervals)

logger = get_logger(__name__)


class FreeSlotService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.faculty_repo = FacultyRepository(db)
        self.availability_repo = AvailabilityRepository(db)
        self.busy_repo = BusySlotRepository(db)
        self.free_repo = FreeSlotRepository(db)
        self.interview_repo = InterviewRepository(db)

    # ------------------------------------------------------------------ syncing
    def sync_interview_busy_slots(self) -> int:
        """Mirror every booked interview into `faculty_busy_slots`.

        Cancelled interviews lose their busy rows, which is what makes a
        cancellation free the faculty up again.
        """
        existing = {(row.interview_id, row.faculty_id): row
                    for row in self.busy_repo.all()
                    if row.interview_id is not None}
        wanted: set[tuple[int, int]] = set()
        created = 0
        for interview in self.interview_repo.search(limit=None):
            active = (interview.status in (InterviewStatus.SCHEDULED,
                                           InterviewStatus.RESCHEDULED,
                                           InterviewStatus.PENDING,
                                           InterviewStatus.CONFLICT,
                                           InterviewStatus.COMPLETED)
                      and interview.date and interview.start_time and interview.end_time)
            if not active:
                continue
            for member in interview.panel_members:
                key = (interview.id, member.faculty_id)
                wanted.add(key)
                row = existing.get(key)
                if row is None:
                    self.busy_repo.create(
                        faculty_id=member.faculty_id, date=interview.date,
                        start_time=interview.start_time, end_time=interview.end_time,
                        source=BusySlotSource.INTERVIEW, interview_id=interview.id,
                        reason=f"Interview {interview.schedule_code}")
                    created += 1
                else:
                    row.date = interview.date
                    row.start_time = interview.start_time
                    row.end_time = interview.end_time
        for key, row in existing.items():
            if key not in wanted:
                self.db.delete(row)
        self.db.flush()
        return created

    # ------------------------------------------------------------ recalculation
    def recalculate(self, *, faculty_ids: Sequence[int] | None = None,
                    start: date | None = None, end: date | None = None,
                    sync_interviews: bool = True) -> dict[str, int]:
        if sync_interviews:
            self.sync_interview_busy_slots()

        targets = (list(faculty_ids) if faculty_ids
                   else [f.id for f in self.faculty_repo.active()])
        if not targets:
            return {"faculty_processed": 0, "slots_created": 0, "slots_removed": 0}

        removed = self.free_repo.clear(faculty_ids=targets, start=start, end=end)

        availability = defaultdict(list)
        for row in self.availability_repo.in_range(start, end):
            if row.faculty_id in set(targets):
                availability[(row.faculty_id, row.date)].append(row)

        busy = defaultdict(list)
        for row in self.busy_repo.in_range(start, end):
            if row.faculty_id in set(targets):
                busy[(row.faculty_id, row.date)].append(row)

        created = 0
        new_rows: list[FacultyFreeSlot] = []
        for (faculty_id, day), rows in availability.items():
            windows = [Interval.from_times(r.start_time, r.end_time) for r in rows
                       if r.availability_status == AvailabilityStatus.AVAILABLE]
            if not windows:
                continue
            blocks = [Interval.from_times(r.start_time, r.end_time) for r in rows
                      if r.availability_status == AvailabilityStatus.UNAVAILABLE]
            blocks += [Interval.from_times(r.start_time, r.end_time)
                       for r in busy.get((faculty_id, day), ())]
            for free in subtract_intervals(windows, blocks):
                new_rows.append(FacultyFreeSlot(
                    faculty_id=faculty_id, date=day,
                    start_time=free.start_time, end_time=free.end_time,
                    duration_minutes=free.duration))
                created += 1
        if new_rows:
            self.free_repo.bulk_add(new_rows)
        logger.info("Recalculated free slots for %s faculty: -%s +%s rows",
                    len(targets), removed, created)
        return {"faculty_processed": len(targets), "slots_created": created,
                "slots_removed": removed}

    def recalculate_for_faculty(self, faculty_ids: Iterable[int]) -> dict[str, int]:
        ids = sorted(set(faculty_ids))
        return self.recalculate(faculty_ids=ids) if ids else {
            "faculty_processed": 0, "slots_created": 0, "slots_removed": 0}

    # ------------------------------------------------------------------ queries
    def load_free_map(self, *, faculty_ids: Sequence[int] | None = None,
                      start: date | None = None,
                      end: date | None = None) -> dict[int, dict[date, list[Interval]]]:
        """faculty_id -> date -> free intervals (used by the scheduling engine)."""
        result: dict[int, dict[date, list[Interval]]] = defaultdict(lambda: defaultdict(list))
        for row in self.free_repo.in_range(faculty_ids=faculty_ids, start=start, end=end):
            result[row.faculty_id][row.date].append(
                Interval.from_times(row.start_time, row.end_time))
        return {fid: dict(days) for fid, days in result.items()}

    def grouped(self, *, faculty_ids: Sequence[int] | None = None,
                start: date | None = None, end: date | None = None) -> list[dict]:
        rows = self.free_repo.in_range(faculty_ids=faculty_ids, start=start, end=end)
        faculty = {f.id: f for f in self.faculty_repo.all()}
        buckets: dict[tuple[int, date], list] = defaultdict(list)
        for row in rows:
            buckets[(row.faculty_id, row.date)].append(row)
        groups = []
        for (faculty_id, day), slots in sorted(buckets.items(),
                                               key=lambda kv: (kv[0][1], kv[0][0])):
            member = faculty.get(faculty_id)
            if member is None:
                continue
            groups.append({
                "faculty_id": faculty_id,
                "faculty_code": member.faculty_code,
                "faculty_name": member.faculty_name,
                "department": member.department,
                "date": day,
                "slots": sorted(slots, key=lambda s: s.start_time),
                "total_free_minutes": sum(s.duration_minutes for s in slots),
            })
        return groups

    # ----------------------------------------------------------------- timeline
    def timeline(self, *, faculty_ids: Sequence[int] | None = None,
                 start: date | None = None, end: date | None = None) -> list[dict]:
        """A day's diary per faculty member as coloured, non-overlapping segments.

        Four kinds, because "not free" means two very different things to the
        person reading the calendar:

            BOOKED      an interview (busy slot with source=INTERVIEW)
            BUSY        declared unavailable / manually blocked / imported
            FREE        calculated free time
            UNAVAILABLE outside any declared availability window

        Derived from the same three tables `recalculate()` reads, so the picture
        can never disagree with the free slots the scheduler consumes.
        """
        targets = set(faculty_ids) if faculty_ids else None
        faculty = {f.id: f for f in self.faculty_repo.all()}

        availability: dict[tuple[int, date], list] = defaultdict(list)
        for row in self.availability_repo.in_range(start, end):
            if targets is None or row.faculty_id in targets:
                availability[(row.faculty_id, row.date)].append(row)

        busy: dict[tuple[int, date], list] = defaultdict(list)
        for row in self.busy_repo.in_range(start, end):
            if targets is None or row.faculty_id in targets:
                busy[(row.faculty_id, row.date)].append(row)

        interviews = {i.id: i for i in self.interview_repo.search(
            start=start, end=end, limit=None)}

        keys = sorted(set(availability) | set(busy), key=lambda k: (k[1], k[0]))
        days: list[dict] = []
        for faculty_id, day in keys:
            member = faculty.get(faculty_id)
            if member is None:
                continue
            declared = [Interval.from_times(r.start_time, r.end_time)
                        for r in availability.get((faculty_id, day), ())
                        if r.availability_status == AvailabilityStatus.AVAILABLE]

            segments: list[dict] = []
            blocks: list[Interval] = []
            # Declared-unavailable windows read as BUSY.
            for row in availability.get((faculty_id, day), ()):
                if row.availability_status == AvailabilityStatus.AVAILABLE:
                    continue
                interval = Interval.from_times(row.start_time, row.end_time)
                blocks.append(interval)
                segments.append(self._segment("BUSY", interval,
                                              label="Marked unavailable"))
            for row in busy.get((faculty_id, day), ()):
                interval = Interval.from_times(row.start_time, row.end_time)
                blocks.append(interval)
                if row.source == BusySlotSource.INTERVIEW:
                    interview = interviews.get(row.interview_id)
                    candidate = interview.candidate if interview else None
                    segments.append(self._segment(
                        "BOOKED", interval,
                        label=(candidate.candidate_name if candidate
                               else (row.reason or "Interview")),
                        interview_id=row.interview_id,
                        schedule_code=interview.schedule_code if interview else None,
                        status=interview.status.value if interview else None))
                else:
                    segments.append(self._segment(
                        "BUSY", interval,
                        label=row.reason or row.source.value.title()))

            for free in subtract_intervals(declared, blocks):
                segments.append(self._segment("FREE", free, label="Free"))

            segments.sort(key=lambda s: s["start_minute"])
            booked = sum(s["duration_minutes"] for s in segments
                         if s["kind"] == "BOOKED")
            busy_minutes = sum(s["duration_minutes"] for s in segments
                               if s["kind"] == "BUSY")
            free_minutes = sum(s["duration_minutes"] for s in segments
                               if s["kind"] == "FREE")
            days.append({
                "faculty_id": faculty_id,
                "faculty_code": member.faculty_code,
                "faculty_name": member.faculty_name,
                "department": member.department,
                "date": day,
                "segments": segments,
                "booked_minutes": booked,
                "busy_minutes": busy_minutes,
                "free_minutes": free_minutes,
                "declared_minutes": sum(i.duration for i in merge_intervals(declared)),
            })
        return days

    @staticmethod
    def _segment(kind: str, interval: Interval, *, label: str = "",
                 **extra) -> dict:
        return {
            "kind": kind,
            "start_time": interval.start_time,
            "end_time": interval.end_time,
            "start_minute": interval.start,
            "end_minute": interval.end,
            "duration_minutes": interval.duration,
            "label": label,
            **extra,
        }
