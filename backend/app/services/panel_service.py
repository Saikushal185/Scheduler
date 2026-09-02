"""Panel group management: membership, availability and alternatives."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, time
from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.models import PanelGroup
from app.repositories import (FacultyRepository, FreeSlotRepository,
                              PanelMemberRepository, PanelRepository)
from app.schemas.panel import (AlternativePanelRequest, PanelCreate, PanelUpdate)
from app.utils.timeutils import Interval, intersect_all, merge_intervals


class PanelService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.panels = PanelRepository(db)
        self.members = PanelMemberRepository(db)
        self.faculty = FacultyRepository(db)
        self.free_slots = FreeSlotRepository(db)

    # --------------------------------------------------------------------- CRUD
    def list(self) -> list[PanelGroup]:
        return self.panels.with_members()

    def get(self, panel_id: int) -> PanelGroup:
        panel = self.panels.get(panel_id)
        if panel is None:
            raise NotFoundError(f"Panel {panel_id} was not found")
        return panel

    def create(self, payload: PanelCreate) -> PanelGroup:
        if self.panels.by_code(payload.panel_code):
            raise ValidationError(f"Panel code '{payload.panel_code}' already exists")
        data = payload.model_dump(exclude={"members"})
        panel = self.panels.create(**data)
        self._set_members(panel, payload.members)
        self._validate_sizes(panel)
        return panel

    def update(self, panel_id: int, payload: PanelUpdate) -> PanelGroup:
        panel = self.get(panel_id)
        data = payload.model_dump(exclude={"members"}, exclude_unset=True)
        for key, value in data.items():
            if value is not None:
                setattr(panel, key, value)
        if payload.members is not None:
            self.members.clear_panel(panel.id)
            panel.members.clear()
            self._set_members(panel, payload.members)
        self.db.flush()
        self._validate_sizes(panel)
        return panel

    def delete(self, panel_id: int) -> None:
        self.panels.delete(self.get(panel_id))

    def _set_members(self, panel: PanelGroup, members) -> None:
        seen: set[int] = set()
        for item in members or []:
            if item.faculty_id in seen:
                continue
            if self.faculty.get(item.faculty_id) is None:
                raise NotFoundError(f"Faculty {item.faculty_id} was not found")
            self.members.create(panel_id=panel.id, faculty_id=item.faculty_id,
                                role=item.role, is_mandatory=item.is_mandatory)
            seen.add(item.faculty_id)
        self.db.flush()
        self.db.refresh(panel)

    def _validate_sizes(self, panel: PanelGroup) -> None:
        count = len(panel.members)
        if count and panel.minimum_panel_size > count:
            raise ValidationError(
                f"Panel {panel.panel_code} needs at least {panel.minimum_panel_size} "
                f"members but only {count} were assigned")

    # ------------------------------------------------------------- availability
    def _member_free(self, faculty_ids: list[int], start: date,
                     end: date) -> dict[int, dict[date, list[Interval]]]:
        result: dict[int, dict[date, list[Interval]]] = defaultdict(
            lambda: defaultdict(list))
        for row in self.free_slots.in_range(faculty_ids=faculty_ids, start=start,
                                            end=end):
            result[row.faculty_id][row.date].append(
                Interval.from_times(row.start_time, row.end_time))
        return result

    def availability(self, panel_id: int, start: date, end: date,
                     minimum_minutes: int = 30) -> dict[str, Any]:
        """Windows where the whole panel - or at least its minimum - is free."""
        panel = self.get(panel_id)
        member_ids = [m.faculty_id for m in panel.members]
        if not member_ids:
            raise ValidationError(f"Panel {panel.panel_code} has no members")
        free = self._member_free(member_ids, start, end)
        days = sorted({day for member in free.values() for day in member})

        full: list[dict[str, Any]] = []
        partial: list[dict[str, Any]] = []
        conflicts: list[str] = []
        for day in days:
            per_member = {fid: merge_intervals(free.get(fid, {}).get(day, []))
                          for fid in member_ids}
            complete = intersect_all([per_member[fid] for fid in member_ids]) \
                if all(per_member[fid] for fid in member_ids) else []
            for window in complete:
                if window.duration >= minimum_minutes:
                    full.append({"date": day, "start_time": window.start_time,
                                 "end_time": window.end_time,
                                 "available_faculty_ids": member_ids,
                                 "available_count": len(member_ids),
                                 "is_complete_panel": True, "meets_minimum": True})
            # Windows where only part of the panel is free.
            boundaries = sorted({point for fid in member_ids
                                 for interval in per_member[fid]
                                 for point in (interval.start, interval.end)})
            for index in range(len(boundaries) - 1):
                window = Interval(boundaries[index], boundaries[index + 1])
                if window.duration < minimum_minutes:
                    continue
                available = [fid for fid in member_ids
                             if any(i.contains(window) for i in per_member[fid])]
                if not available or len(available) == len(member_ids):
                    continue
                partial.append({"date": day, "start_time": window.start_time,
                                "end_time": window.end_time,
                                "available_faculty_ids": available,
                                "available_count": len(available),
                                "is_complete_panel": False,
                                "meets_minimum": len(available)
                                >= panel.minimum_panel_size})
            if not complete:
                conflicts.append(
                    f"No window on {day} has every member of {panel.panel_code} free")
        return {
            "panel_id": panel.id, "panel_code": panel.panel_code,
            "panel_name": panel.panel_name, "date_from": start, "date_to": end,
            "minimum_panel_size": panel.minimum_panel_size,
            "total_members": len(member_ids),
            "fully_available_windows": full,
            "partially_available_windows": partial[:200],
            "conflicts": conflicts,
        }

    def alternatives(self, payload: AlternativePanelRequest) -> list[dict[str, Any]]:
        """Panels that could take a slot the preferred panel cannot cover."""
        if payload.end_time <= payload.start_time:
            raise ValidationError("end_time must be after start_time")
        slot = Interval.from_times(payload.start_time, payload.end_time)
        results: list[dict[str, Any]] = []
        for panel in self.panels.active_with_members():
            if panel.id in set(payload.exclude_panel_ids):
                continue
            member_ids = [m.faculty_id for m in panel.members]
            free = self._member_free(member_ids, payload.date, payload.date)
            available = [fid for fid in member_ids
                         if any(interval.contains(slot)
                                for interval in free.get(fid, {}).get(payload.date, []))]
            if len(available) < panel.minimum_panel_size:
                continue
            mandatory = {m.faculty_id for m in panel.members if m.is_mandatory}
            if not mandatory.issubset(set(available)):
                continue
            score = len(available) / max(1, len(member_ids))
            if payload.department and panel.department:
                if panel.department.lower() == payload.department.lower():
                    score += 1.0
            results.append({
                "panel_id": panel.id, "panel_code": panel.panel_code,
                "panel_name": panel.panel_name, "available_faculty_ids": available,
                "available_count": len(available),
                "minimum_panel_size": panel.minimum_panel_size,
                "department": panel.department, "match_score": round(score, 3)})
        results.sort(key=lambda item: (-item["match_score"], item["panel_code"]))
        return results

    def conflicts(self) -> list[dict[str, Any]]:
        """Faculty shared between panels - useful when planning parallel tracks."""
        membership: dict[int, list[str]] = defaultdict(list)
        for panel in self.panels.with_members():
            for member in panel.members:
                membership[member.faculty_id].append(panel.panel_code)
        faculty = {f.id: f for f in self.faculty.all()}
        return [{"faculty_id": fid, "faculty_name": faculty[fid].faculty_name,
                 "panels": codes,
                 "message": (f"{faculty[fid].faculty_name} belongs to "
                             f"{len(codes)} panels ({', '.join(codes)}) and cannot "
                             "serve on two at the same time")}
                for fid, codes in sorted(membership.items())
                if len(codes) > 1 and fid in faculty]
