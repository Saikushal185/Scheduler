# Data import

`.xlsx`, `.xls` and `.csv` are accepted, up to `MAX_UPLOAD_BYTES` (25 MB by
default). A multi-sheet workbook is processed sheet by sheet — one upload can
carry the whole dataset.

```
store file → read sheets → detect dataset → resolve columns
           → validate rows → import → recalculate free slots
```

## Sheets are matched by their columns, not their position

Each dataset has a `DatasetSpec` in `app/services/column_mappings.py` listing its
fields, each with aliases. Detection scores every spec against the sheet:
required fields present, how many optional fields matched, and a bonus when the
sheet *name* matches a known alias. The best score wins.

Column names are normalised before comparison — lower-cased with non-alphanumeric
runs collapsed to `_` — so `Faculty ID`, `faculty code`, `FacultyId` and
`FACULTY_ID` are the same column. `GET /uploads/column-mappings` returns the
live list of required columns, optional columns and every accepted alias.

## The seven datasets

### Candidates
Sheet aliases: `candidates`, `candidate`, `applicants`, `students`.

| Field | Required | Common aliases |
| ----- | -------- | -------------- |
| `candidate_id` | yes | `candidate_code`, `id`, `code`, `roll_no`, `application_id` |
| `candidate_name` | yes | `name`, `full_name`, `candidate` |
| `email`, `phone`, `department`, `position` | no | `dept`, `branch`, `discipline`, `program`, `applied_for`, … |
| `preferred_date`, `preferred_time` | no | `pref_date`, `preferred_interview_date`, `date`, `time` |
| `preferred_panel` | no | `panel`, `preferred_panel_code` |
| `availability` | no | `available_slots`, `availability_windows`, `free_time` |
| `priority` | no | `weight`, `rank_priority` |
| `constraints`, `notes` | no | `special_requirements`, `remarks`, `comments` |

`availability` is free text parsed into structured windows. Entries are
separated by `;` or newlines, and each accepts:

```
2026-03-02 09:00-12:00      an explicit date and range
2026-03-02 09:00 to 12:00   "to" instead of a dash
09:00-12:00                 range only — uses the candidate's preferred date
2026-03-02                  date only — the whole day
```

Anything unparseable becomes a row-level **warning** naming the offending text,
not a failed import. Leave the column blank for "available whenever" — an empty
list means unrestricted, while a populated one is a hard filter.

### Faculty
Aliases: `faculty`, `faculties`, `interviewers`, `panel_members`, `staff`.
Required: `faculty_id`, `faculty_name`. Optional: `department`, `email`, `phone`,
`designation`, `max_interviews_per_day` (`max_per_day`, `daily_limit`).

### Faculty availability
Aliases: `faculty_availability`, `availability`, `faculty_slots`,
`available_slots`. Required: `faculty_id`, `date`, `start_time`, `end_time`
(`from`/`to`, `start`/`end`, `begin`/`finish`). Optional: `availability_status`,
`note`.

### Faculty busy slots
Aliases: `faculty_busy_slots`, `busy_slots`, `busy`, `engagements`,
`commitments`. Required: `faculty_id`, `date`, `start_time`, `end_time`.
Optional: `reason` (`activity`, `remarks`).

### Panel groups
Aliases: `panel_groups`, `panels`, `panel`, `interview_panels`. Required:
`panel_id`, `panel_name`, `faculty_members` (a delimited list of faculty codes).
Optional: `minimum_panel_size`, `maximum_panel_size`, `department`,
`description`, `mandatory_members` (`chair`, `required_members`).

Member lists accept `,` `;` and `|` as separators — `F001, F002; F003` and
`F001|F002` both work.

### Interview settings
Aliases: `interview_settings`, `settings`, `configuration`, `config`. Required:
`interview_duration`. Optional: `break_duration`, `start_time`/`end_time`
(day bounds), `scheduling_date_range` or `schedule_start_date` /
`schedule_end_date`, `slot_granularity`, `min_panel_size`, `max_panel_size`,
`max_interviews_per_faculty_per_day`, `allow_weekends`. Importing this sheet
updates the singleton settings row.

### Evaluations
Aliases: `evaluation`, `evaluations`, `scores`, `results`, `marks`. Required:
`candidate_id`. Optional: `interview_id` (`schedule_code`), `panel_id`,
`evaluator_id` (`faculty_id`), `evaluation_date`, `recommendation`
(`decision`, `verdict`), `remarks`.

Metric columns are **dynamic**: they are resolved at runtime from
`evaluation_metrics` (by key, name or configured `column_aliases`), so a renamed
or newly added metric is importable immediately without touching code. A sheet
carrying recognisable metric columns also scores higher during dataset
detection.

## Spreadsheet-tolerant parsing

`app/utils/timeutils.py` accepts what spreadsheets actually contain:

- **times**: `09:00`, `9:00 AM`, `09.00`, `0900`, real `time`/`datetime` cells,
  and Excel serial fractions (`0.375` → 09:00);
- **dates**: ISO, `dd-mm-yyyy`, `dd/mm/yyyy`, `mm/dd/yyyy`, `yyyy/mm/dd`,
  `dd-Mon-yyyy`, `dd.mm.yyyy`, plus datetimes (time part dropped);
- blanks, `NaN`, `NaT`, `None`, `-` are all treated as empty.

## Validate, then import

| Endpoint | Effect |
| -------- | ------ |
| `POST /uploads/validate` | stores and checks the file, writes nothing to the domain tables |
| `POST /uploads/import` | stores, checks and imports in one call |
| `POST /uploads/{id}/import` | imports a previously validated upload |

Validation reports, per sheet: the detected dataset, missing required columns,
the resolved column mapping, sample rows, and row-level errors and warnings
naming the sheet, row number, column and value. Duplicate-evaluator rows are
flagged as warnings rather than errors. `uploaded_files` keeps the counts and
the error payload, so the Uploads list is a full ingestion audit trail.

Imports are **upsert by business key** — `candidate_code`, `faculty_code`,
`panel_code` — so re-importing a corrected sheet updates rows instead of
duplicating them. Availability and busy-slot changes trigger a free-slot
recalculation for the faculty touched.

## After the import

`POST /uploads/provision-accounts` creates one login per imported faculty member
and candidate that does not already have one, using the email already in the
sheet, and returns the generated one-time passwords once. Existing accounts are
never touched. See [roles-and-permissions.md](roles-and-permissions.md#account-lifecycle).

## Sample data

`samples/` holds `interview_data.xlsx` (a full multi-sheet workbook),
`evaluations.xlsx`, `candidates.csv` and `invalid_candidates.xlsx` — the last
one deliberately broken, to see the row-level error reporting. Regenerate them
with `python -m scripts.generate_samples`; `python -m scripts.seed --reset`
imports them and runs a real scheduling pass.
