"""API v1 router aggregation."""
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routers import (analytics, auth, candidates, evaluations, faculty,
                                free_slots, interviews, panels, scheduling,
                                settings, uploads)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(uploads.router)
api_router.include_router(candidates.router)
api_router.include_router(faculty.router)
api_router.include_router(faculty.availability_router)
api_router.include_router(faculty.busy_router)
api_router.include_router(free_slots.router)
api_router.include_router(panels.router)
api_router.include_router(scheduling.router)
api_router.include_router(scheduling.constraints_router)
api_router.include_router(interviews.router)
api_router.include_router(evaluations.metrics_router)
api_router.include_router(evaluations.router)
api_router.include_router(analytics.router)
api_router.include_router(settings.router)
