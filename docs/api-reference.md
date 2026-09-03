# API reference

Base URL: `http://localhost:8000/api/v1` (configurable via `API_V1_PREFIX`).
Interactive documentation is generated from the code at `/docs` (Swagger) and
`/redoc`; the OpenAPI schema is at `/openapi.json`.

Every endpoint requires `Authorization: Bearer <token>` except `POST /auth/login`,
`POST /auth/claim`, and the unversioned `GET /health` and `GET /`.

## Access column

| Mark | Who may call it |
| ---- | --------------- |
| **admin** | `ADMIN` only |
| **manager** | `ADMIN`, `COORDINATOR` |
| **staff** | `ADMIN`, `COORDINATOR`, `FACULTY` |
| **report** | `ADMIN`, `COORDINATOR`, `FACULTY`, `VIEWER` |
| **scoped** | any authenticated role; rows narrow to the caller (see [roles-and-permissions.md](roles-and-permissions.md)) |
| **public** | no token needed |

## Getting a token

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","password":"admin123"}' | jq -r .access_token)

curl -s http://localhost:8000/api/v1/analytics/summary \
  -H "Authorization: Bearer $TOKEN" | jq
```

## System

| Method | Path | Access | Purpose |
| ------ | ---- | ------ | ------- |
| GET | `/health` | public | liveness probe (version, environment) |
| GET | `/` | public | service metadata |

## Authentication and accounts — `/auth`

| Method | Path | Access | Purpose |
| ------ | ---- | ------ | ------- |
| POST | `/auth/login` | public | exchange credentials for a JWT |
| POST | `/auth/claim` | public | claim an account for a record already on file (code + email must match) |
| GET | `/auth/me` | any | the current user |
| POST | `/auth/change-password` | any | change your own password; clears `must_change_password` |
| GET | `/auth/users` | admin | list accounts |
| POST | `/auth/users` | admin | create an account |
| PUT | `/auth/users/{id}` | admin | update role, link, name, active flag |
| POST | `/auth/users/{id}/reset-password` | admin | issue a one-time password (returned once; not allowed on your own account) |
| DELETE | `/auth/users/{id}` | admin | deactivate (not allowed on your own account) |

## Data upload — `/uploads`

| Method | Path | Access | Purpose |
| ------ | ---- | ------ | ------- |
| GET | `/uploads/column-mappings` | manager | accepted columns and aliases for every sheet, including live metric columns |
| GET | `/uploads?limit=` | manager | recent uploads with their counts and errors |
| POST | `/uploads/validate` | manager | multipart upload; validate without importing |
| POST | `/uploads/import` | manager | multipart upload; validate and import |
| POST | `/uploads/{id}/import` | manager | import a previously validated upload |
| POST | `/uploads/provision-accounts` | manager | create logins for imported faculty (`faculty=true`) and candidates (`candidates=true`) |
| DELETE | `/uploads/{id}` | manager | delete an upload record |

`validate` and `import` accept an optional `dataset` form field to override
detection.

## Candidates — `/candidates`

| Method | Path | Access | Purpose |
| ------ | ---- | ------ | ------- |
| GET | `/candidates` | scoped | search by `q`, `status`, `department`, `skip`, `limit` (a student sees only themselves) |
| GET | `/candidates/{id}` | scoped | one candidate |
| POST | `/candidates` | manager | create |
| PUT | `/candidates/{id}` | manager | update |
| DELETE | `/candidates/{id}` | manager | delete |

## Faculty — `/faculty`

| Method | Path | Access | Purpose |
| ------ | ---- | ------ | ------- |
| GET | `/faculty` | staff | search by `q`, `department` |
| GET | `/faculty/departments` | staff | distinct departments |
| GET | `/faculty/{id}` | staff | one faculty member |
| GET | `/faculty/{id}/availability` | staff | that member's windows |
| POST/PUT/DELETE | `/faculty[/{id}]` | manager | create / update / delete |

### Availability — `/faculty-availability`

| Method | Path | Access | Purpose |
| ------ | ---- | ------ | ------- |
| GET | `/faculty-availability` | scoped | filter by `faculty_id`, `start_date`, `end_date` |
| POST | `/faculty-availability` | scoped¹ | declare a window |
| PUT | `/faculty-availability/{id}` | scoped¹ | update a window |
| DELETE | `/faculty-availability/{id}` | scoped¹ | remove a window |

### Busy slots — `/faculty-busy-slots`

| Method | Path | Access | Purpose |
| ------ | ---- | ------ | ------- |
| GET | `/faculty-busy-slots` | scoped | filter by `faculty_id`, date range |
| POST | `/faculty-busy-slots` | scoped¹ | block time |
| DELETE | `/faculty-busy-slots/{id}` | scoped¹ | unblock (refused for interview-owned blocks — cancel the interview) |

¹ A faculty caller may only touch their own rows; students are refused. Every
one of these writes triggers a free-slot recalculation for the faculty member.

## Free slots — `/free-slots`

| Method | Path | Access | Purpose |
| ------ | ---- | ------ | ------- |
| GET | `/free-slots` | scoped | calculated slots; `faculty_id`, date range, `min_minutes` |
| GET | `/free-slots/grouped` | scoped | grouped by faculty and day with total free minutes |
| GET | `/free-slots/timeline` | scoped | day diary of `BOOKED` / `BUSY` / `FREE` segments |
| POST | `/free-slots/recalculate` | manager | recompute for the given faculty and date range |

Students are refused on all four — faculty availability is not visible to them.

## Panel groups — `/panels`

| Method | Path | Access | Purpose |
| ------ | ---- | ------ | ------- |
| GET | `/panels` | staff | list with members |
| GET | `/panels/{id}` | staff | one panel |
| GET | `/panels/{id}/availability` | staff | windows where the panel can actually sit (`start_date`, `end_date`) |
| GET | `/panels/conflicts` | staff | faculty shared between panels |
| POST | `/panels/alternatives` | manager | alternative panels for a slot |
| POST/PUT/DELETE | `/panels[/{id}]` | manager | create / update (incl. membership) / delete |

## Automated scheduler — `/scheduling`

| Method | Path | Access | Purpose |
| ------ | ---- | ------ | ------- |
| GET | `/scheduling/algorithms` | manager | available strategies and their descriptions |
| POST | `/scheduling/generate` | manager | run the engine, store a **preview** (creates no interviews) |
| POST | `/scheduling/generate-and-confirm` | manager | run and apply in one call |
| GET | `/scheduling/runs?limit=` | manager | recent runs |
| GET | `/scheduling/runs/{id}` | manager | re-open a stored preview |
| POST | `/scheduling/runs/{id}/confirm` | manager | turn a preview into interviews (`replace_existing`, default true) |
| POST | `/scheduling/runs/{id}/discard` | manager | discard a preview |

`GenerateScheduleRequest` fields, all optional — anything omitted falls back to
the settings row:

```jsonc
{
  "start_date": "2026-03-02", "end_date": "2026-03-06",
  "algorithm": "optimized",              // greedy | backtracking | optimized
  "interview_duration_minutes": 30,
  "break_duration_minutes": 10,
  "slot_granularity_minutes": 15,
  "day_start_time": "09:00", "day_end_time": "17:00",
  "max_interviews_per_faculty_per_day": 12,
  "allow_weekends": false,
  "candidate_ids": [1, 2], "panel_ids": [1],   // restrict the run
  "keep_locked_interviews": true,
  "replace_existing": true                      // generate-and-confirm / confirm
}
```

The preview response carries `run_id`, `run_code`, `algorithm`, `scheduled`
(with names, times, score and per-constraint `priority_info`), `unscheduled`
(with a reason and details per candidate), `conflicts`, `total_score`,
`success_rate`, `duration_ms` and the engine `statistics`.

### Constraints — `/constraints`

| Method | Path | Access | Purpose |
| ------ | ---- | ------ | ------- |
| GET | `/constraints` | manager | list (seeds the defaults on first call) |
| POST | `/constraints` | manager | add a rule |
| PUT | `/constraints/{id}` | manager | change type, priority, scope, parameters, weight |
| DELETE | `/constraints/{id}` | manager | remove a rule |

## Interview schedule — `/interviews`

| Method | Path | Access | Purpose |
| ------ | ---- | ------ | ------- |
| GET | `/interviews` | scoped | filter by `status`, `candidate_id`, `panel_id`, `faculty_id`, `department`, date range |
| GET | `/interviews/calendar` | scoped | events for the day/week/table views |
| GET | `/interviews/conflicts` | staff | conflicts across the current schedule |
| GET | `/interviews/available-slots` | manager | bookable slots for `candidate_id` + `panel_id` (engine-validated and scored) |
| GET | `/interviews/{id}` | scoped | one interview (own/panel only) |
| GET | `/interviews/{id}/history` | scoped | full change history |
| POST | `/interviews` | manager | create manually (`force` to override conflicts) |
| PUT | `/interviews/{id}/reschedule` | manager | change time, panel or members |
| PUT | `/interviews/{id}/status` | manager | set status |
| PUT | `/interviews/{id}/lock` | manager | lock / unlock |
| POST | `/interviews/{id}/cancel` | manager | cancel (frees the faculty) |
| DELETE | `/interviews/{id}` | manager | delete |
| POST | `/interviews/faculty-unavailable` | scoped¹ | block time and flag the interviews it breaks |
| POST | `/interviews/{id}/confirm` | scoped | candidate confirms attendance |
| POST | `/interviews/{id}/change-request` | scoped | candidate asks for a different slot |

Manual write endpoints return `{interview, warnings, conflicts,
free_slots_recalculated}`. A conflicting change is rejected with 409 and the
conflict list unless `force: true`; a forced change is saved with status
`CONFLICT`.

### Change requests — `/interview-requests`

| Method | Path | Access | Purpose |
| ------ | ---- | ------ | ------- |
| GET | `/interview-requests?status=` | scoped | queue for administrators; own requests for a candidate (faculty are refused) |
| POST | `/interview-requests/{id}/decide` | manager | approve (reschedules through the normal path) or reject |

## Evaluation — `/evaluation-metrics` and `/evaluations`

| Method | Path | Access | Purpose |
| ------ | ---- | ------ | ------- |
| GET | `/evaluation-metrics?active_only=` | staff | the configurable metric set |
| POST | `/evaluation-metrics` | manager | add a metric |
| PUT | `/evaluation-metrics/{id}` | manager | rename, reweight, change the range |
| PUT | `/evaluation-metrics` | manager | set all weights at once (rescores every evaluation) |
| DELETE | `/evaluation-metrics/{id}` | manager | remove a metric |
| GET | `/evaluations` | scoped | list (`candidate_id`, `panel_id`); students are directed to `my-result` |
| GET | `/evaluations/rankings?limit=` | report | compiled candidate ranking |
| GET | `/evaluations/candidate/{id}/profile` | report | per-metric profile (radar chart data) |
| GET | `/evaluations/my-result` | scoped | a candidate's own compiled result, once published |
| GET | `/evaluations/{id}` | staff | one evaluation |
| POST | `/evaluations` | scoped | record one (a faculty submission is attributed to that member) |
| PUT | `/evaluations/{id}` | scoped | update scores or remarks |
| DELETE | `/evaluations/{id}` | scoped | delete |

## Analytics — `/analytics`

| Method | Path | Access | Purpose |
| ------ | ---- | ------ | ------- |
| GET | `/analytics/summary` | report | summary cards |
| GET | `/analytics/dashboard` | report | dashboard payload (summary, upcoming, activity, alerts, …) |
| GET | `/analytics/scheduling` | report | workload, utilisation, efficiency, run history |
| GET | `/analytics/evaluation` | report | metric averages, distribution, top candidates |
| GET | `/analytics/report` | report | everything in one document |

## Settings — `/settings`

| Method | Path | Access | Purpose |
| ------ | ---- | ------ | ------- |
| GET | `/settings` | staff | global interview configuration |
| PUT | `/settings` | manager | update it (including `results_published`) |

## Errors

All failures share one envelope:

```json
{ "error": "validation_error", "message": "The request payload is invalid",
  "details": [{ "field": "email", "message": "value is not a valid email address" }] }
```

See [architecture.md](architecture.md#error-model) for the status/code table.
