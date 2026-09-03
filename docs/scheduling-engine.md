# The scheduling engine

`app/scheduling/` is a self-contained solver: it imports no FastAPI and no
database session. It receives a `SchedulingContext` and returns a
`SchedulingResult`. `SchedulingService` is the only bridge to the database.

```
app/scheduling/
├── types.py          input/output dataclasses (Candidate/Faculty/PanelSpec, …)
├── domain.py         builds every legal candidate × panel × slot combination
├── constraints.py    one function per rule, registered against a ConstraintType
├── state.py          mutable solver state: who is booked when
├── placement.py      turns a scored option into a committed assignment
├── conflicts.py      independent verification of a finished schedule
├── engine.py         orchestration + constraint-satisfaction reporting
└── algorithms/       greedy · backtracking · optimized (pluggable)
```

## Free-slot calculation

Everything downstream reads `faculty_free_slots`, and that table is derived:

```
free slots = declared AVAILABLE windows
             − UNAVAILABLE windows
             − busy slots (manual, imported, and mirrored interviews)
```

Times are handled as **minutes since midnight** throughout
(`app/utils/timeutils.py`), which keeps the arithmetic integer-only and free of
timezone surprises. `Interval` is a half-open `[start, end)` range with
`overlaps` / `contains`; `merge_intervals`, `subtract_intervals`,
`intersect_all` and `slice_into_slots` do the set algebra.

Worked example — availability 09:00–17:00, busy 12:00–13:00 and a booked
interview 15:00–15:30:

```
09:00 ─────────────────────────────────────────────── 17:00   declared
            ██ 12:00–13:00 ██        ▓▓ 15:00–15:30 ▓▓          blocked
09:00────12:00   13:00────────15:00   15:30────────17:00        free (3 rows)
```

`FreeSlotService.recalculate()` first mirrors active interviews into
`faculty_busy_slots` (source `INTERVIEW`), then rebuilds the free rows for the
targeted faculty and date window. Because cancelled interviews lose their
mirrored rows, a cancellation genuinely frees the faculty member up again.

`FreeSlotService.timeline()` renders the same three tables as a day diary of
non-overlapping, colour-coded segments — `BOOKED`, `BUSY`, `FREE`,
`UNAVAILABLE` — so the calendar view can never disagree with the free slots the
scheduler consumes.

## Pipeline

```
build context → generate domains → drop hard violations → pre-score
              → solve → verify conflicts → report scheduled + unscheduled
```

### 1. Context

`SchedulingService.build_context()` resolves the date window (request overrides,
then settings, then the range that actually has free slots, then today + 6 days;
weekends excluded unless `allow_weekends`), refreshes free slots for it, and
materialises:

- `CandidateSpec` per schedulable candidate — preferences, parsed availability
  windows, blocked dates, `required_panel_code` from `constraints`, priority;
- `FacultySpec` per active faculty member — department, per-day cap, free slots;
- `PanelSpec` per active panel with at least one active member — member ids,
  mandatory ids, min/max size (min is clamped to the actual membership);
- `ConstraintSpec` per active constraint row;
- `ExistingBooking` for locked interviews (when `keep_locked_interviews`) and
  for every `COMPLETED` interview. Those candidates are excluded from planning
  but their bookings still occupy their faculty and panels.

### 2. Domain generation (`domain.py`)

For each candidate, every legal `(panel, day, slot)` combination. A slot grid is
built per `(panel, day)` from the **union** of member free time — a slot only
needs *some* members — clipped to the working window and sliced at the
configured granularity.

A combination is dropped when: the candidate blocked that date; the slot falls
outside the candidate's declared availability; fewer than the panel minimum are
free; a mandatory member is not free; or any HARD rule rejects it.

Three things keep this affordable on large instances:

- the slot grid and the per-slot eligibility list are computed once per
  `(panel, day)` and shared by every candidate;
- rules are evaluated at the coarsest level they depend on — once per
  `(candidate, panel)` for panel rules, once per `(candidate, day, slot)` for
  time rules, and once per `(panel, slot, department)` for the faculty rules,
  which read only the candidate's *department*. That last cache is disabled
  automatically when any constraint is scoped to an individual candidate, since
  the assumption no longer holds;
- each candidate keeps only its best `max_options_per_candidate` (default 400)
  options in a bounded heap, so memory tracks the cap rather than the
  cross-product. Ties break on earliest date/time, which keeps the kept set
  stable.

A candidate whose domain is empty is reported unscheduled immediately, with the
most frequent rejection reason and up to five counted details
(`"Outside candidate availability (128 combination(s))"`).

### 3. Constraint evaluation (`constraints.py`)

Each rule is a small function registered against a `ConstraintType`:

```python
@register(ConstraintType.DEPARTMENT_MATCH, faculty_dependent=True)
def _department_match(ctx, constraint, candidate, panel, day, slot, faculty_ids):
    ...
    return _outcome(constraint, ctx, ok, "Panel covers department …")
```

A rule returns a `ConstraintOutcome`. When a **HARD** rule reports
`satisfied=False` the combination is discarded; otherwise the outcome's score
feeds the optimiser:

```
score = priority band weight × constraint.weight_multiplier × satisfaction ratio
```

Band weights are configuration (`PRIORITY_WEIGHTS`):

| Band | Weight | Behaviour |
| ---- | ------ | --------- |
| `HARD` | 1000 | filter — a violation removes the option |
| `HIGH` | 100 | strongly preferred |
| `MEDIUM` | 50 | preferred |
| `LOW` | 20 | nice to have |
| `FLEXIBLE` | 5 | tie-break |

Registered rule types:

| Type | Depends on | Behaviour |
| ---- | ---------- | --------- |
| `CANDIDATE_UNAVAILABLE` | slot | candidate must be inside a declared window |
| `FACULTY_UNAVAILABLE` | faculty | every assigned member must be free |
| `PANEL_SIZE` | faculty | assigned count within `[minimum, maximum]` |
| `REQUIRED_PANEL` | panel | must be the named panel |
| `PREFERRED_PANEL` | panel | full credit for the requested panel, none otherwise |
| `BLOCKED_PERIOD` | slot | a blocked day, or a blocked window on a day |
| `CANDIDATE_PREFERRED_DATE` | slot | exact date = full credit; otherwise partial credit decaying over `tolerance_days` (default 5) |
| `CANDIDATE_PREFERRED_TIME` | slot | exact start = full credit; otherwise decays over `tolerance_minutes` (default 120) |
| `DEPARTMENT_MATCH` | faculty | candidate's department matches the panel or a member |
| `EARLIEST_SLOT` | slot | compactness: `0.6 × earlier day + 0.4 × earlier time` |
| `MAX_INTERVIEWS_PER_FACULTY` | solution state | per-day cap; as HARD it blocks, otherwise it scores |
| `LOAD_BALANCE` | solution state | rewards spreading work across faculty |
| `BREAK_BETWEEN_INTERVIEWS` | solution state | the break is enforced structurally by the state |

Setting a soft rule to `HARD` changes its meaning without a code change — a
`HARD` preferred date, for example, blocks every other day.

**Adding a rule** means writing one function, registering it, and inserting a
`scheduling_constraints` row. The solver never changes.

### 4. Solving

`SolutionState` owns everything that depends on *other* assignments and so
cannot be pre-computed: candidate/faculty/panel occupancy, per-day counts, and
the break period — implemented by treating each booking as occupying
`slot.end + break_minutes`, so an overlap check enforces the gap automatically.

`select_faculty()` picks the members: mandatory members must be available, and
remaining seats go to the **least loaded** available members, which is what
spreads workload without a separate balancing pass.

`try_build_assignment()` (`placement.py`) re-checks overlaps against the partial
solution, selects members, applies dynamic hard rules, and re-runs only the
three faculty-dependent rules — the slot-fixed outcomes were already computed
during domain generation.

### 5. Verification

`detect_conflicts()` re-checks the finished schedule independently of the solver
that produced it, and the same routine validates manual overrides. It reports:

| Kind | Meaning |
| ---- | ------- |
| `CANDIDATE_DOUBLE_BOOKED` | overlapping interviews for one candidate |
| `FACULTY_DOUBLE_BOOKED` | overlapping interviews for one faculty member |
| `PANEL_DOUBLE_BOOKED` | one panel in two places at once |
| `BREAK_VIOLATION` | consecutive interviews closer than the configured break |
| `OUTSIDE_FREE_SLOT` | a placement outside a member's calculated free time |
| `DURATION_MISMATCH` | an interview that is not the configured length |

### 6. Reporting

`engine.py` also produces a per-constraint-type satisfaction summary: how often
each rule was satisfied, the score it earned, and the score *forgone* measured
against the best any placement actually achieved, sorted by what was traded
away. That answers "why did we end up here" — which soft constraints were given
up, and how much they cost.

## Algorithms

Registered via `@register_algorithm`, listed at `GET /scheduling/algorithms`,
selectable per run, with a default in settings.

### `greedy`
One pass. Candidates with the fewest feasible slots go first
(most-constrained-variable ordering), each into its highest-scoring free slot.
Fast, and a usable baseline.

### `backtracking`
The problem as a CSP: variables are candidates, domains are feasible
combinations, and the objective is lexicographic —
`(number scheduled, total score)`. MRV ordering, a greedy incumbent so a usable
schedule exists even if the node budget runs out, a bound that prunes branches
that cannot beat the incumbent's count, and a branching factor of 6 best-scoring
options per candidate. Leaving a candidate unscheduled is itself a branch —
sometimes that frees a scarce slot for two others.

### `optimized` (default)
`greedy seed → bounded backtracking → local search`. The first two stop at the
first complete assignment; that is fine for feasibility but leaves value on the
table, because a candidate placed early takes the slot a later, more constrained
candidate needed and nothing revisits that decision. The third phase applies
three moves:

| Move | What it does |
| ---- | ------------ |
| insertion | place an unscheduled candidate, evicting a blocker and re-placing it elsewhere when the swap nets a gain |
| relocation | move one assignment to a better-scoring slot |
| swap | exchange two candidates' slots |

Only strict improvements on the same lexicographic objective are kept, and every
move goes through `SolutionState.commit`/`rollback`, so a move can never produce
a schedule the constructor would have rejected. Guard rails: at most 8 passes
and a 5-second improvement budget. The result is never worse than its own seed,
and the statistics report the deltas (`seed_scheduled` → `final_scheduled`,
`score_gain`, move counts).

## Preview and confirm

A run is not a schedule. `POST /scheduling/generate` stores a `PREVIEW` run with
the whole result — assignments, reasons, conflicts, statistics — and creates no
interviews. Reviewing it, then `POST /scheduling/runs/{id}/confirm`:

1. deletes existing unlocked `SCHEDULED` interviews (unless
   `replace_existing=false`);
2. creates one interview per assignment with its members, score and
   `priority_info`;
3. records an `AUTO_SCHEDULED` history row per interview;
4. updates candidate statuses to `SCHEDULED` / `UNSCHEDULED`;
5. recalculates free slots.

A confirmed run cannot be discarded and cannot be confirmed twice.
`POST /scheduling/generate-and-confirm` does both in one call.

## Manual override

Automation never removes control (`InterviewService`). An administrator or
coordinator can create an interview, move it, swap the panel or its members,
lock, unlock, cancel, complete or delete it, and mark a faculty member
unavailable. After every change the system re-checks conflicts, recalculates the
affected free slots, returns warnings and records history.

- A change that would conflict is **rejected** with the conflict list unless
  `force: true` is passed; a forced change is saved with status `CONFLICT` and
  the warnings stored in history.
- Reschedules validate the panel: unknown members and sub-minimum panels are
  rejected outright.
- A locked interview cannot be changed without `force`, and is preserved by the
  next scheduling run when `keep_locked_interviews` is set.
- Marking a faculty member unavailable creates the busy slot **and** flags every
  interview it breaks as `CONFLICT`, with a history entry naming the clash.
- `GET /interviews/available-slots` answers "where *could* this candidate go
  with this panel" by reusing the engine — the state is seeded with what is
  already booked, so a suggested slot is validated and scored exactly as the
  automated scheduler would score it, and a clash by choice is impossible.

## Candidate self-service

A student cannot reschedule themselves. They can confirm attendance
(`candidate_confirmed_at`) and file one pending change request per interview.
Approving it routes through the ordinary `reschedule()`, so history, conflict
detection and free-slot recalculation behave exactly as an administrator edit
would.

## Guarantees

Each of these is covered by a test in `backend/tests/test_scheduler.py`, most
parametrised across all three algorithms:

- no candidate, faculty member or panel is ever double-booked;
- the break period is preserved between consecutive interviews;
- interviews land only inside calculated faculty free slots;
- the configured duration is respected;
- panel minimum size and mandatory members are hard requirements;
- candidate availability windows and blocked periods are hard filters;
- per-faculty daily caps hold, and a per-faculty override beats the global one;
- existing/locked bookings are respected and can legitimately make a candidate
  unschedulable;
- preferences are honoured when possible and are not binding when soft;
- every unscheduled candidate carries a reason;
- results are deterministic for the same input;
- `optimized` is never worse than its own seed, and matches or beats the others.
