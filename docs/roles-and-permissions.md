# Roles and permissions

Policy lives in `app/core/permissions.py`, which imports no FastAPI plumbing so
it can be reasoned about (and tested) on its own. Enforcement lives in
`app/api/deps.py`. The frontend mirror is `frontend/lib/access.ts` — it decides
only what to *render*; the server remains the authority.

## The five roles

| Role | Purpose |
| ---- | ------- |
| `ADMIN` | Everything, including user administration |
| `COORDINATOR` | Admin-lite: runs the whole scheduling workflow, but may not manage accounts |
| `FACULTY` | Own availability, own panels' interviews, own evaluations |
| `STUDENT` | Own interview only (a candidate's login) |
| `VIEWER` | Read-only institute-wide reporting |

Role groups used by the gates:

```python
ADMIN_ROLES  = (ADMIN, COORDINATOR)
STAFF_ROLES  = (ADMIN, COORDINATOR, FACULTY)              # everyone who works the process
REPORT_ROLES = (ADMIN, COORDINATOR, FACULTY, VIEWER)      # institute-wide reporting
```

## Two mechanisms, because two different things need protecting

### Gating — endpoints a role may not touch at all

Dependency factories in `app/api/deps.py`, named for what they protect:

| Dependency | Roles | Protects |
| ---------- | ----- | -------- |
| `AdminUser` | `ADMIN` | user administration |
| `ManagerUser` | `ADMIN`, `COORDINATOR` | uploads, the scheduler, constraints, settings, master-data writes, manual overrides |
| `StaffUser` | + `FACULTY` | reading faculty, panels, metrics, conflicts |
| `ReportUser` | + `VIEWER` | analytics, rankings, candidate profiles |

A blocked call returns 403 with the caller's role and the allowed roles named.

### Scoping — endpoints everyone may call, narrowed to the caller

`build_scope(user)` derives a `Scope` from the role and the account link:

- `ADMIN` / `COORDINATOR` / `VIEWER` → unrestricted scope;
- `FACULTY` → `Scope(faculty_id=…)`;
- `STUDENT` → `Scope(candidate_id=…)`.

A `FACULTY` or `STUDENT` account with **no** linked person is refused with a 403
explaining that an administrator must link it. Failing closed is the point:
without the link there is nothing to narrow to, so treating it as unrestricted
would be the worst possible default.

List endpoints then apply that scope instead of refusing, so one shared page
keeps working for every role:

| Endpoint | Faculty caller sees | Student caller sees |
| -------- | ------------------- | ------------------- |
| `GET /interviews`, `/interviews/calendar` | interviews they sit on | their own interview |
| `GET /candidates` | all candidates | just themselves |
| `GET /faculty-availability`, `/faculty-busy-slots` | their own rows | 403 |
| `GET /free-slots`, `/free-slots/grouped`, `/free-slots/timeline` | their own diary | 403 |
| `GET /evaluations` | all evaluations | 403 — directed to `/evaluations/my-result` |
| `GET /interview-requests` | 403 — "handled by the scheduling administrators" | their own requests |

Reads of a single record are checked directly: `GET /interviews/{id}` and its
history refuse a student who is not the candidate and a faculty member who is
not on the panel.

### Ownership on mutations

The `assert_faculty_owns` / `assert_candidate_owns` helpers are called from the
service layer, not only from routers, so alternative entry points cannot bypass
them. They no-op for unrestricted callers (who are gated elsewhere) and raise
403 otherwise. Concretely:

- a faculty member may create, edit and delete only **their own** availability
  and busy slots, and may mark only **themselves** unavailable;
- a faculty member's evaluation is force-attributed to them, so marks cannot be
  filed under a colleague's name;
- a student may confirm attendance and request a change only on **their own**
  interview.

## Account lifecycle

Accounts arrive by three routes, all landing in `AccountService`:

**1. Administrator creates one** (`POST /auth/users`). The link rule is enforced
at creation: a `FACULTY` account without `faculty_id`, a `STUDENT` without
`candidate_id`, or an `ADMIN`/`COORDINATOR`/`VIEWER` *with* a link is rejected
with an explanatory 422 rather than failing confusingly at sign-in. One login
per person — the duplicate check names the existing account.

**2. Bulk provisioning after an import**
(`POST /uploads/provision-accounts?faculty=true&candidates=true`). Creates one
login per imported person that does not already have one, using the email
already present in the sheet, and returns the generated one-time passwords
**once** — they are hashed on save and cannot be read back. Existing accounts and
passwords are never overwritten, so re-importing a sheet is safe; people with no
email, or an email already in use, are skipped and listed in `notes`.

**3. Self-claim** (`POST /auth/claim`, public). Restricted to people the
institute already has on file: the submitted code **and** email must match the
same faculty or candidate record. The role follows from which kind of record
matched, so a claimed account is scoped exactly like an admin-created one. A bad
code and a mismatched email return the *same* generic message, so the endpoint
cannot be used to discover which codes exist.

### Passwords

- `POST /auth/login` returns a JWT (`sub` = user id, plus `role` and `email`),
  valid for `ACCESS_TOKEN_EXPIRE_MINUTES` (default 12 hours).
- `POST /auth/users/{id}/reset-password` issues a random one-time password,
  returns it once, and sets `must_change_password`. **An admin cannot reset their
  own password this way** — the new password is shown once, and missing it would
  lock the only account that can unlock anyone. Use change-password instead.
- `POST /auth/change-password` verifies the current password, rejects a new
  password identical to it, clears `must_change_password` and stamps
  `password_changed_at`.
- While `must_change_password` is set, the dashboard layout redirects every
  route to `/change-password`: the temporary password was shown to somebody else,
  so the account gets nowhere else until it is replaced.
- An admin cannot deactivate their own account.

## Frontend mirror

`ROUTE_ACCESS` in `frontend/lib/access.ts` maps route prefixes to roles, and both
the sidebar and the layout guard read it — a link can never appear that the guard
would bounce, and no route is reachable that the nav hides. Longest prefix wins,
so `/schedule` does not shadow `/scheduler`. `HOME_ROUTE` sends each role to a
landing page it can actually open (`/dashboard`, `/my-schedule` for faculty,
`/my-interview` for students), and a role landing on a page it cannot access is
bounced there rather than shown a page whose every request would 403.

| Route | Roles |
| ----- | ----- |
| `/dashboard` | ADMIN, COORDINATOR, VIEWER |
| `/upload`, `/scheduler`, `/settings` | ADMIN, COORDINATOR |
| `/users` | ADMIN |
| `/candidates`, `/faculty`, `/availability`, `/free-slots`, `/panels`, `/schedule`, `/evaluations` | ADMIN, COORDINATOR, FACULTY |
| `/analytics` | ADMIN, COORDINATOR, FACULTY, VIEWER |
| `/my-schedule` | FACULTY |
| `/my-interview` | STUDENT |

## Results visibility

Students never see marks until `interview_settings.results_published` is set by
an administrator. Before that, `GET /evaluations/my-result` returns
`{published: false}` with an explanatory message. After it, the candidate sees
their own compiled result with the rank and the per-evaluator breakdown removed
— both are internal.
