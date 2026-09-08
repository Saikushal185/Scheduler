# Security

## Reporting a vulnerability

Open a [private security advisory](https://github.com/Saikushal185/Scheduler/security/advisories/new)
on this repository. Please do not open a public issue for something exploitable.

## What the application does today

| Area | Behaviour |
| ---- | --------- |
| Authentication | JWT bearer tokens, signed with `SECRET_KEY`, expiring after `ACCESS_TOKEN_EXPIRE_MINUTES` (720 by default) |
| Passwords | bcrypt via passlib; hashes only, never the plaintext |
| Authorisation | Role gating on endpoints a role may not touch, plus row scoping on shared endpoints — see [roles-and-permissions.md](docs/roles-and-permissions.md) |
| CORS | Closed by default to `CORS_ORIGINS` (`http://localhost:3000`) |
| Uploads | Capped at `MAX_UPLOAD_BYTES` (25 MB) and parsed, never executed |

## Before you deploy this anywhere real

These defaults exist so the project runs immediately after a clone. They are
not production settings.

- **Set `SECRET_KEY`.** There is no committed default under Docker Compose —
  it is a required variable, because anyone who knows the signing key can mint
  a valid admin token. The SQLite path in `backend/.env.example` still ships a
  placeholder; replace it.
- **Change `FIRST_ADMIN_EMAIL` and `FIRST_ADMIN_PASSWORD`.** The bootstrap
  account is `admin@example.com` / `admin123` until you say otherwise.
- **Move off SQLite.** Point `DATABASE_URL` at PostgreSQL, and set
  `POSTGRES_PASSWORD` — also required, also with no committed default.
- **Set `CORS_ORIGINS`** to your real front-end origin, not localhost.
- **Terminate TLS in front of the API.** Bearer tokens over plain HTTP are
  readable in transit.
- **Rotate the seeded logins.** `scripts.seed` creates one account per role for
  demonstration; delete or re-password them.

## Credentials in this repository

There are none. `POSTGRES_PASSWORD` and `SECRET_KEY` have to be supplied at
run time and `.env` is git-ignored, so nothing here is a live secret.

Two historical commits will still be reported by secret scanners:

| Commit | What it is |
| ------ | ---------- |
| `509f0c0` | The old `docker-compose.yml` with `POSTGRES_PASSWORD: interview` — a local-only Postgres password for a throwaway container, never used anywhere else. Removed. |
| `055285d` | False positive. `_PASSWORD_ALPHABET = "ABCDEFGH…"` is the character set `generate_password()` draws from, not a password. Renamed to `_UNAMBIGUOUS_CHARS`. |

Neither value gave access to anything, so there is nothing to rotate.

## Scope

Reports about the default credentials above, or about anything reachable only
by an authenticated `ADMIN`, are working as designed rather than
vulnerabilities. Privilege escalation between roles, token forgery, or any way
to read another candidate's evaluation is very much in scope.
