# Tasks

Tasks marked **[blocked: P-xx]** need that pending decision supplied by the administrator. Do not invent defaults. No task here implements import, outbox consumption, email sending or functional UI.

## 1. Repository scaffold

- [x] 1.1 Complete the existing scaffold: `src/frontend/`, `src/backend/app/` (`domain/`, `services/`, `adapters/{storage,identity,mail,db}/`, `api/`, `worker/`), `infra/` and `.github/workflows/`, each with a README. Verify the layout exists and the backend package imports cleanly.
- [x] 1.2 Add backend tooling (lint, format, type check, test runner) and frontend tooling (lint, test runner). Verify each lint and test command runs and passes on the empty skeleton.
- [x] 1.3 Add `.gitignore` excluding `.env` and add `.env.example` with variable names only. Verify `git check-ignore .env` succeeds and `.env.example` contains no secret values.
- [x] 1.4 Add an import-layering check so `domain/` imports no I/O or adapter code. Verify a deliberate violation fails the check.

## 2. Backend settings and composition root

- [x] 2.1 Implement the typed settings object from environment variables with fail-fast validation and `APP_ENV` (`local`, `test`, `production`). Verify unit tests for missing and invalid values.
- [x] 2.2 Implement the composition root that selects the identity, storage, mail transport and telemetry adapters from settings, with business modules never reading the environment. Verify unit tests for each adapter selection (RNF-15).
- [x] 2.3 Implement the startup guard that rejects the dev identity when `APP_ENV` is not `local`. Verify a test that startup exits with a clear error for `test` and `production` values (BASE-08, RNF-16).
- [x] 2.4 Implement the UTC timestamp and Europe/Madrid presentation helper. Verify unit tests cover UTC storage and a presentation across a daylight-saving change (RNF-13).

## 3. Database and migrations

- [x] 3.1 Add SQLAlchemy 2 and Alembic with a database adapter. Verify the connection succeeds against the real local PostgreSQL.
- [x] 3.2 Create the first migration for the allowlist/roles table and the technical-flow record only, with a downgrade. Verify upgrade, downgrade and re-upgrade pass in an integration test.
- [x] 3.3 Make migrations an explicit command, not run at API startup. Verify the API starts without applying migrations and the command applies them.
- [x] 3.4 Document the migration workflow in `src/backend/README.md`. Verify the documented commands run as written.

## 4. Identity and authorization

- [x] 4.1 Implement the identity adapter interface plus the dev identity adapter with a configurable role. Verify unit tests that requests act with the configured role locally.
- [x] 4.2 Implement the Easy Auth principal adapter, honored only outside `local`. Verify unit tests with valid, missing and malformed principal headers.
- [x] 4.3 Implement the authorization middleware order: 401 when identity is missing (before any database query), then allowlist, then role permission. Verify tests that a missing header returns 401 with zero allowlist queries (BASE-12), a non-allowlisted user is denied (BASE-02) and a wrong role is denied.
- [x] 4.4 Implement initial administrator seeding from configuration outside the code. Verify an integration test that the configured admin is allowed and nothing is hardcoded in source. **[blocked: P-07 for the stable identifier and real values]**
- [x] 4.5 Add the allowlist identifier abstraction so the Google `sub` or email choice stays local. Verify tests pass with either identifier kind.
- [x] 4.6 Add the forged-header test for identity headers supplied by a caller outside the trusted path (BASE-04). Verify it passes.

## 5. Storage service

- [x] 5.1 Define the `StorageService` interface and implement the Azurite adapter. Verify integration tests against real Azurite.
- [x] 5.2 Implement the create-only upload grant for a server-generated blob name in `uploads`, with existence and metadata checks. Verify an integration test that a different name and an overwrite attempt are rejected.
- [x] 5.3 Implement the Azure Blob adapter with managed identity and user-delegation SAS. Verify unit tests with a fake client now, and the real check in task 11.
- [x] 5.4 Apply the no-delete rule for `confirmed` in the local adapter by code. Verify a test that deletion is refused. Retention periods are not set **[blocked: P-05]**.
- [x] 5.5 Configure CORS for the frontend origin only, in Azurite locally. Verify a browser-origin upload succeeds from the allowed origin and fails from another.

## 6. API and technical flow

- [x] 6.1 Add the FastAPI app with liveness and readiness endpoints and the middleware wiring. Verify health responses and readiness failing without a database.
- [x] 6.2 Add the technical endpoints: a PostgreSQL connectivity check, an upload-grant request and an uploaded-file lookup that creates no incident. Verify an integration test for BASE-03 and BASE-05.
- [x] 6.3 Add request telemetry middleware with correlation ID, actor and result, plus a log filter that drops secret values and headers. Verify tests that records carry those fields and contain no secret (RNF-05).
- [x] 6.4 Document the technical endpoints in `src/backend/README.md`. Verify the documented requests work against Compose (task 9).

## 7. Worker

- [x] 7.1 Implement the worker entrypoint with a heartbeat loop and lifecycle state, with no business work. Verify it starts and records its state.
- [x] 7.2 Implement `pg_advisory_lock` ownership on a dedicated connection, with non-owners retrying without processing and takeover after the owner disconnects. Verify an integration test with two worker instances (BASE-07, RNF-09).
- [x] 7.3 Add worker telemetry with the same correlation and secret filtering. Verify a test of emitted lifecycle records.

## 8. Frontend skeleton

- [x] 8.1 Create the React + TypeScript app with a minimal technical screen: it shows the identity, calls the API connectivity check and uploads a technical file. Verify component tests and a manual check against Compose. It adds no functional design from change 1.
- [x] 8.2 Add the container that serves the SPA and reverse-proxies `/api/*`, forwarding only the Easy Auth headers and dropping client-supplied copies. Verify a proxy test that a forged header does not reach the API as trusted.
- [x] 8.3 Add the frontend health check. Verify it responds in the container.

## 9. Containers and local Compose

- [x] 9.1 Write the backend image (one image, API and worker commands) and the frontend image. Verify both build and the API and worker start from the same image.
- [x] 9.2 Write `docker-compose.yml` with frontend, API, one worker, PostgreSQL and Azurite on named volumes, and an SMTP capture service (for example Mailpit). Verify one command starts it with no Azure credentials.
- [x] 9.3 Verify local persistence: restart PostgreSQL, Azurite and the app containers, then confirm data and files remain and services recover (BASE-06, RNF-03).
- [x] 9.4 Verify SMTP capture receives a test mail and nothing leaves for a real provider (BASE-09). No outbox consumer is built.
- [x] 9.5 Document local startup and checks in the root `README.md`. Verify a fresh clone follows it successfully (RNF-14).

## 10. Infrastructure as code

- [x] 10.1 Write Bicep modules for the Container Apps environment, the three apps, the registry and monitoring. Verify `bicep build` and a what-if validation pass.
- [x] 10.2 Write modules for PostgreSQL Flexible Server (one per environment), the storage account with `uploads` and `confirmed`, Key Vault, and managed identities with least-privilege role assignments. Verify `bicep build` and a what-if validation pass (RNF-11).
- [x] 10.3 Configure the API with internal ingress, the worker with no ingress and one permanent replica, and Easy Auth with Google only on the frontend, requiring authentication. Verify the what-if output shows these settings. **[blocked: P-07 for the Google application and allowlist values]**
- [x] 10.4 Add `test` and `production` parameter files that share no resources, and make the dev identity variable never set by Bicep. Verify the parameter files reference distinct resource names and no dev variable.
- [x] 10.5 Configure OpenTelemetry export to Application Insights and add technical alert rules. Verify the alerts and workspace appear in the what-if output.
- [x] 10.6 Document the infrastructure in `infra/README.md`. Verify the documented deploy commands run as written in the test environment.

## 11. CI/CD and Azure verification

- [x] 11.1 Add the GitHub Actions workflow: lint, unit tests, integration tests with PostgreSQL and Azurite services, image builds. Verify a green run and that a failing test fails the pipeline.
- [x] 11.2 Add the deployment job (Bicep deploy, then the migration step, then app rollout) gated on earlier jobs, authenticating with federated credentials. Verify it deploys to the test environment and no stored secret exists.
- [x] 11.3 In the test environment, verify BASE-01 (Google sign-in starts), BASE-02, BASE-03, BASE-04, BASE-11 (direct API call fails with and without header), BASE-12 and BASE-08 (dev identity rejected). Record the results.
- [x] 11.4 In the test environment, verify a blob upload from the browser, CORS, and BASE-05 against real Blob.
- [x] 11.5 In the test environment, verify overlapping worker revisions processing nothing twice (BASE-07).
- [x] 11.6 Verify BASE-10: the test and production resources are separate and no test data is shared.
- [x] 11.7 Write and rehearse the database restore procedure in the test environment, record the result and describe the logs and alerts in `docs/operations.md`. Verify the rehearsal restores data. Numeric objectives are not set (P-05) (RNF-10).

## 12. Final integration check

- [x] 12.1 Run the full local stack and the test environment end to end. Verify CI is green, the images build, the technical flow works locally and in Azure, and no secret appears in the repository, logs or database.
- [ ] 12.2 Confirm the delivery states the skeleton is not business functionality, and list the open P-05 and P-07 items for the next change. Verify the listing exists in the PR description.

## Workflow follow-up

- Archive the change after the project's review requirements are satisfied.
- Verify the archived result and the consolidated `platform` and `identity-access` specs.
