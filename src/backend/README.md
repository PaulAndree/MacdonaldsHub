# Backend

One modular Python backend. The FastAPI API and the worker share this code and one image and differ
only in their start command.

Layering (see `CLAUDE.md`): `app/domain` (pure rules, no I/O) -> `app/services` (use cases) ->
`app/adapters` (storage, identity, mail, db). `app/api` and `app/worker` are entrypoints.
Configuration (`app/settings.py`) selects adapters and never business rules. This change provides the
platform skeleton only; nothing here is business functionality.

## Setup

```bash
cd src/backend
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

## Checks

```bash
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/mypy
.venv/bin/lint-imports          # domain must stay pure
.venv/bin/pytest tests/unit     # no services needed
```

### Integration tests (real PostgreSQL, Azurite and SMTP capture)

Start throwaway test services (separate from your local data), then run everything:

```bash
docker compose --profile test up -d --wait postgres-test azurite-test mailpit   # from the repo root
source scripts/test-env.sh
.venv/bin/pytest
```

`scripts/test-env.sh` sets `REQUIRE_INTEGRATION=1`, so a missing service fails the run instead of
silently skipping. The tests drop and recreate the schema, so they refuse any database whose name does
not end in `_test`.

## Migrations

Migrations are versioned and reversible, and are **never applied implicitly** when the API or worker
starts. Run them explicitly (needs `DATABASE_URL`):

```bash
export DATABASE_URL=postgresql+psycopg://postgres:localdev@127.0.0.1:5432/deliveryhub
.venv/bin/python -m app.migrate upgrade           # to head
.venv/bin/python -m app.migrate current           # show the applied revision
.venv/bin/python -m app.migrate downgrade         # one step back (or: downgrade base)
```

Under Compose the `migrate` service runs `upgrade` before the API and worker start.

## Initial administrator

Outside local, access comes from the allowlist. Seed the initial administrator from configuration
(never from code). Set `ALLOWLIST_IDENTIFIER` (`sub` or `email`, decision P-07) and the matching
`INITIAL_ADMIN_SUBJECT` or `INITIAL_ADMIN_EMAIL`, plus the usual settings, then run after migrating:

```bash
.venv/bin/python -m app.seed_admin
```

It is idempotent and re-activates the entry if it was disabled.

## Run the processes

```bash
uvicorn app.api.main:create_app --factory --port 8000    # API
python -m app.worker.main                                  # worker (one active owner at a time)
python -m app.worker.healthcheck                           # exit 0 when the worker heartbeat is fresh
```

## Technical endpoints (platform verification only)

Served under `/api/technical`; every route except `/healthz` and `/readyz` needs an authorized
identity (401 without identity, 403 if not allowlisted or the role is not permitted).

| Method and path | Role | Purpose |
|---|---|---|
| `GET /healthz` | public | liveness |
| `GET /readyz` | public | readiness (PostgreSQL reachable), 503 otherwise |
| `GET /api/technical/me` | any allowlisted | identity and role |
| `POST /api/technical/check` | administrator | writes and reads back a technical record |
| `POST /api/technical/upload-grants` | administrator | temporary create-only upload permission |
| `GET /api/technical/uploads/{upload_id}` | administrator | identify an uploaded technical file |

Against the Compose stack:

```bash
curl -s localhost:3000/api/technical/me
curl -s -X POST localhost:3000/api/technical/check
curl -s -X POST localhost:3000/api/technical/upload-grants     # returns url, method, headers
# upload straight to storage with the returned values, then identify it:
#   curl -X PUT "<url>" -H "x-ms-blob-type: BlockBlob" -H "If-None-Match: *" --data-binary @file
curl -s localhost:3000/api/technical/uploads/<upload_id>
```

These endpoints are not part of the future business API contract (`docs/api/openapi.yaml`).
