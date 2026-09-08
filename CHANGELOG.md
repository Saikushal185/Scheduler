# Changelog

Notable changes, newest first. Written from the commit history rather than
maintained alongside it, so the dates are the dates the work landed.

## Unreleased

### Documentation
- FAQ and glossary chapters, both wired into the docs index and the Word build.
- Contributing notes: setup, the two checks that gate a change, and the
  routers-parse/services-decide layering rule.
- Security notes: what the app does today, and the checklist of dev defaults
  that must not reach production.
- Tech stack table with pinned versions and the reason each dependency is there.
- Corrected the test count (103, not 90) and split it per file.
- Corrected the documented default algorithm — `optimized`, not `backtracking`.

## 1.0.0

The full system, in the order it was built.

### Scheduling
- Constraint-based engine: candidates are variables, domains are feasible
  `(panel, date, slot)` combinations, HARD rules filter and every other band
  scores.
- Three interchangeable solvers — `greedy`, `backtracking` and `optimized` —
  over one domain and one objective, `(candidates scheduled, total score)`.
- The optimised solver keeps improving its answer rather than stopping at the
  first complete assignment.
- Domain construction cost cut, which is what makes larger instances practical.
- Runs are stored as a PREVIEW and create no interviews until confirmed.
- Every run reports what it traded away, and every unscheduled candidate
  carries the reason its domain was empty.
- Manual booking and rescheduling from the schedule view, through the same
  conflict check; a forced change is saved and flagged `CONFLICT`.

### Free slots
- `availability − (busy slots + booked interviews)`, recomputed whenever an
  input changes, so a cancellation genuinely returns the time.
- A faculty day exposed as booked, busy and free segments, drawn as a timeline
  above the availability tables and on the free-slots page.

### Evaluation
- Metrics are rows with their own weights and ranges — seven by default, no
  metric name in the source.
- Marks from several evaluators averaged per metric, then compiled with the
  configured weights.
- Results held back until an admin releases them, from the settings page.

### Access control
- Five roles, protected two ways: gating for endpoints a role may not touch,
  scoping for shared endpoints that narrow to the caller.
- User administration, bulk account provisioning, and account claiming.
- First-login users are sent to set their own password; password provenance is
  tracked and shown on the users page.
- Navigation routes people to what their role can actually reach.

### Data import
- Seven dataset shapes matched by column signature, not sheet position, with
  field aliases.
- Row-level validation naming sheet, row, column and value.
- AM/PM parsing fixed for times coming out of spreadsheets.
- List settings read from comma-separated environment values.

### Frontend
- Next.js dashboard: schedule board coloured by what each block is doing,
  faculty/candidate/admin account pages, analytics.

### Project
- Docker Compose, setup and run scripts for macOS/Linux and Windows.
- 103 tests across interval algebra, the scheduling guarantees and the full
  HTTP workflow.
- Reference documentation under `docs/`, plus a generated Word edition.
