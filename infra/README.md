# Infrastructure

Bicep for Azure Container Apps, registry, PostgreSQL Flexible Server (one per environment), Blob
storage, Key Vault, managed identities and monitoring. One **resource group per environment**
(`rg-deliveryhub-test`, `rg-deliveryhub-production`): nothing is shared between them.

| File | Purpose |
|---|---|
| `main.bicep` | Orchestrates the modules in three stages (below) |
| `main.test.bicepparam`, `main.prod.bicepparam` | Per-environment parameters (region `spaincentral`) |
| `modules/` | identity, registry, monitoring, keyvault, storage, postgres, container-env, container-app, container-job, auth, alerts |
| `tests/test_template.py` | Offline checks of the compiled template's security shape |

## Design in short

- **Only the frontend is public.** The API has internal ingress, the worker has none (ADR-12).
- **No database password.** PostgreSQL is Microsoft Entra-only; the backend managed identity is the
  database principal and the app obtains tokens. In v1 that identity is a database administrator;
  a least-privilege split is a later hardening.
- **No storage keys.** Shared-key access is off; the API signs create-only user-delegation SAS.
  `confirmed` has version-level immutability enabled but **no retention period** (P-05), and no
  identity can write or delete there in this change.
- **Secrets** live in Key Vault (RBAC only). Apps can only read them.
- **No development identity** exists in any Azure configuration.
- **Trade-offs to revisit:** PostgreSQL uses public access limited to Azure services plus TLS and
  Entra auth (a private network is a later hardening); sizing, redundancy and high availability are
  provisional until P-05.

## Stages

`DEPLOYMENT_STAGE` selects how much is deployed; each stage includes the previous one.

| Stage | Adds |
|---|---|
| `infrastructure` (default) | identities, registry, Log Analytics, App Insights, Key Vault, Container Apps environment, storage, PostgreSQL |
| `jobs` | the `migrate` and `seed` jobs (the backend image must already be in the registry) |
| `applications` | frontend, API, worker, alerts, and Easy Auth when enabled |

## Parameters from the environment

Values that depend on pending decisions are read from environment variables and have **no
defaults**: `ALLOWLIST_IDENTIFIER` (`sub` or `email`, P-07), `INITIAL_ADMIN_EMAIL` or
`INITIAL_ADMIN_SUBJECT`, `GOOGLE_CLIENT_ID`, `EASY_AUTH_ENABLED`, `ALERT_EMAIL`, `IMAGE_TAG`.

## Validate without deploying

```bash
az bicep build --file infra/main.bicep --stdout > /dev/null
az bicep lint --file infra/main.bicep
python -m pytest infra/tests
# read-only preview against an existing resource group:
DEPLOYMENT_STAGE=infrastructure az deployment group what-if -g rg-deliveryhub-test \
  --parameters infra/main.test.bicepparam
```

## Deploy (test)

```bash
az group create -n rg-deliveryhub-test -l spaincentral
DEPLOYMENT_STAGE=infrastructure az deployment group create -g rg-deliveryhub-test --parameters infra/main.test.bicepparam
# push images (see .github/workflows/deploy.yml), then:
DEPLOYMENT_STAGE=jobs          IMAGE_TAG=<tag> az deployment group create -g rg-deliveryhub-test --parameters infra/main.test.bicepparam
az containerapp job start -g rg-deliveryhub-test -n deliveryhub-test-migrate
az containerapp job start -g rg-deliveryhub-test -n deliveryhub-test-seed
DEPLOYMENT_STAGE=applications  IMAGE_TAG=<tag> ALLOWLIST_IDENTIFIER=... INITIAL_ADMIN_EMAIL=... \
  az deployment group create -g rg-deliveryhub-test --parameters infra/main.test.bicepparam
```

Use the GitHub workflow `Deploy` for repeatable deployments: it authenticates with GitHub OIDC
(federated credentials, no stored Azure secret). One-time setup: an app registration with a
federated credential for the repository environment (the credential's subject must match the
token exactly; GitHub may use the immutable-ID form `repo:OWNER@ID/REPO@ID:environment:test`, which
the `azure/login` error log prints), granted rights on the resource group that
include creating role assignments and pushing images (for example `Contributor`, `AcrPush` and
`Role Based Access Control Administrator`), and the variables `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`
and `AZURE_SUBSCRIPTION_ID` on the GitHub environment.

Role assignments can take a few minutes to propagate. If an app fails on its first deployment with
a Key Vault or registry access error, redeploy.

## Easy Auth with Google (needs decision P-07)

1. Create the Google OAuth client (redirect URI
   `https://<frontend-fqdn>/.auth/login/google/callback`).
2. Store its secret in Key Vault; it never goes through Bicep or Git:
   `az keyvault secret set --vault-name <vault> --name google-client-secret --value <secret>`
3. Deploy with `EASY_AUTH_ENABLED=true` and `GOOGLE_CLIENT_ID=<client id>`.

With Easy Auth off, the frontend proxy does not forward identity headers, so every `/api` call is
rejected with 401: the system fails closed.

## Status of verification

Verified: Bicep build and lint, offline template tests (including mutation checks), and read-only
`what-if` of all three stages against the test resource group. **Not yet verified:** an actual
deployment, the documented deploy commands end to end, Easy Auth, and the Azure-side checks in
tasks 11.3 to 11.7 of the change.

## Institutional mailbox (P-02, change 3)

Sending is optional per environment. Set the GitHub variables `SMTP_HOST`, `SMTP_PORT` (587 by default, STARTTLS), `SMTP_USER` and `SMTP_FROM`, store the password as the Key Vault secret `smtp-password` and then set `SMTP_PASSWORD_CONFIGURED=true`. Without `SMTP_HOST` the queue reports "sending unavailable", nothing is claimed and no email turns into an error. The password is never a template parameter: the apps read it through a Key Vault reference.
