# Roadmap

What is deliberately not built yet, and what I would do about it. Nothing here
is required for the system to do its job — these are the edges I hit while
building it.

## Scheduling

**Incremental rescheduling.** Today a run schedules the whole cohort. When one
faculty member withdraws late, the honest options are a manual override or a
full re-run. A repair mode that holds every satisfied placement fixed and
re-solves only the affected candidates would be a better answer, and the domain
model already supports it — it is a solver entry point, not a redesign.

**Explaining a rejection positively.** An unscheduled candidate is told why its
domain was empty. It is not told what would have to change to fill it. Relaxing
one constraint at a time and reporting the cheapest relaxation that works would
turn "no free faculty in the window" into "extend to the 19th, or drop the
minimum panel size to 2".

**Fairness across faculty.** The daily cap stops anyone being overloaded on one
day, but nothing balances load across the whole run. A soft constraint on
deviation from the mean would spread it without making the problem harder.

## Evaluation

**Evaluator calibration.** Marks are averaged per metric, which assumes every
evaluator uses the scale the same way. They do not. Reporting per-evaluator
bias against the cohort mean would at least make it visible, even if the
compiled score stays a plain average.

**Partial submissions.** An evaluation is currently all-or-nothing per
evaluator. Saving a draft between candidates would match how panels actually
work.

## Operations

**Migrations.** Schema changes rely on recreating tables. Alembic before the
first deployment that holds data anyone cares about.

**Background jobs.** Free-slot recalculation and scheduling both run in the
request. They are fast enough at the sizes tested, but a large import blocks a
worker. Moving both behind a queue is the obvious fix, and the services are
already free of request state.

**Audit beyond schedule history.** Interview changes are recorded. Settings
changes, metric edits and result releases are not, and those are exactly the
actions someone will later want to attribute.

## Frontend

**Offline-tolerant boards.** TanStack Query invalidates after every mutation,
which is correct but chatty on a bad connection. Optimistic updates on the
override path would help most.

**Accessibility pass.** Radix gives the primitives correct behaviour; the
custom timeline and schedule grid have not been tested with a screen reader.
