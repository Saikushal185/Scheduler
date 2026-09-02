"""Global interview settings (singleton row seeded from app configuration)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import settings as app_settings
from app.models import InterviewSettings
from app.repositories import SettingsRepository
from app.schemas.settings import SettingsUpdate
from app.utils.timeutils import parse_time


class SettingsService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = SettingsRepository(db)

    def get(self) -> InterviewSettings:
        row = self.repo.singleton()
        if row is None:
            row = InterviewSettings(
                id=1,
                interview_duration_minutes=app_settings.DEFAULT_INTERVIEW_DURATION_MIN,
                break_duration_minutes=app_settings.DEFAULT_BREAK_DURATION_MIN,
                day_start_time=parse_time(app_settings.DEFAULT_DAY_START),
                day_end_time=parse_time(app_settings.DEFAULT_DAY_END),
                slot_granularity_minutes=app_settings.DEFAULT_SLOT_GRANULARITY_MIN,
                min_panel_size=app_settings.DEFAULT_MIN_PANEL_SIZE,
                max_panel_size=app_settings.DEFAULT_MAX_PANEL_SIZE,
                max_interviews_per_faculty_per_day=(
                    app_settings.DEFAULT_MAX_INTERVIEWS_PER_FACULTY_PER_DAY),
                default_algorithm=app_settings.DEFAULT_ALGORITHM,
            )
            self.db.add(row)
            self.db.flush()
        return row

    def update(self, payload: SettingsUpdate) -> InterviewSettings:
        row = self.get()
        for key, value in payload.model_dump(exclude_unset=True).items():
            if value is not None:
                setattr(row, key, value)
        self.db.flush()
        return row
