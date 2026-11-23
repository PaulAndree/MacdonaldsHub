# Approval record: change 1 (frontend)

Walkthroughs UI-01 to UI-12 from `docs/change_01_frontend.md`, run against the deployed example build (test environment) or `npm run dev:example`. The data is example data: it is generated in the browser, lives in memory and resets on reload.

**Sample files:** `docs/samples/xlsx/`. In the example build the **file name** chooses the scenario, so keep the names. The footer "Escenario de ejemplo" panel changes role, latency, failures and the queue view.

**Result column:** `OK`, or `Ajuste` with the adjustment requested (then fix it and repeat the row). Do not include personal data.

| ID | How to run it | Expected | Result | Notes |
|---|---|---|---|---|
| UI-01 | Importar → upload `solo-obligatorios.xlsx` | Valid preview with the optional values shown as absent, not zero | OK | |
| UI-02 | Importar → upload `incidencias.xlsx` (reset the example data first) | You can tell what will be imported and why each excluded row is excluded | OK | |
| UI-03 | Confirm the batch from the preview | Prepared rows, definitive incidents and pending emails are clearly different | OK | |
| UI-04 | Upload a file, then cancel the batch; repeat and press "Cerrar sesión" | The batch can no longer be confirmed | OK | |
| UI-05 | Incidencias → open a claimed incident → register a partial recovery, then correct a mark | The amount is explicit and the history shows the correction | OK | |
| UI-06 | Panel | Environment identified; email and Glovo apart; date criterion stated; missing values not invented | OK | |
| UI-07 | Correo (queue view "running") | An email in Error shows its reason and there is no retry, resend or cancel | OK | |
| UI-08 | Correo → Pausar cola while one email is sending | It says the started send may finish and no other starts | OK | |
| UI-09 | Alta manual: one duplicate, one new | The duplicate is refused; the new one needs confirmation before it counts as saved | OK | |
| UI-10 | Footer panel: role "global manager" → try Correo and Importar | Access denied is shown for the action | OK | |
| UI-11 | Review every row above | Layout, navigation and interaction approved, or adjustments requested before closing | OK | |
| UI-12 | With an unconfirmed batch, try to upload another file | Upload blocked, pending batch named, with options to resume or cancel it | OK | |

## Approval (UI-11)

The administrator reviewed the twelve walkthroughs above in the deployed example build and approved the layout, navigation, flows, messages and actions. No adjustments were requested.

- **Design version (git tag):** `frontend-design-v1`
- **Contract `info.version`:** 0.1.0
- **Approved commit:** 3c438d1
- **Date:** 2026-11-23

Recorded values of this first approval: contractVersion=0.1.0, contractSha256=c993ba648f20bb1c83aed5dd29da37cdab838d098324e4514b317a8b23793b8e. Superseded by the approval of 0.1.1 below.

Any later change to `docs/api/openapi.yaml` makes `npm run approval:check` (and CI) fail until a new approval is recorded here.

## Approval of contract 0.1.1

On 2026-11-23, while implementing change 2 (`backend`), the administrator decided P-12 and P-04 and approved version 0.1.1 of the contract and the interface texts that follow from those decisions. No data structure changed; the design tag `frontend-design-v1` still names the approved layout.

- **Manual entry (P-12):** an Uber Eats or Just Eat entry generates one pending email in the same transaction and a Glovo entry generates none. The interface says so instead of "Sin correo".
- **Dashboard (P-04):** the default date is the claim date; the rate is recoveries over claims by number, not calculable without claims or with the recovery date; the age is in calendar days; known amounts are added and the missing ones are flagged. The criteria are no longer marked as examples.
- **Contract version:** 0.1.1.
- **Date:** 2026-11-23
- **Commit:** the one that contains this record.

Recorded values of this approval: contractVersion=0.1.1, contractSha256=900c20ed90d12f6b1ae5b2fe263936b679bfe6f503bbdfde4c1fe22542526cdf. Superseded by the approval of 0.1.2 below.

## Approval of contract 0.1.2

On 2026-11-23, while implementing change 3 (`email-sending`), the administrator approved version 0.1.2 of the contract and the interface texts that follow from it. Nothing else changed.

- **Queue entry without batch:** the `batchId` of an email may be null, because the email of a manual entry belongs to no batch. The Correo screen shows it as "Alta manual" in a new "Lote" column.
- **Sending availability:** the queue status has `sendingAvailable` and `unavailableReason`. When nothing can be sent (no mail server, sender or test recipient, or a production environment without real recipients) the screen says why, and says that the emails stay pending and do not turn into errors.
- **Contract version:** 0.1.2.
- **Date:** 2026-11-23
- **Commit:** the one that contains this record.

<!-- approval: contractVersion=0.1.2 contractSha256=0f5c7e07fee3dc92a73998cd12040ac7a299879bec35a9de5140066392821e31 -->

## Final check (9.3)

Run on `main` at merge commit `d9ece75` (PR #6, which contains the approved commit `3c438d1`), on 2026-11-23.

| Check | Result |
|---|---|
| CI on `d9ece75` (backend, frontend, infra, images) | All four jobs succeeded |
| Both images build (`docker build` of the backend and the frontend, standard and `EXAMPLE_MODE=true`) | Yes |
| Standard frontend image contains no example data | 0 files with example markers; no `mockServiceWorker.js` |
| Example frontend image contains the example layer | 1 file with markers and `mockServiceWorker.js` present (expected) |
| Test deployment of the example build, banners and Google sign-in (8.5) | Confirmed by the administrator |
| No secret in the repository | No `.env` file, key or certificate is tracked. A scan of the tracked files found only: the public Azurite development key (docker-compose, local test scripts), fixture strings in tests, and built-in Azure role-definition IDs in Bicep. No personal email or tenant, subscription or client ID |

Result: change 1 is ready to archive.
