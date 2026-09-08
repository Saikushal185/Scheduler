# FAQ

Answers to the questions that come up first, with a pointer to the chapter that
covers each one properly.

## Why can't I enter a faculty member's free slots?

Because they are derived, not stored input. `faculty_free_slots` is
`availability − (busy slots + booked interviews)`, recomputed by
`FreeSlotService` whenever any of those three change. Entering them by hand
would let the table drift away from the bookings it is supposed to reflect, and
a cancellation would not give the time back. See
[scheduling-engine.md](scheduling-engine.md#free-slot-calculation).

## The scheduler says "No active panel group has available faculty members".

The free-slot table is empty. Import faculty availability, press **Recalculate**
on the Free Slots page, and check that the scheduling date range on the Settings
page overlaps the dates in the availability file. A panel group also has to be
active to be used at all.

## A candidate came back unscheduled. Why?

Every unscheduled candidate carries the reason its domain was empty — no free
faculty in the window, an availability window that does not overlap any panel's
free time, or a daily interview cap already reached. The reason is on the
scheduler results and on the dashboard. Widen the date range, lower the minimum
panel size, or relax a priority band from HARD to something softer.

## Which algorithm should I use?

`optimized` is the default and the right answer nearly always. The three solvers
share one domain and one objective — `(candidates scheduled, total score)`, in
that order — so they are comparable:

| Algorithm | Use it when |
| --------- | ----------- |
| `greedy` | You want an answer instantly and will accept a worse score |
| `backtracking` | Small instances where you want the search to be exhaustive |
| `optimized` | Everything else |

See [Algorithms](scheduling-engine.md#algorithms).

## Does generating a schedule overwrite the current one?

No. A run is stored as a `PREVIEW` and creates no interviews. It becomes real
only when you confirm it. That is what makes it safe to generate repeatedly
with different settings and compare.

## Can I move an interview the scheduler produced?

Yes. Manual override goes through the same conflict check, which rejects a
clashing slot with a 409 and a `details` list naming exactly what clashes. If
you mean it anyway, resubmit with `force: true` — the UI's **Apply anyway** —
and the interview is saved and flagged `CONFLICT`. Either way the change lands
in `interview_schedule_history`.

## How do I change the evaluation metrics?

Edit them. Metrics live in the `evaluation_metrics` table with their own
weights and score ranges; the seven defaults are seed data. No metric name
appears anywhere in the source, so adding an eighth or removing one is a
configuration change, not a code change. See
[evaluation-and-analytics.md](evaluation-and-analytics.md).

## Why can a student call the same endpoint as an admin?

Two different mechanisms protect two different things. Endpoints a role must
not touch at all are **gated** and return 403. Endpoints everyone may call are
**scoped** — the query narrows to the caller's own rows instead of refusing.
That is why one page can serve five roles.
[roles-and-permissions.md](roles-and-permissions.md) has the table.

## My spreadsheet has the columns in a different order.

That is fine. Sheets are matched by their column signature, not by position or
sheet name, and every field accepts aliases. If import still fails, the error
names the sheet, row, column and value. See
[data-import.md](data-import.md).

## Do I need PostgreSQL?

Not to try it. The backend defaults to SQLite so a clone runs with no
infrastructure. Point `DATABASE_URL` at PostgreSQL for anything real — see the
deploy checklist in [SECURITY.md](../SECURITY.md).

## I edited a chapter and the Word document is stale.

It is generated. Rebuild it:

```bash
python3 docs/build-docx.py      # needs pandoc
```
