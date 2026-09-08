# AcademiSync — Documentation

Written and maintained by **Sai Kushal** ([@Saikushal185](https://github.com/Saikushal185)).

Automated interview scheduling and evaluation management. A FastAPI + SQLAlchemy
backend drives a constraint-based scheduling engine; a Next.js dashboard exposes
the whole workflow to five different kinds of user.

The pipeline, end to end:

```
Excel/CSV upload → validation → database → faculty availability
   → free-slot calculation → panel assignment → constraint-based scheduling
   → conflict detection → schedule views → manual override
   → evaluation → compiled results → analytics & reports
```

## Where to start

| If you want to…                                     | Read                                             |
| --------------------------------------------------- | ------------------------------------------------ |
| Get the stack running                               | [operations.md](operations.md)                   |
| Understand how the code is organised                | [architecture.md](architecture.md)               |
| Know what the tables hold                           | [data-model.md](data-model.md)                   |
| Know who can see and do what                        | [roles-and-permissions.md](roles-and-permissions.md) |
| Understand how a schedule is produced               | [scheduling-engine.md](scheduling-engine.md)     |
| Understand scoring, rankings and dashboards         | [evaluation-and-analytics.md](evaluation-and-analytics.md) |
| Prepare a spreadsheet the importer accepts          | [data-import.md](data-import.md)                 |
| Call the HTTP API                                   | [api-reference.md](api-reference.md)             |
| Work on the dashboard                               | [frontend.md](frontend.md)                       |
| Get a quick answer to a common question             | [faq.md](faq.md)                                 |
| Check what a term means here                        | [glossary.md](glossary.md)                       |
| See what is not built yet                           | [roadmap.md](roadmap.md)                         |

A Word edition of this whole reference is built from these files:

```bash
python3 docs/build-docx.py      # -> docs/AcademiSync-Documentation.docx
```

The Markdown files are the source; the `.docx` is a generated artefact, so
regenerate it after editing a chapter (needs `pandoc`).

The repository [README](../README.md) is the short tour; these documents are the
reference. `project.md` holds the original requirement specification and
`torun.txt` a manual walkthrough script. [CONTRIBUTING.md](../CONTRIBUTING.md)
covers the development loop and [SECURITY.md](../SECURITY.md) the deploy
checklist.

## The system in one page

**Ingestion.** Spreadsheets are matched to one of seven dataset shapes by their
column signature, not by sheet position. Every field accepts aliases, so
real-world files import without being reshaped. Validation is row-level: each
problem names the sheet, row, column and value.

**Free slots are derived, never entered.** `availability − (busy slots + booked
interviews)` is recomputed by `FreeSlotService` whenever any input changes, so
the scheduler always reads a current picture and a cancellation genuinely frees
the faculty member up again.

**Scheduling is a constraint problem.** Candidates are variables, their domains
are feasible `(panel, date, slot)` combinations. HARD rules filter the domain;
every other priority band contributes a weighted score. Three interchangeable
solvers (`greedy`, `backtracking`, `optimized`) work on the same domain and the
same objective — `(candidates scheduled, total score)`, in that order.

**Nothing is a black box.** A run is stored as a PREVIEW and only becomes real
interviews when confirmed. Each placement carries its per-constraint outcome,
each unscheduled candidate carries the reason its domain was empty, and every
later change is recorded in interview history.

**Evaluation is configuration, not code.** Metrics — seven by default — live in a
table with their own weights and score ranges. No metric name appears anywhere
in the source. Marks from several evaluators are averaged per metric and then
compiled with the configured weights.

**Five roles, one UI.** `ADMIN`, `COORDINATOR`, `FACULTY`, `STUDENT` and
`VIEWER`. Endpoints a role must not touch are gated; endpoints everyone may call
narrow their rows to the caller instead of returning 403, so one shared page
serves every role.
