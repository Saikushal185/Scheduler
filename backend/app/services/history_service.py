"""Schedule history - every change to an interview is preserved."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import Interview
from app.models.enums import HistoryAction
from app.repositories import HistoryRepository, InterviewRepository


class HistoryService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = HistoryRepository(db)
        self.interviews = InterviewRepository(db)

    @staticmethod
    def snapshot(interview: Interview) -> dict[str, Any]:
        return {
            "date": interview.date.isoformat() if interview.date else None,
            "start_time": (interview.start_time.strftime("%H:%M")
                           if interview.start_time else None),
            "end_time": (interview.end_time.strftime("%H:%M")
                         if interview.end_time else None),
            "panel_id": interview.panel_id,
            "faculty_ids": sorted(m.faculty_id for m in interview.panel_members),
            "status": str(interview.status),
            "is_locked": interview.is_locked,
            "location": interview.location,
        }

    def record(self, interview: Interview, action: HistoryAction,
               previous: dict[str, Any], new: dict[str, Any], *,
               reason: str | None = None, warnings: list[str] | None = None,
               user_id: int | None = None):
        return self.repo.create(
            interview_id=interview.id, action=action, previous_state=previous,
            new_state=new, reason=reason, warnings=warnings or [],
            performed_by=user_id)

    def recent(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.repo.recent(limit)
        interviews = {i.id: i for i in self.interviews.search(limit=None)}
        items = []
        for row in rows:
            interview = interviews.get(row.interview_id)
            items.append({
                "id": row.id,
                "interview_id": row.interview_id,
                "action": str(row.action),
                "reason": row.reason,
                "schedule_code": interview.schedule_code if interview else None,
                "candidate_name": (interview.candidate.candidate_name
                                   if interview and interview.candidate else None),
                "created_at": row.created_at.isoformat() if row.created_at else "",
            })
        return items

    def for_interview(self, interview_id: int):
        return self.repo.for_interview(interview_id)
