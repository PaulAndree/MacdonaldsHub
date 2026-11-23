# Tasks

Phases follow `docs/change_02_backend.md` section 11, in order. Each phase ends with its tests green and a review before the next starts. Approval of change 1 is recorded (`docs/approvals/change_01_frontend.md`, contract 0.1.0, tag `frontend-design-v1`), so business logic may be implemented from phase 2; phase 1 adds none. Run PostgreSQL and Azurite locally (`docker compose`) for integration tests; example data of the frontend is not integration evidence.

## 1. Phase 1: schema, permissions, audit, catalog

- [x] 1.1 Add the permission matrix and role types to `domain` and a test-first unit suite: administrator can everything, global manager only reads. Verify the unit tests pass and import-linter still forbids I/O in `domain`.
- [x] 1.2 Write migration `0002` creating `provider`, `branch`, `batch`, `batch_row`, `incident`, `incident_history`, `outbox`, `audit_log` and the settings table, with the unique key `(provider, order_id)` and the one-unconfirmed-batch partial unique index. Verify with a real PostgreSQL that upgrade and downgrade both succeed and the schema returns to its previous state.
- [x] 1.3 Make `audit_log` append-only for the application role (insert and select only, plus a trigger that rejects update and delete). Verify an integration test that update and delete are refused and insert works.
- [x] 1.4 Add the audit service port and PostgreSQL adapter used by every use case. Verify a unit test that an operation writes the actor, the UTC instant, the object and the outcome.
- [x] 1.5 Load the providers and the branch catalog from configuration or migration, and fail startup with a clear message when imports are enabled but the catalog is empty. Verify an integration test for both cases. **Gate:** the real branch values come from the administrator (received 2026-11-23: Palacio de hielo, Hortaleza, Plaza, Bravo, Manoteras, Plenilunio, Ermita; set as the `BRANCH_CATALOG` variable of the environment, loaded by `python -m app.seed`); use labelled example values only in test fixtures.
- [x] 1.6 Enforce the permission matrix in the API with one dependency and make the existing technical routes unchanged. Verify tests: a global manager mutating gets 403, an identity outside the allowlist gets 403 on business operations, and a deactivated identity loses access on the next call (BE-08).
- [x] 1.7 Add the contract test that compares the generated OpenAPI with `docs/api/openapi.yaml` for implemented operations and lists the deferred ones explicitly. Verify it passes with the current operations and fails when a response field is added by hand (BE-18).
- [x] 1.8 Review of phase 1: confirm no business logic exists beyond schema and permissions, and the checks in CI are green.

## 2. Phase 2: import and classification (TDD)

- [x] 2.1 **Gate:** obtain from the administrator the decisions P-06 (size and row limits, anonymized sample) and P-09 (formula cells, extra headers, empty rows, ambiguous local times) for what phase 2 needs; record them in the change docs. Verify they are written down; do not default any of them. Recorded 2026-11-23 in `docs/change_02_backend.md` and `docs/project_overview.md`: 10 MB limit, no separate row limit, curated file, formula cells are row errors, extra headers ignored, empty rows skipped; no anonymized sample, synthetic files are used.
- [x] 2.2 Write failing domain tests, then implement the row rules: provider and branch lowercasing only, mandatory values, text Order ID, numeric amounts kept exactly, absent is not zero, accepted date and time formats with Europe/Madrid time and no invented time. Verify E-05, BE-06, BE-12, BE-14 and BE-17 pass.
- [x] 2.3 Write failing tests, then implement the classification and comparison as a pure function: errors first, key groups, conflict over duplicate, comparison by decimal value. Verify E-03, E-04, BE-01 and BE-13 pass.
- [x] 2.4 Implement the XLSX reader over the raw package: raw numeric text, date versus number by number format, one sheet, protected and corrupt files rejected, archive size guards, hardened XML parser, no formula evaluation. Verify with synthetic files for every case, including E-02, and with the anonymized sample.
- [x] 2.5 Implement the upload grant and batch registration (create-only, one blob per batch, batch must belong to the user) and the completion call. Verify an integration test with Azurite that a foreign or missing blob is refused and a second upload cannot overwrite (the refusal of a second batch is phase 4).
- [x] 2.6 Implement the worker task that finds batches by persisted state with `FOR UPDATE SKIP LOCKED` and a lease, verifies the SHA-256, processes the file and writes staging in one transaction. Verify an integration test that a restart during processing is recovered and creates no incident (BE-09, E-01).
- [x] 2.7 Implement the preview endpoints: counts per class, paged rows with filter by class, conflict versions, fingerprint, and the identical-file notice. Verify a 600-row batch reports its total and pages without omission, and the notice appears for a confirmed file's hash.
- [x] 2.8 Implement the excluded-rows report as an XLSX with reasons. Verify that uploading the corrected file again classifies already confirmed rows as Duplicada.
- [x] 2.9 Review of phase 2: re-run all phase 2 scenarios and confirm no definitive incident or outbox row exists before confirmation.

## 3. Phase 3: atomic confirmation and outbox without sending

- [x] 3.1 Write failing tests, then implement the confirmation use case in one transaction with the batch row lock: state and reviewed hash checks, revalidation, `ON CONFLICT DO NOTHING` for overtaken keys, outbox rows, history, stored result and audit. Verify E-06 (80 incidents, 60 pending emails, nothing sent) on a real PostgreSQL.
- [x] 3.2 Make confirmation idempotent and safe under concurrency. Verify E-07, BE-03 (two simultaneous confirmations, one wins) and BE-11 (repeat after staging cleanup returns the stored result).
- [x] 3.3 Inject a failure midway through confirmation. Verify E-08: no incident, outbox row or confirmed state remains.
- [x] 3.4 Handle keys created by another batch during review. Verify BE-02: the row is excluded, the rest is imported, and the result reports it.
- [x] 3.5 Store the authorized recipient and template version on each outbox row, with no secrets, and use only the configured test recipient. **Gate:** the test recipient address comes from the administrator (P-01); it is read from `TEST_RECIPIENT_EMAIL` (GitHub variable, passed by Bicep), and until it is set a batch with emails cannot be confirmed (409 `recipient_not_configured`). Verify BE-07: editing the configuration afterwards does not change existing rows.
- [x] 3.6 Add the Bicep role letting the worker identity write to `confirmed` with a condition that removes the delete action (the copy itself is created without overwrite, and P-05 retention will also protect it). Verify the template checks in `infra/tests` pass and the only role with write carries that condition.
- [x] 3.7 Copy the original to `confirmed` after commit under a name set by the batch, verify its SHA-256, record the link in audit, and alert on a discrepancy. Verify with Azurite that the copy is verified, that a failure is retried, and that the temporary blob is not deleted before verification.
- [x] 3.8 Mark batches Completado at confirmation when they have no email, and keep sending disabled. Verify a Glovo-only batch completes and that nothing in the code path sends a message.
- [x] 3.9 Review of phase 3: re-run E-06 to E-08, BE-02, BE-03, BE-07, BE-10 and BE-11, and confirm audit records the confirmation (BE-10).

## 4. Phase 4: discard, Cerrar sesión, one batch per user, cleanup

- [ ] 4.1 Implement discard of one batch in Subido, Procesando or En revisión and the Cerrar sesión operation that discards all the user's unconfirmed batches, both in one transaction and without ending the Easy Auth session. Verify E-11 and that a failure leaves the batch En revisión unchanged (BE-15).
- [ ] 4.2 Enforce the one unconfirmed batch per user through the partial unique index and return the pending batch in the refusal. Verify BE-16 with two simultaneous requests, a Rechazado batch not blocking, and a Procesando batch being discardable.
- [ ] 4.3 Implement the worker cleanup that removes the blob and staging of discarded and rejected batches, records failures and retries, and never claims removal early. Verify with Azurite that a failed removal is recorded and completed later.
- [ ] 4.4 Coordinate cleanup and confirmation on the batch row. Verify BE-05: a confirmed original is never deleted and a discarded batch is never confirmed, under concurrent runs.
- [ ] 4.5 Verify there is no automatic expiry: a batch En revisión stays confirmable after a long idle period and after the browser closes (BE-04). **Gate:** physical cleanup cadence and target stay as decided in P-05; none is invented.
- [ ] 4.6 Review of phase 4: re-run E-11, BE-04, BE-05, BE-15 and BE-16.

## 5. Phase 5: incidents, export, results, manual entry

- [ ] 5.1 Implement incident list and detail with filters by provider, branch, state and the three dates, including history. Verify E-13 prerequisites, that "Sin sucursal" and absent values are explicit, and that amounts keep their digits (`12.345`).
- [ ] 5.2 Implement the XLSX export with the same filters. Verify the file contains exactly the matching incidents and keeps optional values.
- [ ] 5.3 Implement the manual Glovo claim, resolution or rejection with an explicit recovered amount (partial allowed) and the audited correction. **Gate:** do not add restrictions on the recovered amount (P-04) or a claim channel (P-11). Verify E-12: a partial recovery, then a correction, shows previous and new values and changes neither the batch nor the email.
- [ ] 5.4 Implement manual entry with the same mandatory fields, the duplicate check, and creation only after the user reviews and confirms. **Gate:** P-12 is open, so no manual entry creates an outbox record until the administrator decides. Verify E-13: an existing key warns and creates nothing, and a new key is created once with audit and no outbox.
- [ ] 5.5 Review of phase 5: re-run E-12, E-13, RF-16, RF-21 and RF-22 and confirm read-only roles can list and export but not change.

## 6. Phase 6: metrics and dashboard (blocked until P-04 is resolved)

- [ ] 6.1 **Gate:** obtain the P-04 decisions from the administrator (default dates of filters, rate formula and denominator, division by zero, age criterion, recovered-amount restrictions, sum rules with absent amounts) and record them. Verify they are written down. Do not start 6.2 before this.
- [ ] 6.2 Write failing tests, then implement the aggregations in PostgreSQL with email and Glovo apart, explicit recovered amounts, pending claims with age, incomplete-data counts and no absent value treated as zero. Verify against hand-calculated expectations from the recorded P-04 rules.
- [ ] 6.3 Keep test and production figures separate and identified. Verify in the test environment that figures come only from its own data.
- [ ] 6.4 Review of phase 6: re-run the metrics scenarios and compare with the approved dashboard design.

## 7. Phase 7: integration of the approved frontend

- [ ] 7.1 Run the approved frontend (standard build, no example data) against the real API in compose and CI. Verify the contract test passes and the app starts with no example marker (`check:bundle:standard`).
- [ ] 7.2 Repeat the walkthroughs UI-01 to UI-06 and UI-09 to UI-12 against the real API with the sample files in `docs/samples/xlsx/`, record each result, and fix any difference found. Verify all ten rows have a result.
- [ ] 7.3 Record in the change docs that UI-07 and UI-08 are verified in change 3, together with the email queue operations deferred in the contract test. Verify the list of deferred operations matches the contract test.
- [ ] 7.4 Run the final check: CI green, images build, no secret in the repository, all open gates and their decisions listed with their status. Verify the result is recorded with the audit link for a confirmed batch (BE-10).

## Workflow follow-up

- Archive the change only when its tasks are done or the administrator accepts the open gates in writing. Change 3 (`email-sending`) starts after the outbox and the confirmed flow are verified.
