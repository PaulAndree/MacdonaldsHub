# Design

## Context

See `proposal.md` for motivation and scope, and `specs/platform/spec.md` and `specs/identity-access/spec.md` for requirements. Sources read: `docs/change_00_plataforma_base.md`, `docs/architecture.md`, `docs/project_overview.md`. `docs/api/openapi.yaml` was not read. This change does not depend on it, because no business endpoints exist yet.

The repository holds docs and OpenSpec files only. Nothing is implemented. Approved decisions that constrain this design:

- **Topology:** two images (frontend, backend) and three Container Apps services (frontend, API, worker). API and worker share one backend image with different start commands (ADR-01, ADR-03).
- **Identity:** Easy Auth with Google exists only on the frontend app, which proxies `/api` to an internal-ingress API (ADR-12). The API trusts the `X-MS-CLIENT-PRINCIPAL*` headers only in Azure and answers 401 without them.
- **Worker:** one permanent replica with `pg_advisory_lock` loop ownership. `SKIP LOCKED` row claiming and the global send-interval row come later (ADR-13).
- **Storage:** create-only SAS into `uploads`, plus an immutable `confirmed` container (ADR-14).
- **Infrastructure:** PostgreSQL Flexible Server per environment, created by Bicep, with secrets in Key Vault (ADR-15).
- **Layering** (`CLAUDE.md`): `domain/` (pure) → `services/` → `adapters/`, with `api/` and `worker/` as entrypoints. Configuration selects adapters, never business rules.
- **Pending:** P-05 (retention, availability objectives, backup/restore, cleanup cadence) and P-07 (allowlist values and stable identifier) stay open.

## Goals / Non-Goals

**Goals:**
- A skeleton that boots identically in local and Azure, differing only in selected adapters.
- Identity and authorization, tracing and secret handling enforced from the first request.
- Every platform spec scenario (BASE-01 to BASE-12) verifiable by automated tests against real PostgreSQL and Azurite, or by a documented Azure check.

**Non-Goals:**
- No business schema beyond what migrations, the allowlist and the technical flow need. The business model belongs to change 2.
- No XLSX parsing, outbox consumption, SMTP sending or functional UI.
- No decision on P-05 values or P-07 allowlist contents. Both are inputs supplied before the dependent task runs.
- No new services, queues or brokers (a new service needs an ADR).

## Decisions

### D1. Repository layout: monorepo with two deployables
`src/frontend/`, `src/backend/app/`, `infra/`, `.github/workflows/`, `docker-compose.yml` and `.env.example`, following the layout already committed in the repository (`azure.yaml`, `README.md`). The backend follows the layering rule: `domain/`, `services/`, `adapters/` (storage, identity, mail, db), `api/`, `worker/`.
- *Why:* one repo keeps the shared contract, IaC and pipeline together, and the layering rule gives a clean seam between business code and adapters.
- *Alternative:* a repo per service. Rejected, since it multiplies pipelines for a one-team project.

### D2. One backend image, two commands
Both API and worker run the same image with different start commands. Each process reads the same settings module.
- *Why:* required by ADR-01 and RNF-09, and it guarantees identical business code.
- *Alternative:* separate images. Rejected because the architecture forbids separate services without an ADR.

### D3. Settings and adapter selection
A single typed settings object loads from environment variables and fails fast on invalid or missing required values. An `APP_ENV` value (`local`, `test`, `production`) names the environment. Adapters (identity, storage, mail transport, telemetry exporter) are chosen from settings in one composition root. Business modules never read the environment.
- *Why:* RNF-15, and a single startup validation point is also where the RNF-16 guard lives.
- *Alternative:* scattered `os.environ` reads. Rejected as untestable.

### D4. Development identity guard
The development identity adapter is registered only when `APP_ENV=local`. Startup validation raises and the process exits if the dev identity is enabled with any other `APP_ENV`. As a second guard, Bicep never sets the dev-identity variable, and a test asserts the guard against the Azure-style settings.
- *Why:* RNF-16/BASE-08 require failure at startup, not a runtime flag check.
- *Alternative:* a runtime check per request. Rejected because it allows a running misconfigured instance.
- *Residual:* the guard trusts `APP_ENV`. It is set only by Bicep in Azure and is not user-editable there. A further signal such as Container Apps platform variables is left as a hardening option (see Risks).

### D5. Trusted identity from Easy Auth
API middleware reads the Easy Auth principal header in non-local environments, returns 401 if it is absent, then looks the identity up in the allowlist, then applies role permissions. Order matters: 401 before any database lookup (BASE-12). The frontend proxy forwards only the Easy Auth headers and strips the same-named headers from the client request before forwarding. Easy Auth overwrites them at the edge, and the API's internal ingress blocks direct callers (BASE-04, BASE-11).
- *Stable identifier:* the allowlist is keyed by an identifier column kept behind a small abstraction. The choice between Google `sub` and email is P-07 and is not decided here.
- *Alternative:* validate a JWT in the API. Rejected, because ADR-12 fixes the Easy Auth header transport.

### D6. Frontend proxy
The frontend container serves the SPA and reverse-proxies `/api/*` to the API's internal FQDN. The frontend container image is separate from the backend. Easy Auth is configured on the frontend app only, with authentication required.
- *Alternative:* expose the API publicly with its own Easy Auth. Rejected by ADR-12.

### D7. Storage abstraction and upload permission
A `StorageService` interface offers: issue a create-only upload grant for one blob name in `uploads`, check that a blob exists, and read its metadata. Implementations are Azurite (connection-based) and Azure Blob (managed identity, user-delegation SAS). The blob name is generated server-side, so a caller cannot choose the target. CORS allows only the frontend origin. In this change the immutable `confirmed` container is created, but no code writes to it. The no-delete rule is applied in the local adapter by code, because Azurite lacks immutability policies. No retention period is set (P-05).
- *Alternative:* proxy uploads through the API. Rejected, since direct browser upload is mandated.

### D8. Worker ownership with `pg_advisory_lock`
The worker opens a dedicated database connection and takes a session-level advisory lock with a fixed application key. The holder runs the loop. A non-holder keeps retrying acquisition on an interval and does not process. If the connection drops, the lock is released and another instance may take it. The loop here is a heartbeat that records lifecycle state, with no business work. The row-level claiming and the interval row from ADR-13 are added by changes 2 and 3.
- *Alternative:* a lease row with a timestamp. Rejected, because ADR-13 selects advisory locks and they release automatically on disconnect.

### D9. Persistence and migrations
SQLAlchemy 2 and Alembic (both marked as proposals in the architecture) provide versioned, reversible migrations. The first migration creates only what this change needs: the allowlist/roles table and a technical-flow record. The business schema is not designed here. Migrations run as an explicit deployment step, not at API start, so overlapping revisions never race on schema changes. Each migration has a tested downgrade.
- *Alternative:* auto-migrate at startup. Rejected because the worker and API start concurrently.

### D10. Observability
OpenTelemetry instruments the API and the worker, with the exporter chosen by settings: Azure Monitor/Application Insights in Azure, console or a local collector otherwise. A middleware sets the correlation ID, the actor (or system) and the result on each request span. A log filter prevents secret values and headers from being emitted. Alert rules and the log workspace are Bicep resources.
- *Alternative:* app-specific logging only. Rejected because RNF-05 needs correlation across API and worker.

### D11. Infrastructure as code layout
`infra/` holds Bicep modules for the Container Apps environment, the three apps, the registry, PostgreSQL Flexible Server, the storage account with its two containers, Key Vault, managed identities and monitoring. A per-environment parameter file (`test`, `production`) feeds the same modules. Test and production share no resource. The application gets only the identities and role assignments it needs (blob data access, Key Vault secret read).
- *Alternative:* one shared server with two databases. Rejected, since ADR-15 requires a server per environment.

### D12. Local Compose
Compose runs the frontend, API, one worker, PostgreSQL and Azurite on named volumes, plus an SMTP capture container. `APP_ENV=local` selects the dev identity, Azurite and SMTP capture. A single command brings up the stack. No Azure credentials are needed or read.
- *Alternative:* a mocked database for tests. Rejected, because the specs demand real PostgreSQL and Azurite.

### D13. CI/CD
GitHub Actions run lint and unit tests, integration tests with PostgreSQL and Azurite service containers, then image builds, then deployment through Bicep and the migration step. Deployment is gated on all earlier jobs. Azure authentication from the pipeline uses federated credentials, not stored secrets.
- *Alternative:* long-lived service-principal secrets. Rejected, given the no-secrets rule.

### D14. Time handling
Timestamps are stored as UTC (timezone-aware) and converted to Europe/Madrid only at presentation. This change contributes the shared helper and its tests. No incident-date parsing is added here.

## Risks / Trade-offs

- [`APP_ENV` is the only guard for the dev identity] → Bicep never sets the dev variable, the startup test covers non-local values, and the dev adapter is isolated so it can be excluded from the Azure build later if wanted.
- [Header trust depends on the API being unreachable from outside] → Internal ingress is verified by an explicit post-deployment check (BASE-11), and the middleware also rejects missing headers.
- [Easy Auth header behavior is verified only in Azure] → A deployed test environment check is part of the definition of done. Local tests simulate the header at the API boundary and cannot prove Easy Auth itself.
- [Advisory lock held by a hung but connected worker] → The heartbeat records liveness, and this change exposes the state. Recovery policy for stuck owners is revisited in change 3 with real work.
- [Azurite lacks immutability and some SAS semantics] → The adapter interface isolates differences, and Azure-specific behavior is checked in the test environment.
- [Scope creep into the business schema] → The first migration is limited to the allowlist and technical-flow tables.
- [Unresolved P-05 and P-07] → Tasks that need them are marked blocked on the decision and use no invented defaults. The restore procedure is documented without committing numeric objectives.

## Migration Plan

1. Provision the test environment with Bicep. Verify isolation from production.
2. Run the CI pipeline: lint, tests, image builds.
3. Deploy images and run the migration step. Start the worker and confirm that it owns the lock.
4. Verify in test: Google sign-in, allowlist denial, 401 without identity, no direct API reachability, technical flow and upload, overlapping worker revisions.
5. Rehearse database restore in test and record it.
6. Provision and deploy production with the same modules and its own parameters, once P-07 is resolved.

Rollback: redeploy the previous image revision, and run the reversible downgrade for the latest migration. The infrastructure code is idempotent and changes roll back by redeploying the previous version. No user data or confirmed imports exist yet.

## Open Questions

- What stable identifier does the allowlist use, Google `sub` or email? This is P-07. It is needed before production identity is enabled, and the abstraction in D5 keeps the choice local.
- Which local telemetry destination (console or a collector)? Either satisfies the spec.
- Which SMTP capture tool for local development? The choice does not affect the specs.
