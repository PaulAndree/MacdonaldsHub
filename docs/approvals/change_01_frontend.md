# Approval record: change 1 (frontend)

Walkthroughs UI-01 to UI-12 from `docs/change_01_frontend.md`, run against the deployed example build (test environment) or `npm run dev:example`. The data is example data: it is generated in the browser, lives in memory and resets on reload.

**Sample files:** `docs/samples/xlsx/`. In the example build the **file name** chooses the scenario, so keep the names. The footer "Escenario de ejemplo" panel changes role, latency, failures and the queue view.

**Result column:** `OK`, or `Ajuste` with the adjustment requested (then fix it and repeat the row). Do not include personal data.

| ID | How to run it | Expected | Result | Notes |
|---|---|---|---|---|
| UI-01 | Importar → upload `solo-obligatorios.xlsx` | Valid preview with the optional values shown as absent, not zero | | |
| UI-02 | Importar → upload `incidencias.xlsx` (reset the example data first) | You can tell what will be imported and why each excluded row is excluded | | |
| UI-03 | Confirm the batch from the preview | Prepared rows, definitive incidents and pending emails are clearly different | | |
| UI-04 | Upload a file, then cancel the batch; repeat and press "Cerrar sesión" | The batch can no longer be confirmed | | |
| UI-05 | Incidencias → open a claimed incident → register a partial recovery, then correct a mark | The amount is explicit and the history shows the correction | | |
| UI-06 | Panel | Environment identified; email and Glovo apart; date criterion stated; missing values not invented | | |
| UI-07 | Correo (queue view "running") | An email in Error shows its reason and there is no retry, resend or cancel | | |
| UI-08 | Correo → Pausar cola while one email is sending | It says the started send may finish and no other starts | | |
| UI-09 | Alta manual: one duplicate, one new | The duplicate is refused; the new one needs confirmation before it counts as saved | | |
| UI-10 | Footer panel: role "global manager" → try Correo and Importar | Access denied is shown for the action | | |
| UI-11 | Review every row above | Layout, navigation and interaction approved, or adjustments requested before closing | | |
| UI-12 | With an unconfirmed batch, try to upload another file | Upload blocked, pending batch named, with options to resume or cancel it | | |

## Approval (UI-11)

Pending. Filled in only after the administrator approves every row. It must name: the design version (git tag), the contract `info.version`, the commit and the date, and add the line `<!-- approval: contractVersion=... contractSha256=... -->` (values from `npm run approval:hash`).

## Final check (9.3)

Pending: CI green, both images build, the standard image has no example data, no secret in the repository.
