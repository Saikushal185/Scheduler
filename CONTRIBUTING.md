# Contributing

Thanks for looking at AcademiSync. This file is the short version of how the
project is developed; [`docs/operations.md`](docs/operations.md) has the full
setup and [`docs/architecture.md`](docs/architecture.md) explains where code
belongs.

Maintainer: **Sai Kushal** ([@Saikushal185](https://github.com/Saikushal185)).

## Getting set up

```bash
./setup.sh              # macOS/Linux — creates backend/.venv, installs both sides
setup.bat               # Windows
```

Then run the two halves in separate terminals with `./run-backend.sh` and
`./run-frontend.sh`.

## Before you open a pull request

```bash
cd backend  && .venv/bin/python -m pytest -q     # 103 tests, all must pass
cd frontend && npm run typecheck && npm run build
```

Both are cheap. A change that breaks either is not ready.

## Where code goes

The backend is layered, and the layer boundaries are the point:

| Layer | Directory | Rule |
| ----- | --------- | ---- |
| Routers | `app/api/` | Parse, authorise, delegate. No business logic. |
| Services | `app/services/` | All the rules live here. |
| Models | `app/models/` | SQLAlchemy tables only. |
| Schemas | `app/schemas/` | Pydantic request/response shapes. |
| Engine | `app/services/scheduling/` | Domain generation, constraints, solvers. |

If you find yourself writing an `if` about scheduling policy inside a router,
it belongs in a service.

## Adding a scheduling rule

Constraints are data, not branches. Add the type, give it a priority band and a
scoring function in `constraints.py`, and add a test that fails without it — see
[Adding a scheduling rule](README.md#adding-a-scheduling-rule).

## Evaluation metrics

Do not hardcode metric names anywhere. They live in the `evaluation_metrics`
table with their own weights and ranges; the seven defaults are seed data, not
part of the source.

## Commits

One change per commit, present tense, and a body that says *why* when the
subject cannot. The history should read as a description of how the system was
built.

## Documentation

The Markdown files under `docs/` are the source of truth. The Word edition is
generated, so after editing a chapter:

```bash
python3 docs/build-docx.py      # needs pandoc
```
