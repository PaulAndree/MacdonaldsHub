# Walkthroughs against the real API (change 2, backend)

The approved walkthroughs of `docs/change_01_frontend.md`, repeated with the standard frontend (no example data) talking to the real API, PostgreSQL and Azurite. The result column is for the administrator: `OK`, or `Ajuste` with what to change.

**Contract and design approved:** contract 0.1.1 (see `docs/approvals/change_01_frontend.md`), layout tag `frontend-design-v1`.

## How to run them

```bash
docker compose down -v           # a clean database
docker compose up -d --wait      # frontend, API, worker, PostgreSQL, Azurite and mail capture
open http://localhost:3000       # the application; the local identity is an administrator
open http://localhost:8025       # mail capture: it must stay empty, nothing is sent
```

With your `.env` the branch catalog is the real one (Palacio de hielo, Hortaleza, Plaza, Bravo, Manoteras, Plenilunio, Ermita). Use the files of `docs/samples/xlsx/`:

- `incidencias-sucursales-reales.xlsx`: the mixed file with real branches (8 new, 2 duplicate, 2 conflict, 6 error).
- `solo-obligatorios.xlsx`, `sin-order-id.xlsx`, `dos-hojas.xlsx`, `danado.xlsx` need no branch, so they work as they are.

The files `incidencias.xlsx`, `incidencias-validas.xlsx` and `identica.xlsx` use the sample branches (centro, norte, sur): with the real catalog they are rejected row by row, which is itself a valid check of "unknown branch".

For UI-10 restart the API as a read-only user: `DEV_IDENTITY_ROLE=global_manager docker compose up -d --force-recreate api`, and back with `docker compose up -d --force-recreate api`.

## Results

| ID | How to run it | Expected | Result | Notes |
|---|---|---|---|---|
| UI-01 | Importar → `solo-obligatorios.xlsx` | Valid preview with the optional values absent, not zero | OK | |
| UI-02 | Importar → `incidencias-sucursales-reales.xlsx` (after cancelling the previous batch) | You can tell what will be imported and why each excluded row is excluded; the excluded-rows report downloads | OK | |
| UI-03 | Confirm that batch | Prepared rows, definitive incidents and pending emails are clearly different; the emails stay Pendiente and the mail capture stays empty | OK | |
| UI-04 | Upload a file, cancel the batch; repeat and press "Cerrar sesión" | The batch can no longer be confirmed | OK | |
| UI-05 | Incidencias → a Glovo incident → claim it, record a partial recovery, then correct it | Explicit amount and the history of the correction | OK | |
| UI-06 | Panel | Environment identified; email and Glovo apart; date criterion stated (claim date by default); missing values not invented; no "example" notes | OK | |
| UI-09 | Alta manual: repeat an existing Order ID, then a new Uber Eats one | The duplicate is refused; the new one needs confirmation and gets a pending email; a Glovo one gets none | OK | |
| UI-10 | Run as `global_manager`, try Importar, Alta manual and the actions of an incident | Access denied is shown and nothing changes | OK | |
| UI-11 | Review every row above | Layout, navigation and interaction approved, or adjustments requested | OK | |
| UI-12 | With an unconfirmed batch, try to upload another file | Upload blocked, pending batch named, options to resume or cancel it | OK | |

**UI-07 and UI-08** (an email ending in Error, pause with a send in progress) need the email sending of change 3 (`email-sending`) and are verified there. The three email-queue operations (`getEmailQueue`, `pauseEmailQueue`, `resumeEmailQueue`) are the ones the contract test lists as deferred.

## Final check (7.5)

Run on 2026-11-23 on the commit that follows `673a8ad` of the branch `backend`, with the administrator's ten walkthroughs recorded as OK above.

| Check | Result |
|---|---|
| Backend: `ruff check .`, `ruff format --check .`, `mypy`, `lint-imports` | All clean |
| Backend tests with real PostgreSQL, Azurite and mail capture | 588 passed |
| Infrastructure template tests; Bicep build and lint of `main.bicep` and both parameter files | 20 passed; clean |
| Frontend on a clean checkout of the pushed commit: contract lint and check, approval check, contrast, lint, types, tests, standard and example builds | All pass; 481 tests; the contract matches the approved version 0.1.1 |
| Images build: backend, frontend standard, frontend with example data | All three build |
| The standard frontend image holds no example data | 0 files with example markers and no mock service worker; the example image has the example layer, as intended |
| The standard frontend against the real API through the proxy (`scripts/smoke-real-api.sh`) | All checks passed: import, review, confirmation and its repetition, manual claim, manual entry with its email pending, dashboard |
| Nothing is sent | The confirmation and the manual entry leave every email `pending`; mail capture shows no message from the application. A test of the backend suite writes one message labelled "capture check" into the same capture service; it is not an application send |
| Audit link of a confirmed batch (BE-10) | Verified by `test_the_confirmation_is_audited_with_the_reviewed_hash` and `test_the_original_is_copied_verified_and_linked`: the audit names the user, the instant and the reviewed SHA-256, and the original is stored and verified in the confirmed store |
| No secret in the repository | No `.env`, key or certificate is tracked; the only matches are the public Azurite development key and test fixtures |
| CI of the branch | To be confirmed by the merge of the pull request |

## Decisions and gates, with their status

| Item | Status |
|---|---|
| P-04 metrics criteria | Decided 2026-11-23; implemented and approved in contract 0.1.1 |
| P-06 file limits | Decided: 10 MB, no row limit; synthetic sample files |
| P-07 allowlist | Resolved in change 0 (identifier by email) |
| P-09 formulas, extra headers, empty rows, local times | Decided 2026-11-23 |
| P-12 manual entry email | Decided 2026-11-23; Uber Eats and Just Eat create a pending email, Glovo none |
| P-01 real recipients | Open: only the configured test recipient (`TEST_RECIPIENT_EMAIL`) is allowed |
| P-02 mailbox access | Open; belongs to change 3 |
| P-03 final email text | Open: the text is the administrator's example, marked as such |
| P-05 retention, cleanup cadence, backup targets | Open: cleanup runs on every worker tick; no retention period is set on the confirmed store |
| P-08 history of manual claims | Open: needed before real data, to avoid claiming again what was handled by hand |
| P-10 relation between Total and the other amounts | Open: Total is stored as given and never validated |
| P-11 Glovo claim channel | Open: the channel is not recorded |

## Points to watch at the first deployment

- Set the GitHub variables `BRANCH_CATALOG`, `IMPORTS_ENABLED` and `TEST_RECIPIENT_EMAIL` of the test environment; imports stay off until the catalog is set.
- The role assignment that gives the backend write on the `confirmed` container carries a condition that removes delete. It is checked by the template tests, but only a deployment shows it applied.
- A file over 10 MB, or an unsafe archive, is rejected with the contract's reason `corrupt_or_protected_file` and a detail saying why: a dedicated reason would need a new contract version.
- The email queue operations and UI-07 and UI-08 belong to change 3.
