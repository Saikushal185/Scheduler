# Architecture

## Stack

| Layer     | Technology                                                        |
| --------- | ----------------------------------------------------------------- |
| Backend   | FastAPI 0.115, SQLAlchemy 2.0 (typed `Mapped[...]`), Pydantic v2  |
| Database  | PostgreSQL 16 in Docker; SQLite accepted for zero-infra local runs |
| Ingestion | pandas + openpyxl                                                 |
| Auth      | JWT (`python-jose`), bcrypt via `passlib`                         |
| Frontend  | Next.js 16 App Router, React 19, TypeScript, Tailwind v4           |
| Data layer| TanStack Query v5; FullCalendar for calendars; Recharts for charts |
| Tests     | pytest (engine unit tests + API integration tests)                |

## Backend layers

Requests travel outside-in; each layer only knows the one below it.

```
HTTP request
   │
   ├─ app/main.py               app assembly, CORS, exception handlers, lifespan
   ├─ app/api/deps.py           auth, role gates, Scope construction, DB session
   ├─ app/api/v1/routers/*.py   HTTP shape only: validate, delegate, serialise
   ├─ app/services/*.py         business rules and orchestration
   ├─ app/repositories/*.py     query helpers over SQLAlchemy
   └─ app/models/*.py           tables
```

Off to the side and deliberately isolated:

```
app/scheduling/    the solving engine — imports no FastAPI and no Session
app/utils/         interval arithmetic and spreadsheet-tolerant parsing
app/core/          config, database engine, security, permissions, exceptions
```

`app/scheduling` touching neither the database nor the web framework is what
makes `tests/test_scheduler.py` able to build a whole problem instance in memory
and assert on the result. `SchedulingService` is the only bridge: it turns rows
into `SchedulingContext` dataclasses and writes the `SchedulingResult` back.

### Where the rules live

Business rules sit in services, not routers, so an alternative entry point
cannot bypass them:

- ownership assertions (`assert_faculty_owns`, `assert_candidate_owns`) are
  called from the service layer, which is why the Excel importer is subject to
  the same checks as an HTTP call;
- approving a candidate's reschedule request routes through the ordinary
  `InterviewService.reschedule()`, so history, conflict re-checks and free-slot
  recalculation behave exactly as an administrator edit would;
- a faculty member's evaluation submission is re-attributed to that faculty
  member in `EvaluationService._apply_evaluator_scope`, so marks cannot be filed
  under a colleague's name.

## Startup and bootstrap

`lifespan` in `app/main.py` configures logging, runs
`Base.metadata.create_all()` and then `bootstrap_database()`, which is
idempotent and seeds:

1. the bootstrap administrator (`FIRST_ADMIN_EMAIL` / `FIRST_ADMIN_PASSWORD`);
2. the singleton `interview_settings` row from the `DEFAULT_*` configuration;
3. the seven `evaluation_metrics` rows;
4. the eleven default `scheduling_constraints` rows.

There is no migration tool in the project — schema changes are applied by
`create_all` on a fresh database, so a structural change to a model needs the
database recreated (or a hand-written migration).

## Error model

Every expected failure is an `AppError` subclass in `app/core/exceptions.py` and
maps to one HTTP status with one JSON envelope:

```json
{ "error": "conflict", "message": "The requested change conflicts with the schedule",
  "details": ["Faculty 7 has overlapping interviews on 2026-03-02: 09:00-09:30 and 09:15-09:45"] }
```

| Exception                | Status | `error` code            |
| ------------------------ | ------ | ----------------------- |
| `AuthError`              | 401    | `unauthorized`          |
| `PermissionError_`       | 403    | `forbidden`             |
| `NotFoundError`          | 404    | `not_found`             |
| `ConflictError`          | 409    | `conflict`              |
| `ValidationError`        | 422    | `validation_error`      |
| `FileValidationError`    | 422    | `file_validation_error` |
| `SchedulingError`        | 400    | `scheduling_error`      |

Two framework failures are normalised into the same shape: a Pydantic
`RequestValidationError` becomes a 422 with a `details` array of
`{field, message}`, and a SQLAlchemy `IntegrityError` becomes a 409
`integrity_error`. The frontend's `ApiError.detailLines` flattens `details` for
display, so a backend `details` array is what the user actually reads.

## Sessions and transactions

`get_db()` yields a request-scoped session and commits on success, rolls back on
any exception. Services therefore call `db.flush()` — never `commit()` — and a
failed request leaves nothing half-written. Scripts use the equivalent
`session_scope()` context manager. On SQLite a `PRAGMA foreign_keys=ON` hook is
installed on connect, because SQLite otherwise ignores foreign keys.

## Derived data and its invalidation

Two tables are computed rather than entered:

| Table                 | Derived from                                            | Recomputed by                                   |
| --------------------- | ------------------------------------------------------- | ----------------------------------------------- |
| `faculty_busy_slots` (source `INTERVIEW`) | active interviews × their panel members  | `FreeSlotService.sync_interview_busy_slots()`   |
| `faculty_free_slots`  | availability − (unavailable windows + busy slots)        | `FreeSlotService.recalculate()`                 |

Every write path that can affect them triggers a recalculation: availability and
busy-slot CRUD, manual interview create/reschedule/status/cancel/delete, marking
a faculty member unavailable, and confirming a scheduling run. This is why the
free-slot table can be treated as authoritative by the engine.

## Request lifecycle, worked example

`POST /api/v1/scheduling/generate`:

1. `deps.get_current_user` decodes the bearer token and loads the user;
   `require_roles(ADMIN, COORDINATOR)` gates the endpoint.
2. `SchedulingService.build_context()` resolves the date window, recalculates
   free slots for it, and materialises candidates, faculty, panels and
   constraints into `app/scheduling` dataclasses.
3. `SchedulingEngine.run()` generates domains, drops hard violations, pre-scores
   the survivors, solves with the requested algorithm, then re-verifies the
   finished schedule with `detect_conflicts()`.
4. The result is persisted as a `SchedulingRun` with `status=PREVIEW` — no
   interviews exist yet — and serialised for the UI with candidate, panel and
   faculty names resolved.
5. `POST /scheduling/runs/{id}/confirm` turns the stored assignments into
   `interviews` + `interview_panel_members`, writes an `AUTO_SCHEDULED` history
   row per interview, updates candidate statuses, and recalculates free slots.
