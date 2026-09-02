from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import DbSession, ReportUser
from app.schemas.analytics import (DashboardResponse, EvaluationAnalytics,
                                   ReportResponse, SchedulingAnalytics, SummaryCards)
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["Analytics & Reports"])


@router.get("/dashboard", response_model=DashboardResponse,
            summary="Everything the dashboard needs in one call")
def dashboard(db: DbSession, user: ReportUser):
    return AnalyticsService(db).dashboard()


@router.get("/summary", response_model=SummaryCards, summary="Summary cards")
def summary(db: DbSession, user: ReportUser):
    return AnalyticsService(db).summary()


@router.get("/scheduling", response_model=SchedulingAnalytics,
            summary="Workload, utilisation and efficiency analytics")
def scheduling(db: DbSession, user: ReportUser):
    return AnalyticsService(db).scheduling_analytics()


@router.get("/evaluation", response_model=EvaluationAnalytics,
            summary="Metric averages, distribution and rankings")
def evaluation(db: DbSession, user: ReportUser):
    return AnalyticsService(db).evaluation_analytics()


@router.get("/report", response_model=ReportResponse,
            summary="Full report payload (schedule + evaluation)")
def report(db: DbSession, user: ReportUser):
    return AnalyticsService(db).report()
