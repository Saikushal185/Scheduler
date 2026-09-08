# Glossary

The terms this project uses in a specific way. Where a term maps to a table or
a module, the mapping is given.

**Availability** — the windows a faculty member has declared they *could* be
interviewing in. Input data (`faculty_availability`), imported from a
spreadsheet. Not the same as free slots.

**Busy slot** — a window inside an availability window that is already spoken
for by something outside this system: a lecture, a meeting, leave
(`faculty_busy_slots`). Input data.

**Free slot** — derived: `availability − (busy slots + booked interviews)`,
held in `faculty_free_slots` and recomputed by `FreeSlotService` whenever any
input changes. Never entered by hand, which is why cancelling an interview
genuinely returns the time.

**Domain** — in the constraint model, the set of feasible
`(panel, date, slot)` combinations for one candidate. Built in `domain.py`. An
empty domain is exactly why a candidate comes back unscheduled, and the reason
is reported.

**Constraint** — a rule evaluated against a candidate placement, carrying a
priority band. HARD constraints filter the domain; every other band contributes
a weighted score. Lives in `constraints.py` as data, never as a branch in a
router.

**Priority band** — HARD, HIGH, MEDIUM, LOW or FLEXIBLE, weighted 1000 / 100 /
50 / 20 / 5 by `PRIORITY_WEIGHTS`. Demoting a rule from HARD to HIGH turns "must
not" into "prefer not".

**Solver / algorithm** — `greedy`, `backtracking` or `optimized`. Three
interchangeable strategies over the same domain and the same objective:
`(candidates scheduled, total score)`, in that order.

**Run** — one execution of the scheduler (`scheduling_runs`), identified by a
run code. Carries its algorithm, status and per-candidate outcomes.

**Preview** — a run's initial status. It has produced a full proposed schedule
but created no interviews. Generating is therefore free of consequences.

**Confirm** — turning a PREVIEW into real rows in `interviews`. The point at
which a run affects anybody.

**Panel group** — the set of faculty an interview can be staffed from
(`panel_groups`), with a minimum and maximum size. Only active groups are
considered.

**Override** — a manual change to a confirmed interview. Passes the same
conflict check as the scheduler, so it is rejected with 409 unless forced.

**Force** — resubmitting a rejected override with `force: true`. Saves the
change and flags the interview `CONFLICT` rather than pretending the clash is
not there.

**Metric** — one dimension a candidate is scored on (`evaluation_metrics`),
with its own weight and score range. Seven by default, but they are
configuration: no metric name appears in the source.

**Evaluation** — one evaluator's set of marks for one candidate
(`evaluations` + `evaluation_scores`). Several evaluators are averaged per
metric before the configured weights are applied.

**Release** — making compiled results visible to candidates. Until then scores
exist but candidates cannot see them.

**Gating** — refusing a role access to an endpoint outright (403).

**Scoping** — letting every role call an endpoint but narrowing the rows to the
caller. The reason one page can serve all five roles.

**Column signature** — the set of column names that identifies which of the
seven dataset shapes a sheet is. Matching is by signature, not by sheet name or
position, and aliases are accepted.
