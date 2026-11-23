# Design

## Context

The `platform-base` change left a React 18 + TypeScript + Vite SPA with a single technical screen, served by nginx, which proxies `/api/*` to an internal API and forwards Easy Auth identity headers (ADR-12). There is no router, no data layer, no UI structure and `docs/api/` is empty. The API only has the technical operations. Motivation and scope are in `proposal.md`; the required behavior is in the delta specs.

Constraints that shape the approach: no new Azure service and no business server (ADR rule, source section 4); Spanish desktop UI with keyboard and contrast requirements (RNF-07, RNF-08); amounts keep source precision and absence is never zero (RNF-13); the backend is the only authority on validation and deduplication; pending decisions P-01, P-03, P-04, P-07, P-11 and P-12 must stay visibly pending.

## Goals / Non-Goals

**Goals:**
- A navigable SPA the administrator can walk through, in the browser, with no installation.
- A contract (`docs/api/openapi.yaml`) that change 2 can implement and a test can enforce.
- Every UI-01 to UI-12 walkthrough reproducible on demand, including failure and empty states.
- A recorded approval tied to a design version and a contract version.

**Non-Goals:**
- Real parsing, deduplication, persistence, outbox or email sending (changes 2 and 3).
- Replacing Easy Auth or the nginx proxy design from `platform-base`.
- Mobile layouts, internationalization beyond Spanish, or visual branding beyond a consistent design system.

## Decisions

### D1. Example data comes from an in-browser mock layer, selected at build time
Requests to the functional contract operations are answered by Mock Service Worker handlers inside the browser when the build flag `VITE_EXAMPLE_MODE` is true. The handlers never reach the network. The flag defaults to false; the mock module is loaded through a guarded dynamic import so a standard build contains neither the handlers, the fixtures nor the service worker file.
- *Why:* the source forbids an extra business server, and an in-browser layer needs no new service. It works identically on a laptop and behind Easy Auth in the test environment.
- *Alternatives:* a mock server container (Prism or similar) is a new service and needs an ADR, so rejected. Hand-written fetch stubs in the app code would ship in production and are harder to keep contract-shaped.

### D2. The contract is a hand-authored OpenAPI 3.1 file, linted and validated
`docs/api/openapi.yaml` holds the operations of the source table (session, upload grant and processing, batch review, confirm and discard, incidents and export, manual entry and results, metrics, queue and pause). Each operation carries named examples for its states (success, empty, error, denied, discarded, paused). CI lints the file, a test validates every example against its schema, and TypeScript types are generated from it and checked for freshness.
- *Why:* change 2 needs something implementable and testable; a Markdown description cannot fail a build. `info.version` is the contract version recorded at approval.
- *Alternatives:* code-first from FastAPI is impossible here because the business API does not exist yet. Markdown only was rejected earlier in the project as unverifiable.

### D3. Money and dates travel as strings and are never converted to floating point
The contract types amounts as decimal strings and dates as `YYYY-MM-DD` with an optional `HH:MM` time; absent values are `null`, never `0`. System timestamps are UTC instants shown in Europe/Madrid. The interface formats amounts without rounding and does not parse them to `number`.
- *Why:* RNF-13 and the source decimal-precision rule. A binary float would alter values with more than two decimals.

### D4. Routing, structure and server state
React Router gives deep links and the browser back button, which a review of many screens needs. TanStack Query holds server state and yields consistent loading and error states per area. Code is organized by area (`features/batches`, `incidents`, `metrics`, `session`, and `queue`), with shared `ui/`, `api/`, `example/` and a single Spanish strings module. Routes use Spanish paths; code identifiers stay in English.
- *Alternatives:* no router (a state machine in one page) loses deep links and complicates the approval walkthrough. Hand-rolled fetch hooks would repeat loading and error handling in twelve areas.

### D5. Styling: design tokens and native elements, no UI kit
CSS custom properties define color, spacing and type, with contrast checked against WCAG AA. Native elements are preferred (`<table>`, `<dialog>`, `<details>`, form controls) and a headless accessibility primitive is added only if a native one is missing.
- *Why:* fewer dependencies and full control over keyboard behavior and focus. The administrator approves a design, not a vendor look.
- *Alternative:* a component library speeds up the build but imposes its look and weight. Reversible if accessibility tests keep failing.

### D6. Stateful example flows, with fixtures that carry the classification
Mock handlers keep in-memory state so flows hold together: confirming turns the batch into a result, discarding disables confirm, a repeated confirmation returns the stored result, a second upload is blocked while a batch is pending, pausing the queue persists across screens. Fixtures supply each row's class and reason; the browser never computes them. Reloading resets the state.
- *Why:* UI-02, UI-03, UI-04, UI-08 and UI-12 are about interaction, not static pages.
- *Trade-off:* these transitions imitate backend rules. They are example behavior only, labeled as such, and the backend becomes the authority in change 2.

### D7. The scenario switcher exists only in example mode
A scenario switcher selects the role (administrator or global manager), latency, failures, empty data, a paused queue and a discarded batch. A footer shows the design version. All of it is part of the example module, so it is absent from standard builds.
- *Why:* the administrator must reach failure and permission states that a happy-path demo would never show. The twelve walkthroughs (UI-01 to UI-12) are followed from the source document, with the file names that trigger each case listed in `src/frontend/README.md`; there is no separate review-guide screen.
- *Alternative:* a review-guide screen that starts each walkthrough. Rejected: the franchise administrator does not need it, and the switcher and the README cover the same ground.

### D8. Large batches are paginated, never truncated
The batch detail is paginated and filterable by class, and the totals per class are always visible. The example batch has about 500 rows to exercise the 300 to 600 rows normal volume (RNF-01) without silent truncation. A scale target in milliseconds stays pending.

### D9. Pending decisions are a reusable visible marker
A single "pendiente de decisión" component carries the P-xx identifier and is used wherever the interface shows an example of an open decision: template text (P-03), metric criteria (P-04), Glovo claim channel (P-11), email for manual entry (P-12), the global manager role (P-07) and recipients (P-01).

### D10. Delivery of the example build
The frontend `Dockerfile` takes a build argument for example mode, default false. The deploy workflow gets an input choosing the frontend mode; example mode pushes both images with the tag suffix `-example`, so the single `imageTag` parameter in Bicep needs no change. The workflow refuses example mode for the production environment. CI builds both variants and a test fails if the standard bundle contains an example marker.

### D11. Approval record
The approval is written to `docs/approvals/change_01_frontend.md` and names the design version (a git tag, shown in the footer), the contract `info.version`, the commit, the date and the approving role. It records no personal data because the repository is public.

### D12. Evidence and its limits
Each UI-xx walkthrough has at least one Testing Library test driven through the example layer, plus automated accessibility checks and a manual keyboard checklist. These prove design and interaction behavior only; per project rules they are not integration evidence for change 2.

## Risks / Trade-offs

- [Example behavior drifts from the real backend] → The contract is the single source; change 2 adds a contract test, and example transitions are labeled as examples.
- [The example build is mistaken for real data in `test`] → A permanent notice on every screen, a footer with the design version, and the production guard in the deploy workflow.
- [Twelve areas make a large surface] → Tasks are grouped per area with a test per walkthrough, and an optional interim review for the administrator before the final approval.
- [The contract changes after approval] → Version bump and re-approval are required by the platform spec; CI flags a diff against the approved version.
- [A float sneaks into money handling] → Strings in the contract, generated string types, and a test that amounts with more than two decimals round-trip unchanged.
- [The service worker lingers after switching builds] → It is registered only in example mode, and the standard build unregisters any existing worker.
- [Pending decisions hardened by accident] → The shared pending marker, and specs that forbid presenting P-xx examples as approved.

## Open Questions

- Whether to adopt a headless primitive library after the first accessibility pass (D5). It does not change the specs or the task breakdown.
