from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.settings import SettingsRead, SettingsUpdate
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get("", response_model=SettingsRead, summary="Global interview settings")
def get_settings(db: DbSession, user: CurrentUser):
    return SettingsRead.model_validate(SettingsService(db).get())


@router.put("", response_model=SettingsRead, summary="Update interview settings")
def update_settings(payload: SettingsUpdate, db: DbSession, user: CurrentUser):
    return SettingsRead.model_validate(SettingsService(db).update(payload))
