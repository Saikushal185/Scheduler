"""End-to-end API tests running the documented workflow.

    upload -> validate -> import -> free slots -> schedule -> confirm
    -> manual override -> evaluation -> analytics
"""
from __future__ import annotations

import io
from datetime import date, time, timedelta
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.core.database import engine, get_db
from app.main import app
from app.models import Base
from app.services.bootstrap import bootstrap_database
from scripts.generate_samples import build_frames, build_evaluations, next_monday

API = "/api/v1"


def workbook_bytes(frames: dict[str, pd.DataFrame]) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for sheet, frame in frames.items():
            frame.to_excel(writer, sheet_name=sheet, index=False)
    return buffer.getvalue()


def sheet_bytes(frame: pd.DataFrame, sheet_name: str) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        frame.to_excel(writer, sheet_name=sheet_name, index=False)
    return buffer.getvalue()


@pytest.fixture(scope="module")
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = next(get_db())
    bootstrap_database(session)
    session.commit()
    session.close()
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="module")
def token(client):
    response = client.post(f"{API}/auth/login",
                           json={"email": "admin@example.com", "password": "admin123"})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.fixture(scope="module")
def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def start_date():
    return next_monday(date.today())


# --------------------------------------------------------------------- basics
def test_health_endpoint_is_public(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_protected_endpoint_requires_a_token(client):
    assert client.get(f"{API}/candidates").status_code == 401


def test_login_rejects_bad_credentials(client):
    response = client.post(f"{API}/auth/login",
                           json={"email": "admin@example.com", "password": "wrong"})
    assert response.status_code == 401
    assert response.json()["error"] == "unauthorized"


def test_current_user(client, auth):
    response = client.get(f"{API}/auth/me", headers=auth)
    assert response.status_code == 200
    assert response.json()["email"] == "admin@example.com"


def test_seven_metrics_are_seeded_and_configurable(client, auth):
    response = client.get(f"{API}/evaluation-metrics", headers=auth)
    assert response.status_code == 200
    metrics = response.json()
    assert len(metrics) == 7
    assert all(m["metric_key"] and m["name"] for m in metrics)


# --------------------------------------------------------------- upload flow
def test_invalid_file_reports_row_level_errors(client, auth, start_date):
    frames = build_frames(start_date)
    broken = frames["Candidates"].head(4).copy()
    broken.loc[1, "preferred_time"] = "25:99"
    broken = broken.drop(columns=["candidate_name"])
    response = client.post(
        f"{API}/uploads/validate", headers=auth,
        files={"file": ("broken.xlsx", sheet_bytes(broken, "Candidates"),
                        "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet")})
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["is_valid"] is False
    messages = " ".join(e["message"] for e in body["errors"])
    assert "candidate_name" in messages


def test_unsupported_file_type_is_rejected(client, auth):
    response = client.post(f"{API}/uploads/validate", headers=auth,
                           files={"file": ("notes.txt", b"hello", "text/plain")})
    assert response.status_code == 422
    assert "Unsupported file type" in response.json()["message"]


def test_import_workbook_creates_every_entity(client, auth, start_date):
    frames = build_frames(start_date)
    response = client.post(
        f"{API}/uploads/import", headers=auth,
        files={"file": ("interview_data.xlsx", workbook_bytes(frames),
                        "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet")})
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["total_failed"] == 0
    assert body["total_created"] > 100

    assert len(client.get(f"{API}/candidates", headers=auth).json()) == 30
    assert len(client.get(f"{API}/faculty", headers=auth).json()) == 12
    assert len(client.get(f"{API}/panels", headers=auth).json()) == 4


def test_settings_sheet_updated_the_configuration(client, auth):
    settings = client.get(f"{API}/settings", headers=auth).json()
    assert settings["interview_duration_minutes"] == 30
    assert settings["break_duration_minutes"] == 10
    assert settings["schedule_start_date"] is not None


# ---------------------------------------------------------------- free slots
def test_free_slots_are_calculated_from_availability(client, auth):
    response = client.post(f"{API}/free-slots/recalculate", headers=auth, json={})
    assert response.status_code == 200
    assert response.json()["slots_created"] > 0

    slots = client.get(f"{API}/free-slots", headers=auth).json()
    assert slots
    assert all(slot["duration_minutes"] > 0 for slot in slots)


def test_busy_slot_splits_the_free_window(client, auth, start_date):
    faculty = client.get(f"{API}/faculty", headers=auth).json()[0]
    day = (start_date + timedelta(days=3)).isoformat()
    before = [s for s in client.get(f"{API}/free-slots", headers=auth,
                                    params={"faculty_id": faculty["id"]}).json()
              if s["date"] == day]
    response = client.post(f"{API}/faculty-busy-slots", headers=auth,
                           json={"faculty_id": faculty["id"], "date": day,
                                 "start_time": "11:00", "end_time": "11:30",
                                 "reason": "Guest lecture"})
    assert response.status_code == 201, response.text
    after = [s for s in client.get(f"{API}/free-slots", headers=auth,
                                   params={"faculty_id": faculty["id"]}).json()
             if s["date"] == day]
    assert len(after) > len(before)
    blocked = (time(11, 0), time(11, 30))
    for slot in after:
        start = time.fromisoformat(slot["start_time"])
        end = time.fromisoformat(slot["end_time"])
        assert not (start < blocked[1] and blocked[0] < end), \
            f"free slot {slot} still overlaps the blocked 11:00-11:30 window"

    busy_id = response.json()["id"]
    assert client.delete(f"{API}/faculty-busy-slots/{busy_id}",
                         headers=auth).status_code == 200


def test_panel_availability_reports_common_windows(client, auth, start_date):
    panel = client.get(f"{API}/panels", headers=auth).json()[0]
    response = client.get(f"{API}/panels/{panel['id']}/availability", headers=auth,
                          params={"start_date": start_date.isoformat(),
                                  "end_date": (start_date + timedelta(days=4)).isoformat()})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_members"] == 3
    assert body["fully_available_windows"]


# ---------------------------------------------------------------- scheduling
def test_generate_preview_schedules_candidates(client, auth):
    response = client.post(f"{API}/scheduling/generate", headers=auth,
                           json={"algorithm": "backtracking"})
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["scheduled"], "the engine should place candidates"
    assert body["conflicts"] == []
    assert body["success_rate"] > 50
    for item in body["scheduled"]:
        assert item["faculty_ids"]
        assert item["start_time"] < item["end_time"]
        assert item["priority_info"]
    for item in body["unscheduled"]:
        assert item["reason"]
    return body


def test_every_algorithm_is_selectable(client, auth):
    names = [a["name"] for a in client.get(f"{API}/scheduling/algorithms",
                                           headers=auth).json()]
    assert {"greedy", "backtracking"} <= set(names)
    for name in names:
        response = client.post(f"{API}/scheduling/generate", headers=auth,
                               json={"algorithm": name})
        assert response.status_code == 201, response.text
        assert response.json()["algorithm"] == name


def test_confirm_creates_interviews_and_recalculates_free_slots(client, auth):
    preview = client.post(f"{API}/scheduling/generate", headers=auth,
                          json={"algorithm": "backtracking"}).json()
    response = client.post(f"{API}/scheduling/runs/{preview['run_id']}/confirm",
                           headers=auth)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["interviews_created"] == len(preview["scheduled"])

    interviews = client.get(f"{API}/interviews", headers=auth).json()
    assert len(interviews) == len(preview["scheduled"])
    assert all(i["panel_members"] for i in interviews)
    assert client.get(f"{API}/interviews/conflicts", headers=auth).json() == []


def test_calendar_events_are_returned_for_the_schedule(client, auth):
    events = client.get(f"{API}/interviews/calendar", headers=auth).json()
    assert events
    assert all(event["start"] < event["end"] for event in events)


# ----------------------------------------------------------- manual override
def test_reschedule_into_a_taken_slot_is_rejected(client, auth):
    interviews = client.get(f"{API}/interviews", headers=auth).json()
    first, second = interviews[0], interviews[1]
    response = client.put(f"{API}/interviews/{second['id']}/reschedule", headers=auth,
                          json={"date": first["date"],
                                "start_time": first["start_time"],
                                "faculty_ids": [m["faculty_id"]
                                                for m in first["panel_members"]],
                                "panel_id": first["panel_id"]})
    assert response.status_code == 409
    assert response.json()["details"]


def test_reschedule_to_a_free_slot_succeeds_and_is_recorded(client, auth):
    interview = client.get(f"{API}/interviews", headers=auth).json()[0]
    free = client.get(f"{API}/free-slots", headers=auth,
                      params={"faculty_id": interview["panel_members"][0]["faculty_id"],
                              "min_minutes": 40}).json()
    assert free, "expected at least one free window for the reschedule"

    # Some free windows sit right next to another interview and would break the
    # mandatory gap; walk the list until one is accepted.
    response = None
    for target in reversed(free):
        response = client.put(f"{API}/interviews/{interview['id']}/reschedule",
                              headers=auth,
                              json={"date": target["date"],
                                    "start_time": target["start_time"],
                                    "reason": "Candidate requested a later slot"})
        if response.status_code == 200:
            break
        assert response.status_code == 409, response.text
        assert response.json()["details"], "a rejection must explain itself"
    assert response is not None and response.status_code == 200, response.text
    body = response.json()
    assert body["interview"]["status"] in {"RESCHEDULED", "CONFLICT"}
    assert body["interview"]["date"] == target["date"]

    history = client.get(f"{API}/interviews/{interview['id']}/history",
                         headers=auth).json()
    assert any(entry["action"] in {"RESCHEDULED", "PANEL_CHANGED"} for entry in history)
    assert history[0]["previous_state"]


def test_locking_prevents_changes_until_unlocked(client, auth):
    interview = client.get(f"{API}/interviews", headers=auth).json()[1]
    assert client.put(f"{API}/interviews/{interview['id']}/lock", headers=auth,
                      json={"is_locked": True}).status_code == 200
    blocked = client.put(f"{API}/interviews/{interview['id']}/reschedule", headers=auth,
                         json={"start_time": "09:00"})
    assert blocked.status_code == 409
    assert client.put(f"{API}/interviews/{interview['id']}/lock", headers=auth,
                      json={"is_locked": False}).status_code == 200


def test_marking_faculty_unavailable_flags_affected_interviews(client, auth):
    interview = client.get(f"{API}/interviews", headers=auth).json()[2]
    faculty_id = interview["panel_members"][0]["faculty_id"]
    response = client.post(f"{API}/interviews/faculty-unavailable", headers=auth,
                           json={"faculty_id": faculty_id, "date": interview["date"],
                                 "start_time": interview["start_time"],
                                 "end_time": interview["end_time"],
                                 "reason": "Medical leave"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["affected_interviews"]
    assert any(item["interview_id"] == interview["id"]
               for item in body["affected_interviews"])
    updated = client.get(f"{API}/interviews/{interview['id']}", headers=auth).json()
    assert updated["status"] == "CONFLICT"


def test_cancelling_an_interview_frees_the_faculty(client, auth):
    interview = client.get(f"{API}/interviews", headers=auth).json()[-1]
    response = client.post(f"{API}/interviews/{interview['id']}/cancel", headers=auth)
    assert response.status_code == 200, response.text
    assert response.json()["interview"]["status"] == "CANCELLED"
    busy = client.get(f"{API}/faculty-busy-slots", headers=auth,
                      params={"faculty_id":
                              interview["panel_members"][0]["faculty_id"]}).json()
    assert not any(item["interview_id"] == interview["id"] for item in busy)


# ---------------------------------------------------------------- evaluation
def test_import_evaluation_sheet_scores_candidates(client, auth):
    candidates = client.get(f"{API}/candidates", headers=auth).json()
    codes = [c["candidate_code"] for c in candidates[:15]]
    metric_keys = [m["metric_key"] for m in
                   client.get(f"{API}/evaluation-metrics", headers=auth).json()]
    frame = build_evaluations(codes, metric_keys)
    response = client.post(
        f"{API}/uploads/import", headers=auth,
        files={"file": ("evaluations.xlsx", sheet_bytes(frame, "Evaluation"),
                        "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet")})
    assert response.status_code == 201, response.text
    assert response.json()["total_failed"] == 0

    evaluations = client.get(f"{API}/evaluations", headers=auth).json()
    assert len(evaluations) == 15
    assert all(len(e["scores"]) == 7 for e in evaluations)
    assert all(e["overall_score"] > 0 for e in evaluations)


def test_rankings_are_ordered_and_numbered(client, auth):
    rankings = client.get(f"{API}/evaluations/rankings", headers=auth).json()
    assert rankings
    assert [r["rank"] for r in rankings] == list(range(1, len(rankings) + 1))
    scores = [r["overall_score"] for r in rankings]
    assert scores == sorted(scores, reverse=True)
    assert rankings[0]["strongest_metric"] and rankings[0]["weakest_metric"]


def test_changing_metric_weights_rescores_every_evaluation(client, auth):
    before = client.get(f"{API}/evaluations/rankings", headers=auth).json()[0]
    metrics = client.get(f"{API}/evaluation-metrics", headers=auth).json()
    payload = {"weights": [{"metric_id": m["id"], "weight": 1.0} for m in metrics]}
    assert client.put(f"{API}/evaluation-metrics", headers=auth,
                      json=payload).status_code == 200
    after = {r["candidate_id"]: r for r in
             client.get(f"{API}/evaluations/rankings", headers=auth).json()}
    assert after[before["candidate_id"]]["overall_score"] != before["overall_score"]


def test_metric_can_be_renamed_without_touching_code(client, auth):
    metric = client.get(f"{API}/evaluation-metrics", headers=auth).json()[0]
    response = client.put(f"{API}/evaluation-metrics/{metric['id']}", headers=auth,
                          json={"name": "Renamed Metric", "max_score": 20})
    assert response.status_code == 200, response.text
    assert response.json()["name"] == "Renamed Metric"
    profile_candidate = client.get(f"{API}/evaluations", headers=auth).json()[0]
    profile = client.get(
        f"{API}/evaluations/candidate/{profile_candidate['candidate_id']}/profile",
        headers=auth).json()
    assert any(m["metric_name"] == "Renamed Metric" for m in profile["metrics"])


def test_manual_evaluation_validates_the_score_range(client, auth):
    candidate = client.get(f"{API}/candidates", headers=auth).json()[-1]
    metrics = client.get(f"{API}/evaluation-metrics", headers=auth).json()
    response = client.post(f"{API}/evaluations", headers=auth,
                           json={"candidate_id": candidate["id"],
                                 "scores": [{"metric_id": metrics[0]["id"],
                                             "raw_score": 999}]})
    assert response.status_code == 422
    assert "between" in response.json()["message"]


# ----------------------------------------------------------------- analytics
def test_dashboard_reports_live_numbers(client, auth):
    body = client.get(f"{API}/analytics/dashboard", headers=auth).json()
    summary = body["summary"]
    assert summary["total_candidates"] == 30
    assert summary["total_faculty"] == 12
    assert summary["total_panel_groups"] == 4
    assert summary["scheduled_candidates"] > 0
    assert 0 <= summary["scheduling_success_rate"] <= 100
    assert "faculty_availability" in body and body["faculty_availability"]
    assert body["recent_activity"]


def test_scheduling_analytics_expose_workload_and_utilisation(client, auth):
    body = client.get(f"{API}/analytics/scheduling", headers=auth).json()
    assert body["faculty_workload"]
    assert body["panel_workload"]
    assert body["slot_utilisation"]
    assert body["scheduling_efficiency"]["success_rate"] >= 0
    assert body["run_history"]


def test_evaluation_analytics_cover_all_metrics(client, auth):
    body = client.get(f"{API}/analytics/evaluation", headers=auth).json()
    assert len(body["metric_averages"]) == 7
    assert sum(bucket["count"] for bucket in body["score_distribution"]) > 0
    assert body["top_candidates"]


def test_report_endpoint_returns_the_full_payload(client, auth):
    body = client.get(f"{API}/analytics/report", headers=auth).json()
    assert body["summary"] and body["scheduling"] and body["evaluation"]
    assert body["rankings"]
    assert body["generated_at"]
