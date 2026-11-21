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
# 4. To switch the application, redeploy with the new server name; keep the old server until verified.
```

Blob data: versioning is enabled on the storage account. Key Vault: soft delete is enabled
(secrets and the vault can be recovered within the retention period).

## Restore rehearsal record

| Date | Environment | Restore point | Result | Notes |
|---|---|---|---|---|
| _not yet rehearsed_ | | | | Needs the Azure test environment (task 11.7) |

## Known limits

- A confirmed import's original file has no retention policy until P-05 sets the period.
- The worker is a single replica by design; during a revision overlap the PostgreSQL advisory lock
  keeps one owner and the other instance stays on standby.
