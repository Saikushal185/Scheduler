# Data model

All tables use SQLAlchemy 2.0 declarative mapping (`app/models/`). Enums are
stored as strings (`native_enum=False`) so the same schema works on PostgreSQL
and SQLite. Most tables carry `created_at` / `updated_at` from `TimestampMixin`.

## Map

```
users ──┬─ faculty_id ──▶ faculty
        └─ candidate_id ─▶ candidates

faculty ─┬─▶ faculty_availability      declared working windows
         ├─▶ faculty_busy_slots        commitments (incl. mirrored interviews)
         ├─▶ faculty_free_slots        DERIVED: availability − busy
         └─▶ panel_members ──▶ panel_groups

candidates ─┬─▶ interviews ─┬─▶ interview_panel_members ──▶ faculty
            │               ├─▶ interview_schedule_history
            │               ├─▶ interview_change_requests
            │               └─── run_id ──▶ scheduling_runs
            └─▶ evaluations ──▶ evaluation_scores ──▶ evaluation_metrics

scheduling_constraints    configurable rules with priority bands
interview_settings        singleton (id = 1) global configuration
uploaded_files            ingestion audit trail
```

## People and accounts

### `users`
A login account. `email` is unique; `hashed_password` is bcrypt.

| Column | Notes |
| ------ | ----- |
| `role` | `ADMIN` / `COORDINATOR` / `FACULTY` / `STUDENT` / `VIEWER` |
| `faculty_id`, `candidate_id` | unique FKs — the link every permission scope is derived from. Required for `FACULTY` / `STUDENT`, forbidden for the other three roles. |
| `must_change_password` | set when a password was *issued* to the user; blocks the app until replaced |
| `password_issued_at`, `password_changed_at` | password provenance. A bcrypt hash can never be shown, so these two dates are what the Users page reports: whether the account still holds the temporary password that was handed out, or the user has since set their own. |
| `is_active` | deactivation instead of deletion; an inactive account fails auth |

### `faculty`
`faculty_code` (unique business key), name, email, department, designation,
`max_interviews_per_day` (overrides the global cap when set), `is_active`.

### `candidates`
`candidate_code` (unique), name, contact, department, position, plus the
scheduling inputs:

| Column | Meaning |
| ------ | ------- |
| `preferred_date`, `preferred_time`, `preferred_panel_code` | soft preferences, scored not enforced (unless the matching constraint is set to `HARD`) |
| `availability` (JSON) | parsed windows `[{"date","start_time","end_time"}, …]`. **An empty list means "always available"**; a non-empty list is a hard filter. |
| `constraints` (JSON) | free-form, captured from the sheet. `{"required_panel": "P1"}` is read by the engine. |
| `priority` | integer tie-break — higher goes first in the solver's ordering |
| `status` | `PENDING` / `SCHEDULED` / `UNSCHEDULED` / `COMPLETED` / `WITHDRAWN` |

## Availability

### `faculty_availability`
One declared window: `(faculty_id, date, start_time, end_time)` — unique
together — with `availability_status` `AVAILABLE` / `UNAVAILABLE` / `TENTATIVE`.
Only `AVAILABLE` rows create free time; `UNAVAILABLE` rows subtract from it.

### `faculty_busy_slots`
Time that cannot be booked, with `source`:

| Source | Origin |
| ------ | ------ |
| `MANUAL` | someone blocked the diary in the UI |
| `IMPORT` | came from a busy-slots sheet |
| `INTERVIEW` | mirrored from a booked interview; carries `interview_id` |
| `EXTERNAL` | reserved for an external calendar feed |

`INTERVIEW` rows are managed by `sync_interview_busy_slots()` — created for
active interviews, deleted when the interview is cancelled or removed. A busy
slot with an `interview_id` cannot be deleted directly; cancel the interview.

### `faculty_free_slots` (derived)
`(faculty_id, date, start_time, end_time, duration_minutes, computed_at)`.
Written only by `FreeSlotService`; never edited. See
[scheduling-engine.md](scheduling-engine.md#free-slot-calculation).

## Panels

`panel_groups`: `panel_code` (unique), name, department, `minimum_panel_size`,
`maximum_panel_size`, `is_active`.

`panel_members`: `(panel_id, faculty_id)` unique, plus `role` and
`is_mandatory`. A mandatory member must be free for a slot or the slot is
dropped from the domain entirely.

## Scheduling

### `scheduling_runs`
One engine execution. `run_code`, `algorithm`, `status`
(`PREVIEW` / `CONFIRMED` / `DISCARDED`), the `parameters` used, the full
`result` JSON (assignments, unscheduled with reasons, conflicts, statistics),
counts, `total_score`, `duration_ms`, `created_by`. A preview is re-openable
later because the whole result is stored.

### `interviews`
| Column | Notes |
| ------ | ----- |
| `schedule_code` | unique `INT-XXXXXXXX` business key |
| `date`, `start_time`, `end_time`, `duration_minutes` | nullable — an interview row can exist unplaced |
| `status` | `SCHEDULED` / `PENDING` / `CONFLICT` / `UNSCHEDULED` / `RESCHEDULED` / `CANCELLED` / `COMPLETED` |
| `scheduling_score` | the optimiser score of this placement |
| `priority_info` (JSON) | per-constraint outcome: `[{type, priority, satisfied, score, detail}]` — the audit trail for *why* this slot |
| `is_locked` | protects the interview from being replaced by the next run, and from edits without `force` |
| `is_manual` | set by any manual create/reschedule |
| `candidate_confirmed_at` | stamped when the candidate confirms attendance from their own login |
| `run_id` | the run that produced it, if automated |

### `interview_panel_members`
`(interview_id, faculty_id)` unique — the faculty *actually* assigned, which may
be a subset of the panel's membership.

### `interview_schedule_history`
Append-only. `action` (`CREATED`, `AUTO_SCHEDULED`, `RESCHEDULED`,
`PANEL_CHANGED`, `STATUS_CHANGED`, `CANCELLED`, `LOCKED`, `UNLOCKED`,
`COMPLETED`, `MANUAL_OVERRIDE`, `CONFIRMED`, `CHANGE_REQUESTED`),
`previous_state` and `new_state` snapshots, `reason`, `warnings`,
`performed_by`. `HistoryService.snapshot()` defines the snapshot shape: date,
times, panel, faculty ids, status, lock, location.

### `interview_change_requests`
A candidate asking for a different slot: `requested_date`,
`requested_start_time`, `reason`, `status`
(`PENDING` / `APPROVED` / `REJECTED` / `WITHDRAWN`), `decision_note`,
`decided_by`, `decided_at`. Only one `PENDING` request per interview.

### `scheduling_constraints`
A configurable rule: `constraint_type` (13 types), `priority`
(`HARD` / `HIGH` / `MEDIUM` / `LOW` / `FLEXIBLE`), optional `scope`
(`{"candidate_id": 3}`, `{"department": "CSE"}`), rule-specific `parameters`
(`{"max_per_day": 6}`, `{"tolerance_days": 5}`), `weight_multiplier`,
`is_active`, `display_order`.

## Evaluation

### `evaluation_metrics`
`metric_key` (unique), `name`, `description`, `weight`, `min_score`,
`max_score`, `display_order`, `is_active`, `column_aliases` (extra column
headers accepted on import). Seven rows are seeded; the count, names, weights
and ranges are all editable at runtime and no name is referenced in code.

### `evaluations`
Unique on `(candidate_id, interview_id, evaluator_faculty_id)` — one submission
per evaluator per interview, which is what makes several teachers scoring the
same candidate a normal case. Stores `overall_score`, `normalized_score`,
`max_possible_score`, `strongest_metric_id`, `weakest_metric_id`,
`recommendation`, `remarks`.

### `evaluation_scores`
Unique on `(evaluation_id, metric_id)`: `raw_score` as entered, plus the derived
`normalized_score` and `weighted_score` and an optional per-metric `comment`.

## Configuration and ingestion

### `interview_settings` (singleton, `id = 1`)
Interview and break duration, day start/end, schedule start/end date, slot
granularity, min/max panel size, max interviews per faculty per day,
`allow_weekends`, `default_algorithm`, `organisation_name`, and
`results_published` / `results_published_at` — students see their marks only
once an administrator releases them, so an in-progress entry is never visible.

### `uploaded_files`
Ingestion audit: original filename, stored path, size, detected
`dataset_type`, `status` (`PENDING` / `VALIDATED` / `IMPORTED` / `FAILED`),
row counts, and the `errors` / `warnings` / `summary` JSON that the upload page
renders.
