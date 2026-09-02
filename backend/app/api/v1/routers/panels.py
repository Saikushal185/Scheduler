from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.common import Message
from app.schemas.panel import (AlternativePanel, AlternativePanelRequest,
                               PanelAvailabilityResponse, PanelCreate, PanelRead,
                               PanelUpdate)
from app.services.panel_service import PanelService

router = APIRouter(prefix="/panels", tags=["Panel Groups"])


@router.get("", response_model=list[PanelRead], summary="List panel groups")
def list_panels(db: DbSession, user: CurrentUser):
    return [PanelRead.model_validate(p) for p in PanelService(db).list()]


@router.get("/conflicts", summary="Faculty shared between panels")
def panel_conflicts(db: DbSession, user: CurrentUser):
    return PanelService(db).conflicts()


@router.post("/alternatives", response_model=list[AlternativePanel],
             summary="Find alternative panels for a slot")
def alternatives(payload: AlternativePanelRequest, db: DbSession, user: CurrentUser):
    return PanelService(db).alternatives(payload)


@router.get("/{panel_id}", response_model=PanelRead, summary="Get a panel group")
def get_panel(panel_id: int, db: DbSession, user: CurrentUser):
    return PanelRead.model_validate(PanelService(db).get(panel_id))


@router.get("/{panel_id}/availability", response_model=PanelAvailabilityResponse,
            summary="Windows where the panel is available")
def panel_availability(panel_id: int, db: DbSession, user: CurrentUser,
                       start_date: date | None = None, end_date: date | None = None,
                       minimum_minutes: int = 30):
    start = start_date or date.today()
    end = end_date or (start + timedelta(days=13))
    return PanelService(db).availability(panel_id, start, end, minimum_minutes)


@router.post("", response_model=PanelRead, status_code=status.HTTP_201_CREATED,
             summary="Create a panel group")
def create_panel(payload: PanelCreate, db: DbSession, user: CurrentUser):
    return PanelRead.model_validate(PanelService(db).create(payload))


@router.put("/{panel_id}", response_model=PanelRead, summary="Update a panel group")
def update_panel(panel_id: int, payload: PanelUpdate, db: DbSession, user: CurrentUser):
    return PanelRead.model_validate(PanelService(db).update(panel_id, payload))


@router.delete("/{panel_id}", response_model=Message, summary="Delete a panel group")
def delete_panel(panel_id: int, db: DbSession, user: CurrentUser):
    PanelService(db).delete(panel_id)
    return Message(message=f"Panel {panel_id} deleted")
