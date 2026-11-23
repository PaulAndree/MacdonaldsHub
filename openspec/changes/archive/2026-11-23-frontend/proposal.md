# Proposal

## Why

The administrator must see, walk through and approve the layout, navigation, flows, messages and actions of Delivery Hub before any business logic is implemented. Building the backend (change 2) against an unapproved interface would bake guesses into the model and the API. A navigable single-page application with coherent example data, plus a versioned contract of what the interface needs from the backend, lets the administrator approve the design once and lets change 2 implement exactly that.

## What Changes

- **Source:** `docs/change_01_frontend.md`. Shared context: `docs/project_overview.md` and `docs/architecture.md`.
- **Dependencies:** `platform-base` (archived; provides the frontend container and proxy, Easy Auth identity, the technical API and the storage upload mechanism). The real integration belongs to change 2 (`backend`); this change does not implement it.
- Replace the technical screen with a navigable SPA covering the interface areas of the source: access, import, preview, confirmation, cancellation and discard, incidents, results, dashboard, manual entry and email queue. The technical screen is removed: "administrator" is the franchise's business administrator, so there are no screens for authorizations and roles, branches, providers, audit consultation or technical diagnostics (the technical team handles those).
- Serve **example data** through an example mode compiled in by a build flag. It runs locally and can be deployed to the `test` environment behind Google sign-in and Easy Auth, with a permanent visible "example data" notice. The production image is built without it.
- Show the non-happy states in every area: no data, loading, error, incomplete data, permission denied, discarded batch and paused queue.
- Write the frontend/backend contract as a versioned OpenAPI file, `docs/api/openapi.yaml` (ADR-16). Example responses derive from it and are validated against its schemas.
- Record the administrator's explicit approval of layout, navigation, flows, messages and actions, naming the exact design version and contract version approved. The change is not closed by building screens alone.
- Out of scope: the real XLSX parser, real deduplication, business migrations, incident persistence, the real outbox and email sending. Classification shown in the interface is example data, never business logic in the browser.

## Capabilities

### New Capabilities
- `xlsx-import`: the import interface: file selection, upload progress, processing, structure rejection, identical-file notice, and the faithful display of the XLSX input contract (optional values absent, branch and amounts unknown, incident date with optional time).
- `batch-confirmation`: the lifecycle interface of a batch: preview with the four classes and their reasons, compared versions, excluded-rows report, confirmation summary and single action, cancel, the Cerrar sesión discard, the pending-batch notice and the one-unconfirmed-batch rule.
- `incidents`: incident list, detail, filters, export and history; manual results (Glovo claim, partial recovery, rejection, audited correction); manual entry with duplicate or conflict warning and review before saving.
- `metrics`: the dashboard with email and Glovo separated, distinct dates, explicit recovered amount, pending claims and age, and incomplete-data warnings; pending criteria shown as design examples.
- `email-outbox`: the email queue view: Pending, Sending, Sent and Error states, reasons and totals, global pause and resume, one attempt per record with the 30-second minimum, and no retry, resend or cancel actions.

### Modified Capabilities
- `identity-access`: adds the interface side of access: sign-in start, denial for a user outside the allowlist, visible session, role and permissions, and the rule that hiding an action does not replace API authorization; and drops the technical screen from the initial administrator's access.
- `platform`: adds the versioned OpenAPI contract and its validation, the example mode and its boundaries, the visible test-environment identification, the Spanish and accessible interface, the non-happy states, and the recorded administrator approval; and changes the minimal technical flow so it has no user-facing screen.

## Impact

- **Code:** `src/frontend` (routes, screens, example-mode data layer, generated API types, tests, build flag); `docs/api/openapi.yaml` (new); `src/frontend/Dockerfile` (build argument for example mode); `.github/workflows` (CI checks for the contract and the frontend; an input to deploy the example build to `test`).
- **Dependencies:** a router, an in-browser request mocking library, a contract linter and a type generator for the frontend (chosen in `design.md`).
- **Backend and infrastructure:** no business API is added (the technical API stays in the backend, without a screen); no new Azure service; no Bicep changes expected.
- **Process:** the explicit administrator approval is the gate to start change 2. The rules in `openspec/config.yaml` require it before any change 2 business logic.
