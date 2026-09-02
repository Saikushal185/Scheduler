"""Generate the sample Excel/CSV input files under ../samples.

Run:  python -m scripts.generate_samples
The dates are always in the near future so the generated workbook can be
uploaded and scheduled straight away.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "samples"

DEPARTMENTS = ["Computer Science", "Electronics", "Mechanical", "Mathematics"]
FIRST_NAMES = ["Aarav", "Diya", "Vihaan", "Ananya", "Arjun", "Ishita", "Kabir",
               "Meera", "Rohan", "Sara", "Aditya", "Nisha", "Karan", "Priya",
               "Vikram", "Tara", "Rahul", "Neha", "Siddharth", "Kavya", "Manish",
               "Pooja", "Aryan", "Sneha", "Nikhil", "Divya", "Rajat", "Anjali",
               "Varun", "Riya", "Akash", "Shreya", "Dev", "Isha", "Yash", "Naina"]
LAST_NAMES = ["Sharma", "Verma", "Iyer", "Nair", "Reddy", "Gupta", "Bose", "Kapoor",
              "Menon", "Rao", "Joshi", "Desai"]
TITLES = ["Professor", "Associate Professor", "Assistant Professor", "Dean"]


def next_monday(reference: date | None = None) -> date:
    today = reference or date.today()
    return today + timedelta(days=(7 - today.weekday()) % 7 or 7)


def build_frames(start: date) -> dict[str, pd.DataFrame]:
    days = [start + timedelta(days=offset) for offset in range(5)]

    # ---------------------------------------------------------------- faculty
    faculty_rows = []
    for index in range(12):
        department = DEPARTMENTS[index % len(DEPARTMENTS)]
        name = f"Dr. {FIRST_NAMES[index]} {LAST_NAMES[index % len(LAST_NAMES)]}"
        faculty_rows.append({
            "faculty_id": f"FAC{index + 1:03d}",
            "faculty_name": name,
            "department": department,
            "email": f"faculty{index + 1}@institute.edu",
            "designation": TITLES[index % len(TITLES)],
            "max_interviews_per_day": 6 if index % 4 else 4,
        })
    faculty = pd.DataFrame(faculty_rows)

    # ----------------------------------------------------- faculty availability
    availability_rows = []
    for index, row in enumerate(faculty_rows):
        for day in days:
            # A couple of faculty only work mornings, one skips a day entirely.
            if index == 3 and day == days[2]:
                continue
            windows = ([("09:00", "13:00")] if index % 5 == 0
                       else [("09:00", "13:00"), ("14:00", "17:00")])
            for start_time, end_time in windows:
                availability_rows.append({
                    "faculty_id": row["faculty_id"],
                    "date": day.isoformat(),
                    "start_time": start_time,
                    "end_time": end_time,
                    "availability_status": "AVAILABLE",
                })
    availability = pd.DataFrame(availability_rows)

    # ------------------------------------------------------ faculty busy slots
    busy_rows = []
    for index, row in enumerate(faculty_rows[:6]):
        busy_rows.append({
            "faculty_id": row["faculty_id"],
            "date": days[index % len(days)].isoformat(),
            "start_time": "10:00", "end_time": "11:00",
            "reason": "Department meeting",
        })
    busy_rows.append({"faculty_id": "FAC002", "date": days[1].isoformat(),
                      "start_time": "15:00", "end_time": "16:30",
                      "reason": "Doctoral committee"})
    busy = pd.DataFrame(busy_rows)

    # ------------------------------------------------------------ panel groups
    panel_rows = []
    for index in range(4):
        members = [f"FAC{index * 3 + offset:03d}" for offset in (1, 2, 3)]
        panel_rows.append({
            "panel_id": f"PANEL{index + 1}",
            "panel_name": f"{DEPARTMENTS[index]} Panel",
            "faculty_members": ", ".join(members),
            "minimum_panel_size": 2,
            "maximum_panel_size": 3,
            "department": DEPARTMENTS[index],
            "description": f"Interview panel for {DEPARTMENTS[index]}",
            "mandatory_members": members[0],
        })
    panels = pd.DataFrame(panel_rows)

    # -------------------------------------------------------------- candidates
    candidate_rows = []
    for index in range(30):
        department = DEPARTMENTS[index % len(DEPARTMENTS)]
        preferred_day = days[index % len(days)]
        name = (f"{FIRST_NAMES[(index + 5) % len(FIRST_NAMES)]} "
                f"{LAST_NAMES[(index + 2) % len(LAST_NAMES)]}")
        row = {
            "candidate_id": f"CAND{index + 1:03d}",
            "candidate_name": name,
            "email": f"candidate{index + 1}@example.com",
            "phone": f"98765{index:05d}",
            "department": department,
            "position": "Research Scholar" if index % 3 else "Teaching Assistant",
            "preferred_date": preferred_day.isoformat(),
            "preferred_time": "10:00" if index % 2 else "14:30",
            "preferred_panel": f"PANEL{(index % 4) + 1}",
            "priority": 2 if index < 5 else (1 if index < 12 else 0),
            "notes": "",
        }
        # Every third candidate declares explicit availability windows.
        if index % 3 == 0:
            row["availability"] = (f"{preferred_day.isoformat()} 09:00-13:00; "
                                   f"{days[(index + 1) % len(days)].isoformat()} "
                                   "14:00-17:00")
        else:
            row["availability"] = ""
        candidate_rows.append(row)
    candidates = pd.DataFrame(candidate_rows)

    # ---------------------------------------------------------------- settings
    settings = pd.DataFrame([{
        "interview_duration": 30,
        "break_duration": 10,
        "start_time": "09:00",
        "end_time": "17:00",
        "scheduling_date_range": f"{days[0].isoformat()} to {days[-1].isoformat()}",
        "slot_granularity": 15,
        "min_panel_size": 2,
        "max_panel_size": 3,
        "max_interviews_per_faculty_per_day": 6,
        "allow_weekends": "No",
    }])

    return {
        "Candidates": candidates,
        "Faculty": faculty,
        "Faculty Availability": availability,
        "Faculty Busy Slots": busy,
        "Panel Groups": panels,
        "Interview Settings": settings,
    }


def build_evaluations(candidate_codes: list[str], metric_keys: list[str]) -> pd.DataFrame:
    """Scores keyed by metric column names supplied by the caller."""
    rows = []
    for index, code in enumerate(candidate_codes):
        row: dict[str, object] = {"candidate_id": code,
                                  "evaluator_id": f"FAC{(index % 12) + 1:03d}",
                                  "panel_id": f"PANEL{(index % 4) + 1}"}
        for position, key in enumerate(metric_keys):
            # Deterministic but varied scores in the 4.0 - 9.5 range.
            row[key] = round(4.0 + ((index * 7 + position * 3) % 12) * 0.5, 1)
        row["recommendation"] = "SELECT" if index % 3 == 0 else (
            "HOLD" if index % 3 == 1 else "REJECT")
        row["remarks"] = "Automatically generated sample evaluation"
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> None:
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    start = next_monday()
    frames = build_frames(start)

    workbook = SAMPLES_DIR / "interview_data.xlsx"
    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        for sheet, frame in frames.items():
            frame.to_excel(writer, sheet_name=sheet, index=False)

    # Evaluation workbook uses the default metric keys (metric_1 ... metric_7).
    metric_keys = [f"metric_{i}" for i in range(1, 8)]
    codes = frames["Candidates"]["candidate_id"].tolist()[:20]
    evaluations = build_evaluations(codes, metric_keys)
    evaluations.to_excel(SAMPLES_DIR / "evaluations.xlsx", index=False,
                         sheet_name="Evaluation")

    # A plain CSV, showing the alternative single-dataset upload path.
    frames["Candidates"].to_csv(SAMPLES_DIR / "candidates.csv", index=False)

    # A deliberately broken file used to demonstrate validation errors.
    broken = frames["Candidates"].head(5).copy()
    broken.loc[0, "candidate_id"] = None
    broken.loc[1, "preferred_date"] = "31/02/2026"
    broken.loc[2, "preferred_time"] = "25:99"
    broken = broken.drop(columns=["candidate_name"])
    broken.to_excel(SAMPLES_DIR / "invalid_candidates.xlsx", index=False,
                    sheet_name="Candidates")

    print(f"Sample files written to {SAMPLES_DIR}")
    for path in sorted(SAMPLES_DIR.iterdir()):
        print(f"  - {path.name}")
    print(f"Scheduling window: {start} .. {start + timedelta(days=4)}")


if __name__ == "__main__":
    main()
