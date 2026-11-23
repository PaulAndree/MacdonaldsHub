# Design

## Context

`platform-base` left a layered Python backend (`domain` pure, `services` use cases, `adapters` for PostgreSQL, Blob, identity and telemetry, `api` and `worker` entrypoints sharing that code), an allowlist table, a worker with a PostgreSQL advisory lock, a create-only upload mechanism with the `uploads` and `confirmed` containers, and Alembic migrations. Only the allowlist and a technical-check table exist. The `frontend` change approved contract 0.1.0 (24 operations) and the interface; `src/frontend/src/example/` holds the example layer that this change replaces with the real API. See `proposal.md` for motivation.

Constraints that shape everything: the unique key is provider + Order ID; amounts are decimals with source precision and absent is not zero; one email attempt (change 3); PostgreSQL atomicity is separate from Blob retention; one worker, no broker; API 403/401 semantics from ADR-12.

## Goals / Non-Goals

**Goals:**
- Business schema, ingestion, classification, atomic confirmation, discard, incidents, results, manual entry, audit and (later) metrics, matching the approved contract.
- Business rules as pure domain code under TDD, with PostgreSQL and Azurite integration tests for what only a real service can prove.
- No new Azure service and no new application service.

**Non-Goals:**
- Sending email, the consumer, the queue read and pause operations (change 3).
- Any administration or audit-consultation operation.
- Real recipients, template text, retention periods, file limits and the metrics criteria (open decisions).

## Decisions

### D1. Module layout follows the existing layers
`domain/` holds the row rules, the classification, the comparison, the permission matrix and decimal and date value types (no I/O). `services/` holds the use cases (prepare batch, confirm, discard, record result, manual entry) and the ports. `adapters/` holds PostgreSQL repositories, the XLSX reader and Blob. Routers in `api/` are thin. The import-linter contracts already in `pyproject.toml` keep `domain` free of I/O.
*Alternative:* a flat module per feature. Rejected: it loses the enforced purity that TDD on the rules depends on.

### D2. XLSX is read from the raw package, not through a spreadsheet library's numbers
A small reader opens the `.xlsx` ZIP, streams the single worksheet XML and keeps each numeric cell's **raw text** (`<v>12.345</v>`) to build a `Decimal`. A numeric cell is told from a text cell by the cell type, and a date cell from a number by the style's number format. It rejects, with a stated reason: encrypted files (not a ZIP), corrupt packages, more than one sheet, and unsafe archives (entry-size and compression-ratio guards). It never evaluates a formula; a formula cell is reported as such (P-09). XML is parsed with a hardened parser.
*Alternatives:* `openpyxl` read-only returns floats for numeric cells, which loses the source digits and breaks RNF-13 and BE-17; `pandas` is heavier and also converts. A custom reader is about a few hundred lines and fully testable with synthetic files.
*Risk:* edge cases of the format (shared strings, 1904 date system, inline strings). → Mitigation: tests per case with synthetic files; no anonymized sample exists (P-06), so a real file from the administrator is checked as soon as one is available.

### D3. Money is `NUMERIC` without scale and `Decimal` in code
Amount columns are `NUMERIC` with no precision or scale restriction. The API serializes them as strings. The stored value keeps the digits of the source, and comparison for classification is by decimal value, so `12.50` and `12.5` are equal in a comparison (RN-02) while each keeps its own digits when shown. No float appears on any path.

### D4. Dates: a `date` plus an optional `time`, and UTC for system instants
The incident date is a `DATE` and the time a nullable `TIME` read as Europe/Madrid local time. They are not combined into one timestamp, because a missing time must stay missing (RNF-13). All system instants are `timestamptz` stored in UTC. Non-existent or ambiguous local times (daylight saving) are pending P-09: while the time is stored as local wall-clock time, no conversion to an instant is needed for the incident.

### D5. Schema (reversible migrations, Alembic)
Tables: `provider`, `branch`, `batch`, `batch_row` (staging), `incident`, `incident_history`, `outbox`, `audit_log`, `confirmation_result` (stored as a column of `batch`), and a key-value table for system settings (authorized recipient and template version). Key constraints:
- `incident` `UNIQUE (provider_id, order_id)`.
- `batch` partial unique index on `(owner_id)` `WHERE state IN ('uploaded','processing','in_review')` for the one-unconfirmed-batch rule; it holds under concurrent inserts and lets a Rechazado batch not count.
- `batch_row` keyed by `(batch_id, row_number)` with the class, reason and parsed fields.
- `audit_log` append-only: the application role has `INSERT` and `SELECT` only, plus a trigger that raises on `UPDATE` or `DELETE`.
Migrations are tested up and down on a real PostgreSQL. Downgrades of business tables are allowed in development; production rollback is by restoring (documented in `operations.md`).

### D6. Classification is a pure function over a batch's rows and the existing incidents
It takes the parsed rows and a lookup of existing incidents by key, and returns one class and reason per row. Order of evaluation: errors first; then group valid rows by key; a group with any difference in a relevant field, or a difference against the existing incident, is En conflicto for every row; identical repetitions, or a match with equal fields, are Duplicada; the rest are Nueva. It is written test-first with the scenarios E-03 to E-05, BE-01, BE-06, BE-13, BE-17. The existing-incident lookup is a single set query per batch, not one per row.

### D7. The worker discovers work from persisted batch state
The batch state is the job queue: the worker, as lock owner, selects batches in `processing` (set when the browser reports the upload) whose lease is empty or expired with `FOR UPDATE SKIP LOCKED`, sets a lease timestamp on the one it takes, reads the file from Blob, verifies it, computes the SHA-256, writes staging and sets `in_review` or `rejected`. After a restart the stale lease makes the batch eligible again, and the processing is idempotent (it rewrites that batch's staging in one transaction), so BE-09 holds. No broker and no second service (ADR-13 unchanged).

### D8. Confirmation is one transaction with the batch row as the lock
`SELECT … FROM batch WHERE id = :id FOR UPDATE` serializes confirmations and cleanup on the same batch. Inside it: check state and the reviewed hash; if already `confirmed`, return the stored result; revalidate rows against current incidents; `INSERT … ON CONFLICT (provider_id, order_id) DO NOTHING RETURNING` to detect keys that appeared meanwhile (those rows become excluded results); insert outbox records for the new Uber Eats and Just Eat incidents; write history, the result JSON, the confirmed state and the audit record. Any exception rolls back everything. The recipient and template version in force are copied into each outbox row. Nothing sends.
*Alternative:* optimistic retry without a row lock. Rejected: the lock is simpler and makes cleanup coordination (D10) the same mechanism.

### D9. The confirmed original is copied after the transaction, by the worker
After commit, the batch has `original_copy = pending`. The worker copies the blob to `confirmed` under `batches/<batchId>.xlsx`, recomputes the SHA-256, and records `verified` or a discrepancy, which is logged and raises an alert (observability from `platform-base`). Retries of the copy are safe because the name is deterministic and the container refuses overwrites. Cleanup skips a blob while `original_copy` is not `verified` for a confirmed batch. The backend identity gets write on `confirmed` through a role assignment whose condition removes the delete action (phase 3), so nothing the application runs as can delete a blob there; the copy itself is created without overwrite, and the retention of P-05 will also make it immutable. Azure role conditions cannot tell creating from overwriting, which is why the adapter refuses to overwrite.

### D10. Discard and cleanup use the same lock
Discard locks the batch row, refuses a confirmed one, sets `discarded` and queues physical removal (`cleanup = pending`) in the same transaction. The worker performs the Blob delete and staging delete; on failure it records the error and retries, and the state does not claim removal until it succeeded. Cerrar sesión discards all of the user's unconfirmed batches in one transaction. There is no timer-based expiry anywhere. The cleanup cadence is pending P-05; the first version runs on every worker tick.

### D11. Permissions are a domain matrix, enforced in one place
The matrix (administrator all; global manager read-only) lives in `domain`, and one FastAPI dependency per operation checks it after the allowlist. 403 is returned with no change. The `session` operation already returns the permission list the frontend uses.

### D12. Contract test compares the generated OpenAPI to the approved file
A test loads `docs/api/openapi.yaml`, builds the app's OpenAPI, and compares paths, methods, parameters, request and response schemas and status codes of every operation that is implemented. A small explicit list names the deferred operations (`getEmailQueue`, `pauseEmailQueue`, `resumeEmailQueue`, change 3); anything else missing or different fails. Response models are written to match the contract (the routers use explicit Pydantic models, not inferred ones).

### D13. The queue operations are left to change 3
The source of change 3 assigns the queue read and the pause and resume to the sending change, and change 2 sends nothing. Implementing a queue view over records that can only be Pendiente would add an operation without its behavior. So the three operations stay in the approved contract and are deferred explicitly (D12). Consequence: walkthroughs UI-07 and UI-08 are verified against the real API in change 3, not here. Phase 7 repeats the others.
*Alternative:* serve the read from the outbox now. Rejected for scope and because the totals and pause semantics depend on the consumer.

### D14. Frontend integration removes no capability
The standard build already calls `/api/...`; phase 7 verifies each screen against the real API and removes example-only assumptions the real data does not allow. The example build stays for the `test` demonstration (`EXAMPLE_MODE`). Integration tests run the real API and PostgreSQL in CI through compose.

## Risks / Trade-offs

- [Custom XLSX reader misses a spreadsheet feature] → synthetic files and per-feature tests, and a clear rejection reason for anything unsupported instead of guessing.
- [Preview of 300–600 rows or more is slow] → batch inserts, one set query for existing incidents, paging in the API; no truncation, and the only limit is 10 MB of file size (P-06).
- [Confirmation holds a row lock while it writes up to hundreds of rows] → the transaction does no I/O to Blob or mail; hundreds of rows commit in well under a second.
- [Original copy fails after commit] → batch stays confirmed, copy is retried, discrepancy alerted, cleanup protects the temporary blob.
- [Decisions still open could block phases] → P-12 gates manual-entry email, P-04 blocks phase 6, P-10 gates any Total validation, P-08 gates real data. Each is a visible task gate, not an assumed default.
- [Two overlapping revisions run the worker] → the existing advisory lock and `SKIP LOCKED` per row keep one owner; leases make takeover safe.

## Migration Plan

Phases follow `docs/change_02_backend.md` section 11, each ending with green tests and a review before the next:
1. Schema, permissions, audit, catalog from configuration (no business logic).
2. Import and classification (TDD).
3. Atomic confirmation and outbox without sending, plus the `confirmed` role.
4. Discard, Cerrar sesión, one batch per user, cleanup.
5. Incidents, export, results, manual entry.
6. Metrics (blocked until P-04).
7. Frontend integration with the real API.

Deploy order per phase: migrations run before the applications (existing job). Rollback of a phase: revert the migration and redeploy the previous image; confirmed data is never deleted by a rollback of the application.

## Open Questions

- Real branch catalog values and the test recipient address: supplied by the administrator before phase 2 (the catalog) and phase 3 (the recipient); fixtures with example values are used until then.
- Whether the `confirmed` retention period (P-05) is applied in this change: left to the administrator's decision; no period is invented.
