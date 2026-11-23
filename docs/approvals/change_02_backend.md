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
| UI-01 | Importar → `solo-obligatorios.xlsx` | Valid preview with the optional values absent, not zero | | |
| UI-02 | Importar → `incidencias-sucursales-reales.xlsx` (after cancelling the previous batch) | You can tell what will be imported and why each excluded row is excluded; the excluded-rows report downloads | | |
| UI-03 | Confirm that batch | Prepared rows, definitive incidents and pending emails are clearly different; the emails stay Pendiente and the mail capture stays empty | | |
| UI-04 | Upload a file, cancel the batch; repeat and press "Cerrar sesión" | The batch can no longer be confirmed | | |
| UI-05 | Incidencias → a Glovo incident → claim it, record a partial recovery, then correct it | Explicit amount and the history of the correction | | |
| UI-06 | Panel | Environment identified; email and Glovo apart; date criterion stated (claim date by default); missing values not invented; no "example" notes | | |
| UI-09 | Alta manual: repeat an existing Order ID, then a new Uber Eats one | The duplicate is refused; the new one needs confirmation and gets a pending email; a Glovo one gets none | | |
| UI-10 | Run as `global_manager`, try Importar, Alta manual and the actions of an incident | Access denied is shown and nothing changes | | |
| UI-11 | Review every row above | Layout, navigation and interaction approved, or adjustments requested | | |
| UI-12 | With an unconfirmed batch, try to upload another file | Upload blocked, pending batch named, options to resume or cancel it | | |

**UI-07 and UI-08** (an email ending in Error, pause with a send in progress) need the email sending of change 3 (`email-sending`) and are verified there. The three email-queue operations (`getEmailQueue`, `pauseEmailQueue`, `resumeEmailQueue`) are the ones the contract test lists as deferred.

## Final check (7.5)

Pending.
