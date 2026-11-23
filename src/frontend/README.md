# Frontend

React + TypeScript SPA served by its own container, which also proxies `/api/*` to the internal API.

Change 1 (`frontend`) builds the navigable interface on **example data**, so the administrator can
walk through and approve the design before any business logic exists. Nothing here is business
functionality: classification, deduplication and persistence belong to the backend (change 2).

## Commands

```bash
npm ci
npm run dev             # standard mode: talks to the real API (proxied to localhost:8000)
npm run dev:example     # example mode: no backend needed
npm test                # unit and walkthrough tests
npm run lint && npm run typecheck && npm run check:contrast
npm run build           # standard build (what production ships)
npm run build:example   # example build (what the test environment can show)
```

The API contract lives in `docs/api/openapi.yaml`; see `docs/api/README.md` for how to change it.

## Example mode

Example mode serves example data from inside the browser, with no business server. It exists in two
places only: your machine (`npm run dev:example`) and, when the deploy workflow asks for it, the test
environment, behind Google sign-in. It is a **build-time** choice (`vite --mode example-data`), so the
standard build contains none of it. Check a build with `npm run check:bundle:standard` or
`npm run check:bundle:example` after building.

How it works:

- A mock service worker (`public-example/mockServiceWorker.js`, only copied into the example build)
  answers the contract's operations. Responses come from the **named examples in the contract**, so the
  contract and the example data cannot drift apart. `src/example/handlers.ts` adds in-memory state for
  the flows that need it (batches, confirmation, discard, the queue pause).
- The example state is in the browser's memory. Reloading the page resets it.
- Everything the example layer does is design behavior. It imitates rules the backend will own and is
  never evidence for change 2.

### Reproducing the walkthroughs

The file name chosen at upload decides what the example does with it:

| File name contains | Result |
|---|---|
| `sin-order-id` | Rejected: a required header is missing |
| `dos-hojas` | Rejected: more than one worksheet |
| `protegido` or `danado` | Rejected: the file is corrupt or protected |
| `solo-obligatorios` | Prepared, with only the three required columns (every optional value absent) |
| `identica` | Prepared, with the "identical file" notice |
| anything else | Prepared, with rows of the four classes |

The scenario (role, delay, failures, empty data, a batch already under review, a paused queue) is
chosen from the **Escenario de ejemplo** panel in the footer of every screen. The walkthroughs UI-01 to
UI-12 are described in `docs/change_01_frontend.md`; the table above gives the file names that trigger the
import cases, and the panel gives the role and the failure cases.

## Layout

```
src/app        routes, layout, navigation by area
src/features   one folder per area of the interface
src/ui         tokens, shared components and state views (loading, empty, error, denied...)
src/api        API client, query setup and generated types (schema.d.ts, do not edit)
src/example    the example layer: handlers, state, scenario (example build only)
src/i18n       all user-facing text, in Spanish
```
