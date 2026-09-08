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

- **Change `SECRET_KEY`.** The default is a development placeholder. Anyone who
  knows it can mint a valid admin token.
- **Change `FIRST_ADMIN_EMAIL` and `FIRST_ADMIN_PASSWORD`.** The bootstrap
  account is `admin@example.com` / `admin123` until you say otherwise.
- **Move off SQLite.** Point `DATABASE_URL` at PostgreSQL.
- **Set `CORS_ORIGINS`** to your real front-end origin, not localhost.
- **Terminate TLS in front of the API.** Bearer tokens over plain HTTP are
  readable in transit.
- **Rotate the seeded logins.** `scripts.seed` creates one account per role for
  demonstration; delete or re-password them.

## Scope

Reports about the default credentials above, or about anything reachable only
by an authenticated `ADMIN`, are working as designed rather than
vulnerabilities. Privilege escalation between roles, token forgery, or any way
to read another candidate's evaluation is very much in scope.
