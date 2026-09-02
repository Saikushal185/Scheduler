"""Excel / CSV ingestion: read -> validate -> import.

Every uploaded file is stored, parsed sheet by sheet, validated against the
declarative column mappings, and only then written to the database.  Row level
problems are reported with the sheet, row number, column and value so the user
can fix the source file.
"""
from __future__ import annotations

import re
from datetime import date, time
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
from sqlalchemy.orm import Session

from app.core.config import settings as app_settings
from app.core.exceptions import FileValidationError, NotFoundError
from app.core.logging_config import get_logger
from app.models import (Candidate, EvaluationMetric, Faculty, FacultyAvailability,
                        FacultyBusySlot, PanelGroup, PanelMember, UploadedFile)
from app.models.enums import (AvailabilityStatus, BusySlotSource, DatasetType,
                              UploadStatus)
from app.repositories import (AvailabilityRepository, BusySlotRepository,
                              CandidateRepository, FacultyRepository,
                              MetricRepository, PanelMemberRepository,
                              PanelRepository, UploadRepository)
from app.services.column_mappings import (BY_TYPE, DatasetSpec, detect_dataset,
                                          normalise)
from app.services.free_slot_service import FreeSlotService
from app.services.settings_service import SettingsService
from app.utils.timeutils import parse_date, parse_time

logger = get_logger(__name__)

_NULLS = {"", "nan", "nat", "none", "null", "-", "n/a", "na"}


def _clean(value: Any) -> Any:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, str):
        text = value.strip()
        return None if text.lower() in _NULLS else text
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _as_str(value: Any) -> str | None:
    value = _clean(value)
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _as_int(value: Any) -> int | None:
    value = _clean(value)
    if value is None:
        return None
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    value = _clean(value)
    if value is None:
        return None
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _as_bool(value: Any) -> bool | None:
    value = _clean(value)
    if value is None:
        return None
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on", "allowed"}


def split_list(value: Any) -> list[str]:
    """Split 'F001, F002; F003' or 'F001|F002' into codes."""
    text = _as_str(value)
    if not text:
        return []
    parts = re.split(r"[,;|/]+|\s{2,}", text)
    return [p.strip() for p in parts if p.strip()]


def parse_availability_windows(value: Any, fallback_date: date | None = None
                               ) -> tuple[list[dict[str, str]], list[str]]:
    """Parse candidate availability text into structured windows.

    Accepted forms (separated by ';' or newlines):
        2026-03-02 09:00-12:00
        2026-03-02 09:00 to 12:00
        09:00-12:00                  (uses the preferred date)
        2026-03-02                   (whole day)
    """
    text = _as_str(value)
    if not text:
        return [], []
    windows: list[dict[str, str]] = []
    problems: list[str] = []
    for chunk in re.split(r"[;\n]+", text):
        chunk = chunk.strip()
        if not chunk:
            continue
        normalised = chunk.replace(" to ", "-").replace(" TO ", "-")
        day = fallback_date
        times = re.findall(r"\d{1,2}:\d{2}\s*(?:[APap][Mm])?", normalised)
        date_match = re.search(r"\d{4}-\d{2}-\d{2}|\d{1,2}[-/]\d{1,2}[-/]\d{4}",
                               normalised)
        if date_match:
            parsed_day = parse_date(date_match.group(0))
            if parsed_day is None:
                problems.append(f"Unrecognised date in availability '{chunk}'")
                continue
            day = parsed_day
        if day is None:
            problems.append(f"Availability '{chunk}' has no date and no preferred date")
            continue
        if len(times) >= 2:
            start, end = parse_time(times[0]), parse_time(times[1])
            if start is None or end is None or end <= start:
                problems.append(f"Invalid time range in availability '{chunk}'")
                continue
        elif times:
            problems.append(f"Availability '{chunk}' needs a start and an end time")
            continue
        else:
            start, end = time(0, 0), time(23, 59)
        windows.append({"date": day.isoformat(),
                        "start_time": start.strftime("%H:%M"),
                        "end_time": end.strftime("%H:%M")})
    return windows, problems


class ExcelService:
    """Reads, validates and imports spreadsheet data."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.uploads = UploadRepository(db)
        self.candidates = CandidateRepository(db)
        self.faculty = FacultyRepository(db)
        self.availability = AvailabilityRepository(db)
        self.busy = BusySlotRepository(db)
        self.panels = PanelRepository(db)
        self.panel_members = PanelMemberRepository(db)
        self.metrics = MetricRepository(db)

    # --------------------------------------------------------------- file input
    def store_upload(self, *, filename: str, content: bytes,
                     content_type: str | None = None,
                     user_id: int | None = None) -> UploadedFile:
        suffix = Path(filename).suffix.lower()
        if suffix not in app_settings.ALLOWED_UPLOAD_EXTENSIONS:
            raise FileValidationError(
                f"Unsupported file type '{suffix}'. Allowed: "
                f"{', '.join(app_settings.ALLOWED_UPLOAD_EXTENSIONS)}")
        if len(content) > app_settings.MAX_UPLOAD_BYTES:
            raise FileValidationError(
                f"File is larger than {app_settings.MAX_UPLOAD_BYTES // (1024*1024)} MB")
        upload_dir = Path(app_settings.UPLOAD_DIR)
        upload_dir.mkdir(parents=True, exist_ok=True)
        record = self.uploads.create(
            original_filename=filename, stored_path="", content_type=content_type,
            size_bytes=len(content), status=UploadStatus.PENDING, uploaded_by=user_id)
        stored = upload_dir / f"{record.id}_{Path(filename).name}"
        stored.write_bytes(content)
        record.stored_path = str(stored)
        self.db.flush()
        return record

    def read_sheets(self, upload: UploadedFile) -> dict[str, pd.DataFrame]:
        path = Path(upload.stored_path)
        if not path.exists():
            raise NotFoundError(f"Stored file for upload {upload.id} is missing")
        try:
            if path.suffix.lower() == ".csv":
                return {"csv": pd.read_csv(path, dtype=object, keep_default_na=False,
                                           na_values=["", "NA", "N/A", "null"])}
            frames = pd.read_excel(path, sheet_name=None, dtype=object,
                                   engine="openpyxl" if path.suffix.lower() == ".xlsx"
                                   else None)
            return {name: frame for name, frame in frames.items()}
        except Exception as exc:  # pragma: no cover - pandas raises many types
            raise FileValidationError(f"Could not read the file: {exc}") from exc

    def metric_columns(self) -> list[str]:
        names: list[str] = []
        for metric in self.metrics.active():
            names.extend([metric.metric_key, metric.name, *(metric.column_aliases or [])])
        return names

    # --------------------------------------------------------------- validation
    def validate(self, upload: UploadedFile,
                 dataset_override: DatasetType | None = None) -> dict[str, Any]:
        sheets = self.read_sheets(upload)
        metric_columns = self.metric_columns()
        previews: list[dict[str, Any]] = []
        overall_errors: list[dict[str, Any]] = []

        for sheet_name, frame in sheets.items():
            frame = frame.dropna(how="all")
            columns = [str(c) for c in frame.columns]
            spec = (BY_TYPE[dataset_override] if dataset_override
                    else detect_dataset(sheet_name, columns, metric_columns))
            preview: dict[str, Any] = {
                "sheet_name": sheet_name,
                "detected_dataset": spec.dataset if spec else None,
                "columns": columns,
                "row_count": int(len(frame)),
                "sample_rows": self._sample_rows(frame),
                "missing_required_columns": [],
                "unmapped_columns": [],
                "errors": [],
                "warnings": [],
                "is_valid": True,
            }
            if spec is None:
                preview["is_valid"] = False
                preview["errors"].append({
                    "message": ("Could not recognise this sheet. Expected one of: "
                                + ", ".join(s.value for s in DatasetType))})
                previews.append(preview)
                overall_errors.extend(preview["errors"])
                continue

            mapping = spec.resolve(columns)
            missing = spec.missing_required(columns)
            preview["missing_required_columns"] = missing
            mapped_columns = set(mapping.values())
            if spec.dynamic_metric_columns:
                metric_map = self._resolve_metric_columns(columns)
                mapped_columns |= set(metric_map.values())
                if not metric_map:
                    preview["errors"].append({
                        "message": ("No evaluation metric columns found. Expected "
                                    "columns for: "
                                    + ", ".join(m.metric_key for m in
                                                self.metrics.active()))})
                    preview["is_valid"] = False
            preview["unmapped_columns"] = [c for c in columns if c not in mapped_columns]
            if missing:
                preview["is_valid"] = False
                preview["errors"].append({
                    "message": (f"Missing required column(s): {', '.join(missing)}. "
                                f"Accepted names: "
                                + "; ".join(f"{f.name} ({'/'.join(f.all_names)})"
                                            for f in spec.required_fields
                                            if f.name in missing))})
            # Row checks run even when a column is missing, so one round-trip
            # reports everything wrong with the file instead of just the header.
            row_errors, row_warnings = self._validate_rows(spec, frame, mapping)
            preview["errors"].extend(row_errors)
            preview["warnings"].extend(row_warnings)
            if row_errors:
                preview["is_valid"] = False
            previews.append(preview)
            overall_errors.extend(preview["errors"])

        is_valid = bool(previews) and all(p["is_valid"] for p in previews)
        upload.status = UploadStatus.VALIDATED if is_valid else UploadStatus.FAILED
        upload.errors = overall_errors[:200]
        upload.rows_total = sum(p["row_count"] for p in previews)
        upload.summary = {"sheets": [p["sheet_name"] for p in previews],
                          "datasets": [p["detected_dataset"].value if p["detected_dataset"]
                                       else None for p in previews]}
        detected = [p["detected_dataset"] for p in previews if p["detected_dataset"]]
        upload.dataset_type = detected[0] if len(set(detected)) == 1 else None
        self.db.flush()
        return {"upload_id": upload.id, "filename": upload.original_filename,
                "sheets": previews, "is_valid": is_valid,
                "errors": overall_errors[:50]}

    def _sample_rows(self, frame: pd.DataFrame, limit: int = 5) -> list[dict[str, Any]]:
        rows = []
        for _, row in frame.head(limit).iterrows():
            rows.append({str(k): (None if _clean(v) is None else str(_clean(v)))
                         for k, v in row.items()})
        return rows

    def _validate_rows(self, spec: DatasetSpec, frame: pd.DataFrame,
                       mapping: dict[str, str]
                       ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        errors: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        date_fields = {"date", "preferred_date", "evaluation_date",
                       "schedule_start_date", "schedule_end_date"}
        time_fields = {"start_time", "end_time", "preferred_time"}

        for index, row in frame.iterrows():
            excel_row = int(index) + 2  # header occupies row 1
            for field_name in spec.required_fields:
                column = mapping.get(field_name.name)
                if column and _clean(row.get(column)) is None:
                    errors.append({"row": excel_row, "column": column,
                                   "message": f"'{field_name.name}' is required"})
            for field_name, column in mapping.items():
                raw = row.get(column)
                if _clean(raw) is None:
                    continue
                if field_name in date_fields and parse_date(raw) is None:
                    errors.append({"row": excel_row, "column": column,
                                   "value": str(raw),
                                   "message": (f"'{raw}' is not a valid date "
                                               "(use YYYY-MM-DD)")})
                elif field_name in time_fields and parse_time(raw) is None:
                    errors.append({"row": excel_row, "column": column,
                                   "value": str(raw),
                                   "message": f"'{raw}' is not a valid time (use HH:MM)"})
            start_col, end_col = mapping.get("start_time"), mapping.get("end_time")
            if start_col and end_col:
                start, end = parse_time(row.get(start_col)), parse_time(row.get(end_col))
                if start and end and end <= start:
                    errors.append({"row": excel_row, "column": end_col,
                                   "message": "end_time must be after start_time"})
            if spec.dataset == DatasetType.CANDIDATES and mapping.get("availability"):
                _, problems = parse_availability_windows(
                    row.get(mapping["availability"]),
                    parse_date(row.get(mapping.get("preferred_date", ""), None)))
                warnings.extend({"row": excel_row, "column": mapping["availability"],
                                 "message": problem} for problem in problems)
            if spec.dataset == DatasetType.EVALUATIONS:
                for key, column in self._resolve_metric_columns(
                        [str(c) for c in frame.columns]).items():
                    value = _as_float(row.get(column))
                    if _clean(row.get(column)) is not None and value is None:
                        errors.append({"row": excel_row, "column": column,
                                       "value": str(row.get(column)),
                                       "message": f"Score for '{key}' must be numeric"})

        if spec.dataset == DatasetType.EVALUATIONS:
            warnings.extend(self._duplicate_evaluator_warnings(frame, mapping))
        return errors[:200], warnings[:200]

    def _duplicate_evaluator_warnings(self, frame: pd.DataFrame,
                                      mapping: dict[str, str]) -> list[dict[str, Any]]:
        """Flag rows that would silently overwrite each other on import.

        Evaluations are keyed by (candidate, interview, evaluator).  When the
        sheet has no usable `evaluator_id`, two teachers marking the same
        candidate collapse onto one row and the first teacher's marks are lost.
        """
        candidate_col = mapping.get("candidate_id")
        if not candidate_col:
            return []
        evaluator_col = mapping.get("evaluator_id")
        seen: dict[str, int] = {}
        clashing: dict[str, int] = {}
        for _, row in frame.iterrows():
            code = _as_str(row.get(candidate_col))
            if not code:
                continue
            evaluator = _as_str(row.get(evaluator_col)) if evaluator_col else None
            if evaluator:
                continue
            seen[code] = seen.get(code, 0) + 1
            if seen[code] > 1:
                clashing[code] = seen[code]
        if not clashing:
            return []
        listed = ", ".join(sorted(clashing)[:10])
        detail = ("no 'evaluator_id' column" if not evaluator_col
                  else "a blank 'evaluator_id'")
        return [{
            "row": None, "column": evaluator_col or candidate_col,
            "message": (f"{len(clashing)} candidate(s) appear on multiple rows with "
                        f"{detail} ({listed}). Only the last row per candidate will "
                        "be kept - add an evaluator_id column so each teacher's "
                        "marks are stored and compiled separately."),
        }]

    def _resolve_metric_columns(self, columns: list[str]) -> dict[str, str]:
        """metric_key -> column name, driven entirely by the metric configuration."""
        available = {normalise(c): c for c in columns}
        resolved: dict[str, str] = {}
        for metric in self.metrics.active():
            for alias in [metric.metric_key, metric.name, *(metric.column_aliases or [])]:
                key = normalise(alias)
                if key in available:
                    resolved[metric.metric_key] = available[key]
                    break
        return resolved

    # ------------------------------------------------------------------- import
    def import_upload(self, upload: UploadedFile,
                      dataset_override: DatasetType | None = None,
                      *, recalculate_free_slots: bool = True) -> dict[str, Any]:
        validation = self.validate(upload, dataset_override)
        if not validation["is_valid"]:
            upload.status = UploadStatus.FAILED
            self.db.flush()
            raise FileValidationError(
                "The file did not pass validation; no data was imported.",
                details=validation)

        sheets = self.read_sheets(upload)
        summaries: list[dict[str, Any]] = []
        touched_faculty: set[int] = set()

        importers = {
            DatasetType.CANDIDATES: self._import_candidates,
            DatasetType.FACULTY: self._import_faculty,
            DatasetType.FACULTY_AVAILABILITY: self._import_availability,
            DatasetType.FACULTY_BUSY_SLOTS: self._import_busy_slots,
            DatasetType.PANEL_GROUPS: self._import_panels,
            DatasetType.INTERVIEW_SETTINGS: self._import_settings,
            DatasetType.EVALUATIONS: self._import_evaluations,
        }
        # Faculty must exist before availability/panels reference them.
        order = [DatasetType.FACULTY, DatasetType.CANDIDATES,
                 DatasetType.FACULTY_AVAILABILITY, DatasetType.FACULTY_BUSY_SLOTS,
                 DatasetType.PANEL_GROUPS, DatasetType.INTERVIEW_SETTINGS,
                 DatasetType.EVALUATIONS]
        planned: list[tuple[DatasetType, str, pd.DataFrame]] = []
        for preview in validation["sheets"]:
            dataset = preview["detected_dataset"]
            frame = sheets[preview["sheet_name"]].dropna(how="all")
            planned.append((dataset, preview["sheet_name"], frame))
        planned.sort(key=lambda item: order.index(item[0]))

        for dataset, sheet_name, frame in planned:
            spec = BY_TYPE[dataset]
            mapping = spec.resolve([str(c) for c in frame.columns])
            summary = importers[dataset](frame, mapping, touched_faculty)
            summary.update({"dataset": dataset, "sheet_name": sheet_name,
                            "rows_total": int(len(frame))})
            summaries.append(summary)

        recalculated = 0
        if recalculate_free_slots and touched_faculty:
            stats = FreeSlotService(self.db).recalculate_for_faculty(touched_faculty)
            recalculated = stats["slots_created"]

        upload.status = UploadStatus.IMPORTED
        upload.rows_imported = sum(s["created"] + s["updated"] for s in summaries)
        upload.rows_failed = sum(s["failed"] for s in summaries)
        upload.summary = {"datasets": [s["dataset"].value for s in summaries],
                          "created": upload.rows_imported,
                          "failed": upload.rows_failed}
        self.db.flush()
        logger.info("Imported upload %s: %s row(s), %s failure(s)", upload.id,
                    upload.rows_imported, upload.rows_failed)
        return {
            "upload_id": upload.id,
            "filename": upload.original_filename,
            "status": upload.status,
            "summaries": summaries,
            "total_created": sum(s["created"] for s in summaries),
            "total_updated": sum(s["updated"] for s in summaries),
            "total_failed": sum(s["failed"] for s in summaries),
            "free_slots_recalculated": recalculated,
            "errors": [e for s in summaries for e in s["errors"]][:50],
        }

    # -------------------------------------------------------------- per dataset
    @staticmethod
    def _blank_summary() -> dict[str, Any]:
        return {"created": 0, "updated": 0, "failed": 0, "errors": [], "warnings": []}

    def _rows(self, frame: pd.DataFrame, mapping: dict[str, str]
              ) -> Iterable[tuple[int, dict[str, Any], Any]]:
        """Yield (spreadsheet row number, mapped values, raw row)."""
        for position, (_, row) in enumerate(frame.iterrows(), start=2):
            yield position, {field: row.get(column)
                             for field, column in mapping.items()}, row

    def _import_candidates(self, frame, mapping, touched) -> dict[str, Any]:
        summary = self._blank_summary()
        for excel_row, values, raw_row in self._rows(frame, mapping):
            code = _as_str(values.get("candidate_id"))
            name = _as_str(values.get("candidate_name"))
            if not code or not name:
                summary["failed"] += 1
                summary["errors"].append({"row": excel_row,
                                          "message": "candidate_id and candidate_name "
                                                     "are required"})
                continue
            preferred_date = parse_date(values.get("preferred_date"))
            windows, problems = parse_availability_windows(
                values.get("availability"), preferred_date)
            summary["warnings"].extend({"row": excel_row, "message": p}
                                       for p in problems)
            constraints_raw = _as_str(values.get("constraints"))
            payload = {
                "candidate_name": name,
                "email": _as_str(values.get("email")),
                "phone": _as_str(values.get("phone")),
                "department": _as_str(values.get("department")),
                "position": _as_str(values.get("position")),
                "preferred_date": preferred_date,
                "preferred_time": parse_time(values.get("preferred_time")),
                "preferred_panel_code": _as_str(values.get("preferred_panel")),
                "availability": windows,
                "constraints": ({"note": constraints_raw} if constraints_raw else {}),
                "priority": _as_int(values.get("priority")) or 0,
                "notes": _as_str(values.get("notes")),
            }
            existing = self.candidates.by_code(code)
            if existing:
                for key, value in payload.items():
                    setattr(existing, key, value)
                summary["updated"] += 1
            else:
                self.candidates.create(candidate_code=code, **payload)
                summary["created"] += 1
        self.db.flush()
        return summary

    def _import_faculty(self, frame, mapping, touched) -> dict[str, Any]:
        summary = self._blank_summary()
        for excel_row, values, raw_row in self._rows(frame, mapping):
            code = _as_str(values.get("faculty_id"))
            name = _as_str(values.get("faculty_name"))
            if not code or not name:
                summary["failed"] += 1
                summary["errors"].append({"row": excel_row,
                                          "message": "faculty_id and faculty_name "
                                                     "are required"})
                continue
            payload = {
                "faculty_name": name,
                "email": _as_str(values.get("email")),
                "phone": _as_str(values.get("phone")),
                "department": _as_str(values.get("department")),
                "designation": _as_str(values.get("designation")),
                "max_interviews_per_day": _as_int(values.get("max_interviews_per_day")),
            }
            existing = self.faculty.by_code(code)
            if existing:
                for key, value in payload.items():
                    setattr(existing, key, value)
                touched.add(existing.id)
                summary["updated"] += 1
            else:
                created = self.faculty.create(faculty_code=code, **payload)
                touched.add(created.id)
                summary["created"] += 1
        self.db.flush()
        return summary

    def _import_availability(self, frame, mapping, touched) -> dict[str, Any]:
        summary = self._blank_summary()
        for excel_row, values, raw_row in self._rows(frame, mapping):
            member = self._lookup_faculty(_as_str(values.get("faculty_id")))
            if member is None:
                summary["failed"] += 1
                summary["errors"].append({
                    "row": excel_row,
                    "message": f"Unknown faculty '{_as_str(values.get('faculty_id'))}'"})
                continue
            day = parse_date(values.get("date"))
            start = parse_time(values.get("start_time"))
            end = parse_time(values.get("end_time"))
            if not (day and start and end) or end <= start:
                summary["failed"] += 1
                summary["errors"].append({"row": excel_row,
                                          "message": "Invalid date or time range"})
                continue
            status_text = (_as_str(values.get("availability_status")) or "AVAILABLE")
            status = (AvailabilityStatus.UNAVAILABLE
                      if status_text.strip().upper() in {"UNAVAILABLE", "BUSY", "NO",
                                                         "FALSE", "0"}
                      else AvailabilityStatus.TENTATIVE
                      if status_text.strip().upper() in {"TENTATIVE", "MAYBE"}
                      else AvailabilityStatus.AVAILABLE)
            existing = self.availability.get_by(faculty_id=member.id, date=day,
                                                start_time=start, end_time=end)
            if existing:
                existing.availability_status = status
                existing.note = _as_str(values.get("note"))
                summary["updated"] += 1
            else:
                self.availability.create(
                    faculty_id=member.id, date=day, start_time=start, end_time=end,
                    availability_status=status, note=_as_str(values.get("note")))
                summary["created"] += 1
            touched.add(member.id)
        self.db.flush()
        return summary

    def _import_busy_slots(self, frame, mapping, touched) -> dict[str, Any]:
        summary = self._blank_summary()
        for excel_row, values, raw_row in self._rows(frame, mapping):
            member = self._lookup_faculty(_as_str(values.get("faculty_id")))
            if member is None:
                summary["failed"] += 1
                summary["errors"].append({
                    "row": excel_row,
                    "message": f"Unknown faculty '{_as_str(values.get('faculty_id'))}'"})
                continue
            day = parse_date(values.get("date"))
            start = parse_time(values.get("start_time"))
            end = parse_time(values.get("end_time"))
            if not (day and start and end) or end <= start:
                summary["failed"] += 1
                summary["errors"].append({"row": excel_row,
                                          "message": "Invalid date or time range"})
                continue
            duplicate = [b for b in self.busy.for_faculty(member.id, day)
                         if b.start_time == start and b.end_time == end
                         and b.interview_id is None]
            if duplicate:
                duplicate[0].reason = _as_str(values.get("reason"))
                summary["updated"] += 1
            else:
                self.busy.create(faculty_id=member.id, date=day, start_time=start,
                                 end_time=end, source=BusySlotSource.IMPORT,
                                 reason=_as_str(values.get("reason")))
                summary["created"] += 1
            touched.add(member.id)
        self.db.flush()
        return summary

    def _import_panels(self, frame, mapping, touched) -> dict[str, Any]:
        summary = self._blank_summary()
        for excel_row, values, raw_row in self._rows(frame, mapping):
            code = _as_str(values.get("panel_id"))
            name = _as_str(values.get("panel_name"))
            if not code or not name:
                summary["failed"] += 1
                summary["errors"].append({"row": excel_row,
                                          "message": "panel_id and panel_name "
                                                     "are required"})
                continue
            member_codes = split_list(values.get("faculty_members"))
            mandatory_codes = {c.lower() for c in
                               split_list(values.get("mandatory_members"))}
            members, unknown = [], []
            for member_code in member_codes:
                member = self._lookup_faculty(member_code)
                (members.append(member) if member else unknown.append(member_code))
            if unknown:
                summary["errors"].append({
                    "row": excel_row,
                    "message": f"Unknown faculty in panel: {', '.join(unknown)}"})
            if not members:
                summary["failed"] += 1
                summary["errors"].append({"row": excel_row,
                                          "message": "Panel has no known faculty "
                                                     "members"})
                continue
            minimum = _as_int(values.get("minimum_panel_size")) or min(2, len(members))
            maximum = _as_int(values.get("maximum_panel_size")) or len(members)
            payload = {
                "panel_name": name,
                "description": _as_str(values.get("description")),
                "department": _as_str(values.get("department")),
                "minimum_panel_size": max(1, min(minimum, len(members))),
                "maximum_panel_size": max(minimum, maximum),
            }
            panel = self.panels.by_code(code)
            if panel:
                for key, value in payload.items():
                    setattr(panel, key, value)
                self.panel_members.clear_panel(panel.id)
                summary["updated"] += 1
            else:
                panel = self.panels.create(panel_code=code, **payload)
                summary["created"] += 1
            for member in members:
                self.panel_members.create(
                    panel_id=panel.id, faculty_id=member.id,
                    is_mandatory=member.faculty_code.lower() in mandatory_codes)
                touched.add(member.id)
        self.db.flush()
        return summary

    def _import_settings(self, frame, mapping, touched) -> dict[str, Any]:
        summary = self._blank_summary()
        service = SettingsService(self.db)
        row = service.get()
        if frame.empty:
            return summary
        values = {field: frame.iloc[0].get(column) for field, column in mapping.items()}
        duration = _as_int(values.get("interview_duration"))
        if duration:
            row.interview_duration_minutes = duration
        break_minutes = _as_int(values.get("break_duration"))
        if break_minutes is not None:
            row.break_duration_minutes = break_minutes
        start = parse_time(values.get("start_time"))
        if start:
            row.day_start_time = start
        end = parse_time(values.get("end_time"))
        if end:
            row.day_end_time = end
        granularity = _as_int(values.get("slot_granularity"))
        if granularity:
            row.slot_granularity_minutes = granularity
        minimum = _as_int(values.get("min_panel_size"))
        if minimum:
            row.min_panel_size = minimum
        maximum = _as_int(values.get("max_panel_size"))
        if maximum:
            row.max_panel_size = max(maximum, row.min_panel_size)
        cap = _as_int(values.get("max_interviews_per_faculty_per_day"))
        if cap:
            row.max_interviews_per_faculty_per_day = cap
        weekends = _as_bool(values.get("allow_weekends"))
        if weekends is not None:
            row.allow_weekends = weekends
        start_date = parse_date(values.get("schedule_start_date"))
        end_date = parse_date(values.get("schedule_end_date"))
        range_text = _as_str(values.get("scheduling_date_range"))
        if range_text and not (start_date and end_date):
            found = re.findall(r"\d{4}-\d{2}-\d{2}|\d{1,2}[-/]\d{1,2}[-/]\d{4}",
                               range_text)
            if len(found) >= 2:
                start_date = start_date or parse_date(found[0])
                end_date = end_date or parse_date(found[1])
        if start_date:
            row.schedule_start_date = start_date
        if end_date:
            row.schedule_end_date = end_date
        self.db.flush()
        summary["updated"] = 1
        return summary

    def _import_evaluations(self, frame, mapping, touched) -> dict[str, Any]:
        from app.services.evaluation_service import EvaluationService

        summary = self._blank_summary()
        service = EvaluationService(self.db)
        metric_columns = self._resolve_metric_columns([str(c) for c in frame.columns])
        metrics = {m.metric_key: m for m in self.metrics.active()}
        for excel_row, values, raw_row in self._rows(frame, mapping):
            code = _as_str(values.get("candidate_id"))
            candidate = self.candidates.by_code(code) if code else None
            if candidate is None:
                summary["failed"] += 1
                summary["errors"].append({"row": excel_row,
                                          "message": f"Unknown candidate '{code}'"})
                continue
            scores: list[dict[str, Any]] = []
            out_of_range: list[str] = []
            for metric_key, column in metric_columns.items():
                score = _as_float(raw_row.get(column))
                if score is None:
                    continue
                metric = metrics[metric_key]
                # Same range rule the API path enforces in _resolve_scores().
                if not (metric.min_score <= score <= metric.max_score):
                    out_of_range.append(
                        f"'{metric.name}' score {score} is outside "
                        f"{metric.min_score}-{metric.max_score}")
                    continue
                scores.append({"metric_id": metric.id, "raw_score": score})
            if out_of_range:
                summary["failed"] += 1
                summary["errors"].append({"row": excel_row,
                                          "message": "; ".join(out_of_range)})
                continue
            if not scores:
                summary["failed"] += 1
                summary["errors"].append({"row": excel_row,
                                          "message": "No metric scores found in the row"})
                continue
            evaluator = self._lookup_faculty(_as_str(values.get("evaluator_id")))
            panel_code = _as_str(values.get("panel_id"))
            panel = self.panels.by_code(panel_code) if panel_code else None
            created = service.upsert_from_import(
                candidate_id=candidate.id,
                panel_id=panel.id if panel else None,
                evaluator_faculty_id=evaluator.id if evaluator else None,
                evaluation_date=parse_date(values.get("evaluation_date")),
                scores=scores,
                recommendation=_as_str(values.get("recommendation")),
                remarks=_as_str(values.get("remarks")),
            )
            summary["created" if created else "updated"] += 1
        self.db.flush()
        return summary

    # ------------------------------------------------------------------ helpers
    def _lookup_faculty(self, code: str | None) -> Faculty | None:
        if not code:
            return None
        member = self.faculty.by_code(code)
        if member:
            return member
        for candidate_member in self.faculty.all():
            if candidate_member.faculty_name.strip().lower() == code.strip().lower():
                return candidate_member
        return None
