# Proposal

## Why

Delivery Hub needs a deployable, verifiable foundation before any business flow is designed or built. Infrastructure, identity, secure configuration and process startup are the shared prerequisites of the frontend, backend and email-sending changes. Fixing them first avoids rework and puts authorization, tracing and secret handling in place from the start.

## What Changes

Source: `docs/change_00_plataforma_base.md` (with shared context from `docs/project_overview.md` and `docs/architecture.md`).
Dependencies: none. This is change 0 of 4. The next delivery is `frontend` (`docs/change_01_frontend.md`).

- Create the repository structure: a separate React + TypeScript frontend and one modular Python backend whose code and image are shared by the FastAPI API and one worker process.
- Add Bicep IaC for Azure Container Apps (frontend, API, worker), the image registry, one PostgreSQL Flexible Server per environment (ADR-15), Blob Storage with `uploads` and `confirmed` containers (ADR-14), Key Vault with managed identity, observability and connectivity.
- Add minimal frontend, API and worker services with containers, health checks and environment-variable configuration:
  - The worker runs as one permanent replica with no public ingress.
  - PostgreSQL mutual exclusion (`pg_advisory_lock`) stops overlapping revisions from processing the same work.
  - The worker only demonstrates its lifecycle and exclusion. It does not import or send.
- Add a reproducible local Compose environment with frontend, API, worker, persistent PostgreSQL, persistent Azurite and SMTP capture. One command starts it, and it needs no Azure access.
- Add `.env.example` without secrets and keep `.env` out of version control. Secrets come from Key Vault, and managed identities cover Azure service access.
- Add Google login through Container Apps Easy Auth (ADR-12):
  - Easy Auth is enabled only on the frontend, which proxies `/api` to an internal-ingress API.
  - FastAPI authorization middleware enforces an allowlist and role permissions from the forwarded identity, and answers 401 without it.
  - The initial administrator is configured outside the code.
- Add an explicit local development identity adapter with a configurable role. The process refuses to start if it is enabled outside the local environment.
- Add a `StorageService` interface with Azurite locally and Blob with managed identity in Azure. It issues temporary, create-only direct-upload permission scoped to the authorized file, with CORS in both environments.
- Add OpenTelemetry for API and worker, exporting to Azure Monitor/Application Insights, with configurable local output.
- Add GitHub Actions for lint, tests, image builds and deployment, and versioned reversible migrations (Alembic proposed).
- Provide a test environment separate from production, with its own database, storage and mail configuration. Test batches are never promoted to production.
- Deliver a minimal technical flow: authorized user → minimal screen → API → PostgreSQL, plus upload of a technical file to Blob/Azurite.
- Out of scope: import, preview, confirmation, incidents, metrics, outbox consumption and email sending, and the functional UI design of change 1. Pending items P-05 (operating objectives) and P-07 (identities and allowlist) stay explicit and are resolved before the parts that depend on them are implemented. No defaults are invented.

No **BREAKING** changes. There is no prior implementation.

## Capabilities

### New Capabilities
- `platform`: deployable runtime foundation covering:
  - the three-service topology, containers, health checks and environment-driven configuration;
  - Bicep-provisioned Azure resources;
  - the local Compose environment;
  - the storage abstraction and temporary direct-upload permission;
  - single-worker mutual exclusion;
  - secret handling;
  - observability and trace correlation;
  - UTC/Europe/Madrid time handling;
  - the CI/CD pipeline and reversible migrations;
  - test/production environment isolation;
  - persistence across restarts.
- `identity-access`: user authentication and authorization covering:
  - Google login through Easy Auth on the frontend only;
  - trust of the forwarded identity only from that mechanism, with 401 otherwise;
  - the FastAPI allowlist and role permission checks;
  - the externally configured initial administrator;
  - the local development identity adapter, rejected at startup outside local.

### Modified Capabilities
None. `openspec/specs/` currently holds no specs.

## Impact

- **New code:** `src/frontend/`, `src/backend/app/` (domain, services, adapters, api, worker), `infra/` (Bicep), Compose files, `.env.example`, `.github/workflows/`, Alembic migrations.
- **Azure resources:** Container Apps environment and three apps, registry, PostgreSQL Flexible Server, Storage account (`uploads`, `confirmed`), Key Vault, Application Insights/Azure Monitor, managed identities.
- **Dependencies:** FastAPI, Alembic, OpenTelemetry, Azurite, an SMTP capture tool, Google as identity provider through Easy Auth.
- **Requirements covered:** RNF-03, 04, 05, 09, 10, 11, 13, 14, 15, 16 and scenarios BASE-01 to BASE-12.
- **Downstream:** change 1 (`frontend`) builds on the layout and identity. Change 2 (`backend`) adds the business model to the migration mechanism. Change 3 (`email-sending`) builds on the worker lifecycle. The frontend approval boundary is unchanged.
