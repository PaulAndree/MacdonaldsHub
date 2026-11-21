# Delivery Hub

Delivery-incident claims app for a McDonald's franchise.

- `docs/` approved requirements (Spanish, source of truth)
- `openspec/` formal specs and changes (English)
- `infra/` Bicep (IaC) · `src/frontend` React + TS · `src/backend` FastAPI API + worker (one image)
- `.env.example` documents variables; never commit `.env`

**Status:** the `platform-base` change provides the runnable platform skeleton (identity, storage,
database, worker lifecycle, local environment). It contains **no business functionality**: no import,
confirmation, incidents, metrics or email sending. Those arrive in later changes.

## Run locally

Requires Docker. No Azure access is needed.

```bash
docker compose up --build
```

| What | Where |
|---|---|
| Frontend (technical screen, proxies `/api`) | http://localhost:3000 |
| API (direct) | http://localhost:8000/healthz |
| Captured email (Mailpit, nothing leaves the machine) | http://localhost:8025 |
| PostgreSQL | `localhost:5432`, database `deliveryhub` |
| Azurite (blob) | `http://127.0.0.1:10000/devstoreaccount1` |

Locally you act as the development identity (`dev@example.test`, role `administrator`); set
`DEV_IDENTITY_ROLE=global_manager` to try the other role. That identity cannot be enabled outside
`APP_ENV=local`: the process refuses to start.

### Check it works

```bash
docker compose ps                                    # all services running/healthy
curl -s localhost:3000/api/technical/me              # who am I (identity + role)
curl -s -X POST localhost:3000/api/technical/check   # round trip through PostgreSQL
```

Open http://localhost:3000, press "Comprobar base de datos", and choose any file to upload it
straight to Azurite. Data survives restarts: `docker compose restart` and `docker compose down`
keep the PostgreSQL and Azurite volumes.

```bash
docker compose down        # stop, keep data
docker compose down -v     # stop and DELETE local data
```

## Develop and test

Backend and frontend instructions: [src/backend/README.md](src/backend/README.md) and
[src/frontend/README.md](src/frontend/README.md). Azure infrastructure: [infra/README.md](infra/README.md).

Pending business decisions (P-01..P-12 in `docs/project_overview.md`) are not resolved by this code;
P-05 (retention and operating objectives) and P-07 (allowlist identifiers) are still open.
