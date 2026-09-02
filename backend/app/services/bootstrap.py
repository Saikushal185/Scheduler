"""First-run bootstrap: admin user, settings, metrics and constraints."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import settings as app_settings
from app.core.logging_config import get_logger
from app.core.security import hash_password
from app.models.enums import UserRole
from app.repositories import UserRepository
from app.services.evaluation_service import EvaluationService
from app.services.scheduling_service import SchedulingService
from app.services.settings_service import SettingsService

logger = get_logger(__name__)


def bootstrap_database(db: Session) -> None:
    users = UserRepository(db)
    if users.by_email(app_settings.FIRST_ADMIN_EMAIL) is None:
        users.create(email=app_settings.FIRST_ADMIN_EMAIL.lower(),
                     full_name=app_settings.FIRST_ADMIN_NAME,
                     hashed_password=hash_password(app_settings.FIRST_ADMIN_PASSWORD),
                     role=UserRole.ADMIN)
        logger.info("Created the bootstrap administrator %s",
                    app_settings.FIRST_ADMIN_EMAIL)
    SettingsService(db).get()
    EvaluationService(db).ensure_metrics()
    SchedulingService(db).ensure_constraints()
    db.flush()
