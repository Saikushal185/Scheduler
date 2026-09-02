"""Dashboard, analytics and report generation - all computed from live data."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings as app_settings
from app.models.enums import CandidateStatus, InterviewStatus
from app.repositories import (CandidateRepository, EvaluationRepository,
                              FacultyRepository, FreeSlotRepository,
                              InterviewMemberRepository, InterviewRepository,
                              MetricRepository, PanelRepository, RunRepository,
                              ScoreRepository)
from app.services.evaluation_service import EvaluationService
from app.services.history_service import HistoryService
from app.services.interview_service import InterviewService
from app.services.settings_service import SettingsService

SCHEDULED_STATUSES = (InterviewStatus.SCHEDULED, InterviewStatus.RESCHEDULED,
                      InterviewStatus.PENDING, InterviewStatus.CONFLICT,
                      InterviewStatus.COMPLETED)


class AnalyticsService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.candidates = CandidateRepository(db)
        self.faculty = FacultyRepository(db)
        self.panels = PanelRepository(db)
        self.interviews = InterviewRepository(db)
        self.members = InterviewMemberRepository(db)
        self.free_slots = FreeSlotRepository(db)
        self.evaluations = EvaluationRepository(db)
        self.metrics = MetricRepository(db)
        self.scores = ScoreRepository(db)
        self.runs = RunRepository(db)
        self.history = HistoryService(db)
        self.settings = SettingsService(db)

    # -------------------------------------------------------------- dashboard
    def summary(self) -> dict[str, Any]:
        candidates = self.candidates.all()
        faculty = self.faculty.all()
        interviews = self.interviews.search(limit=None)
        active = [i for i in interviews if i.status in SCHEDULED_STATUSES]
        scheduled_candidate_ids = {i.candidate_id for i in active}
        free_rows = self.free_slots.in_range()
        free_minutes = sum(row.duration_minutes for row in free_rows)
        conflicts = InterviewService(self.db).detect_all_conflicts()
        total = len(candidates)
        return {
            "total_candidates": total,
            "scheduled_candidates": len(scheduled_candidate_ids),
            "unscheduled_candidates": total - len(scheduled_candidate_ids),
            "total_faculty": len(faculty),
            "available_faculty": len({row.faculty_id for row in free_rows}),
            "total_panel_groups": len(self.panels.all()),
            "available_free_slots": len(free_rows),
            "free_slot_hours": round(free_minutes / 60, 2),
            "scheduling_success_rate": round(
                100.0 * len(scheduled_candidate_ids) / total, 2) if total else 0.0,
            "conflicts_detected": len(conflicts),
            "completed_interviews": len(
                [i for i in interviews if i.status == InterviewStatus.COMPLETED]),
            # Rows recorded vs. distinct candidates covered: with two evaluators
            # per candidate the raw row count overstates coverage.
            "evaluations_recorded": self.evaluations.count(),
            "candidates_evaluated": len(
                {e.candidate_id for e in self.evaluations.all_full()}),
        }

    def dashboard(self) -> dict[str, Any]:
        today = date.today()
        interviews = self.interviews.search(limit=None)
        active = [i for i in interviews if i.status in SCHEDULED_STATUSES]
        conflicts = InterviewService(self.db).detect_all_conflicts()

        upcoming = []
        for interview in self.interviews.upcoming(today, limit=10):
            if not (interview.date and interview.start_time and interview.end_time):
                continue
            upcoming.append({
                "interview_id": interview.id,
                "schedule_code": interview.schedule_code,
                "candidate_name": interview.candidate.candidate_name
                if interview.candidate else "",
                "candidate_code": interview.candidate.candidate_code
                if interview.candidate else "",
                "date": interview.date, "start_time": interview.start_time,
                "end_time": interview.end_time,
                "panel_name": interview.panel.panel_name if interview.panel else None,
                "faculty_names": [m.faculty.faculty_name
                                  for m in interview.panel_members if m.faculty],
                "status": interview.status})

        scheduled_ids = {i.candidate_id for i in active}
        unscheduled = [{
            "candidate_id": c.id, "candidate_code": c.candidate_code,
            "candidate_name": c.candidate_name, "department": c.department,
            "reason": self._unscheduled_reason(c.id)}
            for c in self.candidates.all()
            if c.id not in scheduled_ids and c.status != CandidateStatus.WITHDRAWN][:25]

        per_day: dict[date, int] = defaultdict(int)
        for interview in active:
            if interview.date:
                per_day[interview.date] += 1

        return {
            "summary": self.summary(),
            "upcoming_interviews": upcoming,
            "recent_activity": self.history.recent(15),
            "unscheduled_candidates": unscheduled,
            "conflict_alerts": conflicts[:25],
            "faculty_availability": self.faculty_overview(),
            "status_breakdown": self.interviews.count_by_status(),
            "interviews_per_day": [{"date": day.isoformat(), "count": count}
                                   for day, count in sorted(per_day.items())],
        }

    def _unscheduled_reason(self, candidate_id: int) -> str | None:
        for run in self.runs.latest(3):
            for item in (run.result or {}).get("unscheduled", []):
                if item.get("candidate_id") == candidate_id:
                    return item.get("reason")
        return None

    def faculty_overview(self) -> list[dict[str, Any]]:
        free_by_faculty: dict[int, int] = defaultdict(int)
        for row in self.free_slots.in_range():
            free_by_faculty[row.faculty_id] += row.duration_minutes
        booked: dict[int, int] = defaultdict(int)
        counts: dict[int, int] = defaultdict(int)
        for interview in self.interviews.search(limit=None):
            if interview.status not in SCHEDULED_STATUSES:
                continue
            for member in interview.panel_members:
                booked[member.faculty_id] += interview.duration_minutes
                counts[member.faculty_id] += 1
        rows = []
        for member in self.faculty.all():
            free = free_by_faculty.get(member.id, 0)
            used = booked.get(member.id, 0)
            total = free + used
            rows.append({
                "faculty_id": member.id, "faculty_code": member.faculty_code,
                "faculty_name": member.faculty_name, "department": member.department,
                "free_minutes": free, "booked_minutes": used,
                "interviews": counts.get(member.id, 0),
                "utilisation": round(100.0 * used / total, 2) if total else 0.0})
        rows.sort(key=lambda r: -r["interviews"])
        return rows

    # ------------------------------------------------------------- scheduling
    def scheduling_analytics(self) -> dict[str, Any]:
        interviews = self.interviews.search(limit=None)
        active = [i for i in interviews if i.status in SCHEDULED_STATUSES]
        candidates = self.candidates.all()
        scheduled_ids = {i.candidate_id for i in active}

        faculty = {f.id: f for f in self.faculty.all()}
        faculty_rows: dict[int, dict[str, Any]] = {
            fid: {"id": fid, "code": member.faculty_code, "name": member.faculty_name,
                  "department": member.department, "interviews": 0, "minutes": 0,
                  "share": 0.0}
            for fid, member in faculty.items()}
        panel_rows: dict[int, dict[str, Any]] = {
            panel.id: {"id": panel.id, "code": panel.panel_code,
                       "name": panel.panel_name, "department": panel.department,
                       "interviews": 0, "minutes": 0, "share": 0.0}
            for panel in self.panels.all()}

        per_day: dict[date, int] = defaultdict(int)
        booked_minutes_per_day: dict[date, int] = defaultdict(int)
        for interview in active:
            if interview.date:
                per_day[interview.date] += 1
                booked_minutes_per_day[interview.date] += interview.duration_minutes
            for member in interview.panel_members:
                row = faculty_rows.get(member.faculty_id)
                if row:
                    row["interviews"] += 1
                    row["minutes"] += interview.duration_minutes
            if interview.panel_id in panel_rows:
                panel_rows[interview.panel_id]["interviews"] += 1
                panel_rows[interview.panel_id]["minutes"] += interview.duration_minutes

        total_interviews = max(1, len(active))
        for row in faculty_rows.values():
            row["share"] = round(100.0 * row["interviews"] / total_interviews, 2)
        for row in panel_rows.values():
            row["share"] = round(100.0 * row["interviews"] / total_interviews, 2)

        free_per_day: dict[date, int] = defaultdict(int)
        for row in self.free_slots.in_range():
            free_per_day[row.date] += row.duration_minutes
        utilisation = []
        for day in sorted(set(free_per_day) | set(booked_minutes_per_day)):
            free = free_per_day.get(day, 0)
            booked = booked_minutes_per_day.get(day, 0)
            total = free + booked
            utilisation.append({
                "date": day, "free_minutes": free, "booked_minutes": booked,
                "utilisation": round(100.0 * booked / total, 2) if total else 0.0,
                "interviews": per_day.get(day, 0)})

        departments: dict[str, dict[str, int]] = defaultdict(
            lambda: {"total": 0, "scheduled": 0})
        for candidate in candidates:
            key = candidate.department or "Unassigned"
            departments[key]["total"] += 1
            if candidate.id in scheduled_ids:
                departments[key]["scheduled"] += 1

        runs = [{"run_code": run.run_code, "algorithm": run.algorithm,
                 "status": str(run.status), "scheduled": run.scheduled_count,
                 "unscheduled": run.unscheduled_count,
                 "score": round(run.total_score, 2), "duration_ms": run.duration_ms,
                 "created_at": run.created_at.isoformat() if run.created_at else None}
                for run in self.runs.latest(10)]

        total_candidates = len(candidates)
        avg_score = (sum(i.scheduling_score for i in active) / len(active)
                     if active else 0.0)
        return {
            "scheduled_vs_unscheduled": {
                "scheduled": len(scheduled_ids),
                "unscheduled": total_candidates - len(scheduled_ids)},
            "status_breakdown": self.interviews.count_by_status(),
            "faculty_workload": sorted(faculty_rows.values(),
                                       key=lambda r: -r["interviews"]),
            "panel_workload": sorted(panel_rows.values(),
                                     key=lambda r: -r["interviews"]),
            "slot_utilisation": utilisation,
            "interviews_per_day": [{"date": day.isoformat(), "count": count}
                                   for day, count in sorted(per_day.items())],
            "scheduling_efficiency": {
                "success_rate": round(100.0 * len(scheduled_ids) / total_candidates, 2)
                if total_candidates else 0.0,
                "average_score": round(avg_score, 2),
                "conflict_count": float(len(InterviewService(self.db)
                                            .detect_all_conflicts())),
                "locked_interviews": float(len([i for i in active if i.is_locked])),
                "manual_overrides": float(len([i for i in interviews if i.is_manual])),
            },
            "department_breakdown": [
                {"department": name, "total": data["total"],
                 "scheduled": data["scheduled"],
                 "unscheduled": data["total"] - data["scheduled"]}
                for name, data in sorted(departments.items())],
            "run_history": runs,
        }

    # ------------------------------------------------------------- evaluation
    def evaluation_analytics(self) -> dict[str, Any]:
        service = EvaluationService(self.db)
        metrics = {m.id: m for m in service.list_metrics()}
        evaluations = self.evaluations.all_full()

        totals: dict[int, list[float]] = defaultdict(list)
        for evaluation in evaluations:
            for score in evaluation.scores:
                totals[score.metric_id].append(score.raw_score)

        metric_averages = []
        for metric in sorted(metrics.values(), key=lambda m: m.display_order):
            values = totals.get(metric.id, [])
            average = sum(values) / len(values) if values else 0.0
            span = max(1e-9, metric.max_score - metric.min_score)
            metric_averages.append({
                "metric_id": metric.id, "metric_key": metric.metric_key,
                "metric_name": metric.name, "average": round(average, 3),
                "max_score": metric.max_score, "weight": metric.weight,
                "evaluations": len(values),
                "normalized_average": round(
                    (average - metric.min_score) / span
                    * app_settings.EVALUATION_NORMALISED_SCALE, 2)})

        buckets = [(0, 20), (20, 40), (40, 60), (60, 80), (80, 100.01)]
        distribution = []
        for lower, upper in buckets:
            count = len([e for e in evaluations
                         if lower <= e.normalized_score < upper])
            distribution.append({"label": f"{lower}-{min(100, int(upper))}",
                                 "lower": float(lower), "upper": float(upper),
                                 "count": count})

        rankings = service.rankings()
        panel_stats: dict[int, list[float]] = defaultdict(list)
        faculty_stats: dict[int, list[float]] = defaultdict(list)
        for evaluation in evaluations:
            if evaluation.panel_id:
                panel_stats[evaluation.panel_id].append(evaluation.normalized_score)
            if evaluation.evaluator_faculty_id:
                faculty_stats[evaluation.evaluator_faculty_id].append(
                    evaluation.normalized_score)
        panels = {p.id: p for p in self.panels.all()}
        faculty = {f.id: f for f in self.faculty.all()}
        return {
            "metric_averages": metric_averages,
            "score_distribution": distribution,
            "top_candidates": rankings[:10],
            "panel_statistics": [
                {"panel_id": pid, "panel_code": panels[pid].panel_code,
                 "panel_name": panels[pid].panel_name, "evaluations": len(values),
                 "average_score": round(sum(values) / len(values), 2)}
                for pid, values in panel_stats.items() if pid in panels and values],
            "faculty_statistics": [
                {"faculty_id": fid, "faculty_code": faculty[fid].faculty_code,
                 "faculty_name": faculty[fid].faculty_name, "evaluations": len(values),
                 "average_score": round(sum(values) / len(values), 2)}
                for fid, values in faculty_stats.items() if fid in faculty and values],
            "total_evaluations": len(evaluations),
            "candidates_evaluated": len({e.candidate_id for e in evaluations}),
            "average_overall_score": round(
                sum(r["overall_score"] for r in rankings) / len(rankings), 3)
            if rankings else 0.0,
        }

    # ----------------------------------------------------------------- report
    def report(self) -> dict[str, Any]:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "organisation": self.settings.get().organisation_name,
            "summary": self.summary(),
            "scheduling": self.scheduling_analytics(),
            "evaluation": self.evaluation_analytics(),
            "rankings": EvaluationService(self.db).rankings(),
        }
