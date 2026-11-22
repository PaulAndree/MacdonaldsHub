# Operations (platform base)

Technical notes for running Delivery Hub. Operating objectives (availability, RPO, RTO, backup
retention, cleanup cadence) are **pending decision P-05** and are deliberately not stated here.

## Logs, traces and alerts

- API and worker emit OpenTelemetry to Application Insights (Azure) or the console (local).
  Each request and worker state change carries a correlation id, the actor (a user identifier, or
  `system:worker`) and the result. Secrets are redacted from logs.
- Container logs: Log Analytics workspace `<prefix>-logs`. Query `ContainerAppConsoleLogs_CL` for
  structured JSON events (`app.access`, `app.worker`).
- Technical alerts (action group only if `ALERT_EMAIL` is set): API server errors, no worker
  replica running, PostgreSQL storage above 85 percent.
- Worker health: `GET :8081/healthz` is for the platform probe only (no ingress);
  `python -m app.worker.healthcheck` checks the heartbeat file.

## Database restore procedure

PostgreSQL Flexible Server keeps automated backups and supports point-in-time restore into a **new**
server. The application never restores in place.

```bash
# 1. Pick a time inside the retention window (UTC) and restore into a new server.
az postgres flexible-server restore -g <rg> --name <new-server> \
  --source-server <server> --restore-time 2026-01-01T10:00:00Z

# 2. Entra-only auth is part of the server configuration; the restored server needs the backend
#    managed identity as an administrator again:
az postgres flexible-server microsoft-entra-admin create -g <rg> -s <new-server> \
  --display-name <backend-identity-name> --object-id <backend-identity-principal-id> --type ServicePrincipal

# 3. Verify against the restored server (read-only): row counts and alembic revision.
#    From an operator machine this needs, on the NEW server only: the operator as an Entra admin
#    and a temporary firewall rule for the operator IP. Connect with an Entra token
#    (`az account get-access-token --resource-type oss-rdbms`) as the password.
# 4. To switch the application, redeploy with the new server name; keep the old server until verified.
```

Blob data: versioning is enabled on the storage account. Key Vault: soft delete is enabled
(secrets and the vault can be recovered within the retention period).

## Restore rehearsal record

| Date | Environment | Restore point | Result | Notes |
|---|---|---|---|---|
| 2026-11-22 | test | 2026-11-22T08:12:59Z (point-in-time, about 10 min earlier) | Restored and verified | New server ready in about 6 minutes (Burstable B1ms, PostgreSQL 17). Alembic revision `0001` equals the code head; `allowlist_entry` 1 row, `technical_check` 1 row. Step 2 commands worked as written. The temporary server was deleted afterwards; the original server was untouched |

Rehearsal limits: the restored data was compared with the expected values (migration head and the
seeded rows), not against live row counts of the source server. The restore point was a few minutes
old because the database holds only the technical tables. Application cut-over to a restored server
(redeploy with the new server name) was not exercised.

## Test environment identity verification record (task 11.3)

Environment `test`, 2026-11-22. Identity: Google through Easy Auth on the frontend only (ADR-12);
allowlist by email, initial administrator seeded from configuration (P-07).

| Scenario | How it was verified | Result |
|---|---|---|
| BASE-01 | Opened the frontend without a session in a browser | Redirected to Google sign-in. Reported by the administrator |
| BASE-02 | Signed in with a Google account outside the allowlist | Access denied. Reported by the administrator |
| BASE-03 | Signed in as the initial administrator | Technical screen, screen to API to PostgreSQL flow works. Reported by the administrator |
| BASE-04 | Requests with a forged identity header | No access outside Easy Auth. Reported by the administrator |
| BASE-11 | Direct call to the API from outside the environment | Not reachable: the API has internal ingress (`external=false`), the worker has no ingress. Confirmed in the Container Apps configuration |
| BASE-12 | Request reaching the API without an identity header | Rejected with 401. Reported by the administrator |
| BASE-08 | Azure configuration plus unit tests | The API and the worker run with `APP_ENV=test` and `IDENTITY_PROVIDER=easy_auth`; no development identity exists in Azure. `test_dev_identity_rejected_outside_local` and `test_startup_exits_with_clear_error_for_dev_identity_in_azure` pass. A live rejected start in Azure was not exercised |

## Test and production isolation record (task 11.6, BASE-10)

Checked 2026-11-22 against the Azure subscription used for deployments.

- The subscription holds one resource group for this project, `rg-deliveryhub-test`. The production
  group `rg-deliveryhub-production` does not exist: production has not been deployed.
- All 17 resources in the test group derive their names from the `test` environment (`tst` for
  globally unique names: registry, storage account, Key Vault, PostgreSQL server). None contains
  `prd` or `production`. Each environment gets its own PostgreSQL server, storage account and
  Key Vault, so no database, storage or secrets can be shared.
- The template tests `test_environment_isolation_in_naming_and_parameters` and the related checks
  pass: the two parameter files resolve to distinct resource names.
- No test batch or outbox data exists to promote, and the platform base creates none.

Re-run this check when production is first deployed (P-05 and P-07 pending).

## Browser upload to real Blob record (task 11.4, BASE-05)

Environment `test`, 2026-11-22.

- The administrator uploaded a technical file (13181 bytes) from the browser through the technical
  screen, using a create-only user-delegation SAS issued by the API. The screen reported
  "Archivo almacenado en uploads (13181 bytes)": the API read the size back from the real blob, so
  the upload reached the storage account. No incident is created by this flow.
- CORS on the blob service allows only the frontend origin, with methods `PUT` and `OPTIONS`. The
  browser upload working end to end confirms the rule.
- The storage account has the `uploads` and `confirmed` containers. Shared-key access is off.
- Not verified directly: listing the blob from the operator's own session, which needs a data role
  such as Storage Blob Data Reader on the storage account. The API's size read-back stands in for it.

## Overlapping worker revisions record (task 11.5, BASE-07)

Environment `test`, 2026-11-22. The administrator exercised overlapping worker revisions and
reported that only one revision processed work at a time. This was reported by the administrator
and was not independently observed in logs for this record.

## Known limits

- A confirmed import's original file has no retention policy until P-05 sets the period.
- The worker is a single replica by design; during a revision overlap the PostgreSQL advisory lock
  keeps one owner and the other instance stays on standby.
