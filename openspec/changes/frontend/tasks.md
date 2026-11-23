# Tasks

Source: `docs/change_01_frontend.md`. These tasks build a navigable interface on example data. They are design evidence only: none of them is integration evidence for change 2. Tasks marked **[approval]** need the administrator's explicit decision.

## 1. API contract and tooling

- [x] 1.1 Add the frontend dependencies chosen in `design.md` (router, server-state library, request-mocking library, contract linter, type generator, schema validator, accessibility test helper) and verify `npm ci`, `npm run lint`, `npm test` and `npm run build` still pass.
- [x] 1.2 Write `docs/api/openapi.yaml` with the shared schemas: decimal amounts as strings, incident date with optional time, absent as null, system timestamps, batch states, the four row classes with reasons, incident states, error shape. Verify the contract linter passes and a schema test shows an absent amount is `null` and `0.1234` stays `"0.1234"` (RNF-13).
- [x] 1.3 Add the session, upload grant and processing, batch review, confirm and discard operations with named examples for success, rejection, discarded and pending-batch states. Verify the linter and the example-validation test pass.
- [x] 1.4 Add the incidents, export, results, corrections, manual entry and metrics operations with named examples (including empty and incomplete data). Verify the linter and the example-validation test pass.
- [x] 1.5 Add the email queue and pause and resume operations with named examples (error reasons, paused queue, denied). Verify the linter and the example-validation test pass.
- [x] 1.6 Generate the TypeScript types from the contract and add the CI checks: lint, example validation and generated-types freshness. Verify an edited contract with stale types fails CI and the unedited one passes.
- [x] 1.7 Add the approval check: the approval record stores the approved contract version and its SHA-256, and a CI check fails when the contract differs from the approved one, saying a new administrator approval is required. Verify with tests that a matching record passes, an edited contract fails, and no record yet passes with a notice.
- [x] 1.8 Document in `docs/api/README.md` how to change the contract and when a new approval is required. Verify the documented commands run as written.

## 2. Shell, design system and example layer

- [x] 2.1 Add design tokens, the page layout and the navigation by area, with all text in one Spanish strings module. Verify a render test of the layout and a script that checks the token color pairs meet WCAG AA.
- [x] 2.2 Add the router with the routes of all twelve areas and the 404 route. Verify a routing test for each route and that the nginx SPA fallback and `src/frontend/proxy-test/run.sh` still pass.
- [x] 2.3 Add the API client, the server-state setup and shared view primitives for empty, loading, error, incomplete, denied, discarded and paused states, plus the pending-decision marker with a P-xx id (D9). Verify one test per state and that no error text claims an outcome it cannot know.
- [x] 2.4 Build the example layer: build-flag guard, request handlers fed by the contract examples, in-memory state for the flows, and the example-mode section in `src/frontend/README.md`. Verify a standard build contains no example marker and an example build serves every contract operation.
- [x] 2.5 Add the permanent example-data notice, the visible test-environment identification and the footer with the design version. Verify tests that every screen shows them in example mode and that a standard build shows neither the notice nor example data.
- [x] 2.6 Add the scenario switcher in the footer of the example build (role, latency, failure, empty, paused queue, discarded batch) and list in `src/frontend/README.md` the file names that trigger each walkthrough case of UI-01 to UI-12. Verify the switcher changes the scenario in a test.

## 3. Access and identity (identity-access)

- [x] 3.1 Add the no-session and not-authorized screens, the identity, role and environment display, and the navigation filtered by role. Verify tests for 401, 403, administrator and global manager roles.
- [x] 3.2 Represent a denied administrative action returned by the API without silent failure (UI-10). Verify a test where a global manager triggers an administrative action and sees the denial with no change.

## 4. Import and batch review (xlsx-import, batch-confirmation)

- [x] 4.1 Build the import screen with file selection, upload progress, processing state and the interrupted-upload message. Verify tests for success and for an interrupted upload.
- [x] 4.2 Add the structure rejection reasons (missing header, several sheets, corrupt or protected) and the identical-file notice. Verify tests for each reason and that file size limits are not shown as approved (P-06).
- [x] 4.3 Add the display components for the input contract: unknown values, "Sin sucursal", full-decimal amounts, date with optional time in Europe/Madrid. Verify unit tests for absent not zero, `0.1234` unchanged, and no `00:00` invented (UI-01, RNF-13).
- [x] 4.4 Build the preview: counts per class, paginated and filterable detail with reasons, an example batch of about 500 rows, totals always visible. Verify the UI-02 test and that the browser never recomputes a class.
- [x] 4.5 Add the compared versions for conflicts, the repeated-key groups and the excluded-rows report download served from a static example file. Verify tests for the side-by-side differences and the download.
- [x] 4.6 Build the confirmation: summary, test recipient and template marked as example (P-03), no-undo notice, disabled action while waiting, uncertain-outcome message, stored result on repeat, and matches found at confirmation. Verify tests for UI-03, double click and network failure.
- [x] 4.7 Add cancel, the Cerrar sesión discard (confirmation, batches only, Google session kept, failure case), the pending-batch notice with no expiry, and the one-unconfirmed-batch block. Verify tests for UI-04 and UI-12, including that a rejected batch does not block.

## 5. Incidents and results (incidents)

- [x] 5.1 Build the incident list with filters, the detail with the status history and the three distinct dates. Verify tests for filtering and for the detail.
- [x] 5.2 Add the filtered export that keeps absent values explicit. Verify a test with an incident without branch and amount.
- [x] 5.3 Add the incident states without any retry action. Verify a test that Error de envío offers no retry or resend.
- [x] 5.4 Add the manual Glovo claim, the resolution with explicit recovered amount including partial, and the audited correction. Verify the UI-05 test and that the P-11 channel is shown as pending.
- [x] 5.5 Build the manual entry form with duplicate or conflict warning, the review step and the human confirmation, and no email option (P-12). Verify the UI-09 tests for duplicate, new and pending email option.

## 6. Dashboard (metrics)

- [x] 6.1 Build the dashboard with email and Glovo apart, the stated date criterion, explicit recovered amount, incompleteness warnings, pending claims with age, and example criteria marked pending (P-04). Verify the UI-06 tests, including a total with absent amounts that carries the warning.

## 7. Email queue (email-outbox)

- [x] 7.1 Build the queue view with the four states and totals, and completed batches with both Enviado and Error totals. Verify a test for a completed batch with failures.
- [x] 7.2 Add error reasons, the unverifiable-result message and the absence of retry, resend and cancel actions. Verify the UI-07 tests.
- [x] 7.3 Add pause and resume with the in-flight explanation, the paused indicator and the permission check. Verify the UI-08 test and that a non-administrator sees no controls.
- [x] 7.4 Show the single-attempt rule and the 30-second minimum, the Glovo-only empty queue and the test recipient label. Verify tests for each.

## 8. Delivery and accessibility

- [x] 8.1 Add the example-mode build argument to the frontend `Dockerfile` and the build scripts. Verify both images build and the standard image has no example marker.
- [x] 8.2 Add the CI job that builds both variants and fails when the standard bundle contains an example marker. Verify it fails against a build that includes one.
- [ ] 8.3 Add the example-mode input to the deploy workflow with the `-example` tag suffix and the production guard. Verify the guard rejects production with example mode and a test-environment deployment succeeds.
- [x] 8.4 Add automated accessibility checks over every area and a manual keyboard checklist in `docs/approvals/keyboard-checklist.md`. Verify the automated checks pass and the checklist is completed for the import review flow (RNF-08).
- [ ] 8.5 Deploy the example build to the `test` environment. Verify the example notice and test identification show and Google sign-in still protects access.

## 9. Review and approval

- [ ] 9.1 Walk through UI-01 to UI-12 in the deployed example build following the walkthroughs of `docs/change_01_frontend.md` and the scenario switcher, fix any gap found, and record each result in `docs/approvals/change_01_frontend.md`. Verify all twelve rows are filled with a result.
- [ ] 9.2 **[approval]** Obtain the administrator's explicit approval of layout, navigation, flows, messages and actions, or their requested adjustments, and tag the design version. Verify the record names the design version, the contract `info.version`, the commit and the date, with no personal data.
- [ ] 9.3 Run the final check: CI green, both images build, the standard image contains no example data, and no secret appears in the repository. Verify the results are recorded in the approval document.

## Workflow follow-up

- Archive the change only after the administrator's approval is recorded. Change 2 (`backend`) starts after that.
