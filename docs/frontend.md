# Frontend

Next.js 16 App Router, React 19, TypeScript, Tailwind v4. Every page is a client
component talking to the FastAPI backend through TanStack Query. There is no
mock data anywhere — every number on screen comes from a live endpoint.

```
frontend/
├── app/
│   ├── login/                  sign in
│   ├── claim/                  self-claim an account (code + email)
│   ├── change-password/        forced first-login password change
│   └── (app)/                  the dashboard, behind the auth guard
│       ├── layout.tsx          session guard + role guard + chrome
│       └── …/page.tsx          15 pages
├── components/
│   ├── layout/                 sidebar, topbar, page-meta context
│   ├── ui/                     button, card, table, dialog, tabs, toast, feedback
│   ├── charts/                 Recharts wrappers
│   ├── schedule-calendar.tsx   FullCalendar day/week views
│   └── faculty-timeline.tsx    booked / busy / free day diary
└── lib/
    ├── api.ts                  typed fetch wrapper, token storage, ApiError
    ├── queries.ts              every query and mutation hook, keyed
    ├── types.ts                TypeScript mirror of the API payloads
    ├── access.ts               route → role policy
    └── utils.ts                date/time formatting helpers
```

## Data layer

`lib/api.ts` is a thin typed wrapper around `fetch`:

- reads `NEXT_PUBLIC_API_URL` (falling back to `/api/v1`);
- attaches `Authorization: Bearer <token>` from `localStorage`;
- on any **401**, clears the session and redirects to `/login`;
- turns a non-OK response into an `ApiError` carrying `status`, the backend
  `error` code, the message and `detailLines` — the flattened `details` array,
  which is what the UI actually shows the user;
- `api.upload()` handles multipart for the Data Upload page.

`lib/queries.ts` holds every hook and a central `keys` registry, so invalidation
is explicit rather than guessed. `useInvalidateSchedule()` is the shared
invalidator that scheduling mutations call, keeping the schedule, calendar, free
slots, conflicts and dashboard consistent after any change.

## Guards

`app/(app)/layout.tsx` runs three checks before rendering anything:

1. no token → `/login`;
2. `must_change_password` → `/change-password` (an account still holding an
   issued temporary password gets nowhere else — that password was shown to
   somebody else);
3. `canAccess(role, pathname)` fails → bounce to the role's own home, rather than
   render a page whose every request would come back 403.

The sidebar filters its links through the same `canAccess` and drops sections
left empty by that filtering — so a link can never appear that the guard would
bounce. See [roles-and-permissions.md](roles-and-permissions.md#frontend-mirror).

## Pages

| Route | Title | What it does |
| ----- | ----- | ------------ |
| `/dashboard` | Dashboard | Live scheduling progress, conflict alerts, upcoming interviews, recent activity, faculty availability |
| `/upload` | Data / Excel Upload | Drop a `.xlsx`/`.csv`, see detected sheets, missing columns and row-level errors, then import; provision accounts |
| `/candidates` | Candidates | Everyone waiting for an interview, with preferences and constraints; create and edit |
| `/faculty` | Faculty | Interviewers, departments, daily interview limits |
| `/availability` | Faculty Availability | Declared windows and blocking commitments; free slots update automatically |
| `/free-slots` | Free Slots | Calculated free time, grouped or as a timeline, with a recalculate action |
| `/panels` | Panel Groups | Panels, their members, shared-faculty conflicts, and the windows where a panel can actually sit |
| `/scheduler` | Automated Scheduler | Choose algorithm, window and parameters; run; inspect the preview — per-placement constraint outcomes, unscheduled reasons, conflicts — then confirm or discard |
| `/schedule` | Interview Schedule | Day, week and table views; manual reschedule, panel swap, lock, cancel, complete; per-interview history; mark a faculty member unavailable |
| `/evaluations` | Evaluation Management | Configure metrics and weights, record evaluations, candidate metric profiles and rankings |
| `/analytics` | Analytics & Reports | Scheduling efficiency, workload distribution, utilisation, evaluation performance; downloadable report |
| `/settings` | Settings | Global scheduling configuration used by the engine, plus results publication |
| `/users` | User accounts | Logins, roles and links; create, reset a password, deactivate; password provenance |
| `/my-schedule` | My schedule | A faculty member's own interviews and availability |
| `/my-interview` | My interview | A candidate's own slot: confirm attendance, request a different time, see released results |

Outside the guard: `/login`, `/claim` (self-claim with a code and email) and
`/change-password`.

## Conventions

- `usePageMeta(title, description, actions)` sets the topbar from inside a page,
  so page-level actions live next to the page that owns them.
- `components/ui/feedback.tsx` provides the shared `LoadingState`, `EmptyState`,
  `Alert` and `ErrorState` used for every loading, empty and error state.
- Times arrive as `HH:MM:SS` and dates as ISO strings; `lib/utils.ts` has the
  formatting helpers (`formatTime`, `formatDate`, `minutesToHours`, …).
- `npm run typecheck` runs `tsc --noEmit`. `lib/types.ts` is the hand-maintained
  mirror of the API payloads, so a change to a backend response shape should be
  reflected there.
