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

<!-- approval: contractVersion=0.1.0 contractSha256=c993ba648f20bb1c83aed5dd29da37cdab838d098324e4514b317a8b23793b8e -->

Any later change to `docs/api/openapi.yaml` makes `npm run approval:check` (and CI) fail until a new approval is recorded here.

## Final check (9.3)

Pending: CI green, both images build, the standard image has no example data, no secret in the repository.
