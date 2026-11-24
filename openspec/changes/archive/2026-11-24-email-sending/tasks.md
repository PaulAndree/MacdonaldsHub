# Tasks

Order: schema and settings, the rules and the consumer under test, the transport, the queue operations, the worker, the contract and interface, and the walkthroughs. Each group ends with its tests green. Integration uses real PostgreSQL and the Mailpit capture service; nothing goes to a real provider.

## 1. Schema and settings

- [x] 1.1 Add migration `mail_control` (single row, paused by default, last start time) and an index on the outbox for the pending queue. Verify with a real PostgreSQL that it upgrades and downgrades, that exactly one row exists and that it is paused.
- [x] 1.2 Add the settings `SMTP_USER`, `SMTP_PASSWORD` (secret), `SMTP_FROM` and `SMTP_STARTTLS`, and the capture and SMTP transports in the registry. Verify the settings load, the password never appears in a log or an error, and an environment without a host is reported as sending unavailable.

## 2. Rules and consumer (TDD)

- [x] 2.1 Write failing tests, then the pure rules: which email is eligible, the 30-second interval, the recipient authorization and the sending availability (transport, test recipient, not production). Verify MAIL-01 and MAIL-10 cases, including that unavailability turns nothing into an error.
- [x] 2.2 Write failing tests, then the claim: lock the control row, take the oldest eligible email with row locking, record Enviando with its start time and the last start in one transaction, audit it. Verify with real PostgreSQL that an attempt is recorded before any transport call, that a paused queue claims nothing, and that two concurrent consumers claim at most one email (MAIL-04).
- [x] 2.3 Write failing tests, then the result recording: Enviado or Error with reason and kind, the incident to Reclamada with the Madrid claim date or to Error de envío, the history entry, the batch completion and the audit, in one transaction guarded by the Enviando state. Verify MAIL-06, MAIL-08 and E-10, and that a result for an email already ended by recovery changes nothing.
- [x] 2.4 Write failing tests, then the recovery of interrupted attempts at the start of a tick. Verify MAIL-03 and MAIL-07: an Enviando email becomes Error unverified with the same effects as 2.3, it is never sent again, and pending emails continue after the interval.
- [x] 2.5 Verify with a fake transport and the real database that no path makes a second attempt: after Enviado, after Error, after a restart and after changing the configuration, the transport is called exactly once per email.

## 3. Transport

- [x] 3.1 Write failing tests, then the SMTP transport over `smtplib` with the phases of D7, a 20-second socket timeout and STARTTLS and login only when configured. Verify against Mailpit that a message arrives with the stored subject and body, the Order ID in place of the variable and no amount or description.
- [x] 3.2 Classify failures: a failure up to the recipient is send failed, a failure while sending the data or a later timeout is unverified. Verify with a fake SMTP server for each case and with the capture service stopped (send failed).
- [x] 3.3 Verify that no credential, recipient password or message content appears in logs, the outbox or the audit.

## 4. Queue operations and permissions

- [x] 4.1 Write failing tests, then `pauseEmailQueue` and `resumeEmailQueue`: persistent, audited with the user, 403 and no change for a user without the queue permission, and an environment that starts paused. Verify MAIL-02 (an attempt in progress can finish, no other starts) and MAIL-09.
- [x] 4.2 Write failing tests, then `getEmailQueue`: pause status, attempts in progress, totals, per-batch progress with completed, entries filtered by state and batch and paged, `nextEligibleAt`, the 30-second and single-attempt statements, and an email of a manual entry with no batch. Verify against hand-counted data, including a completed batch with failures.
- [x] 4.3 Report unavailability in the queue with its reason. Verify each cause: no transport, no test recipient, production.

## 5. Worker and flow

- [x] 5.1 Wire the consumer and the recovery into the worker tick, after preparation, the original copy and the cleanup. Verify the worker with a restart in the middle of a send and two overlapping workers.
- [x] 5.2 Verify the complete flow with real PostgreSQL, Azurite and Mailpit: upload, review, confirm, resume the queue, the emails arrive one at a time at least 30 seconds apart at the test recipient only, the incidents become Reclamada, the batch Completado, and the dashboard counts the email claims (E-09, MAIL-11).
- [x] 5.3 Add the sending steps to `scripts/smoke-real-api.sh` and run it in CI: resume, wait for the first email, check the queue and the captured message. Verify it passes locally and in CI.

## 6. Contract and interface

- [x] 6.1 Update the contract to 0.1.2 (nullable `batchId`, `sendingAvailable` and `unavailableReason`), regenerate the types and the example data, make the contract test serve every operation with no deferred list, and update the queue screen for a null batch and for unavailability. Verify `contract:lint`, `contract:check`, the frontend tests and `approval:check` once approved.
- [x] 6.2 Obtain the administrator's approval of contract 0.1.2 and record it in `docs/approvals/change_01_frontend.md`. Verify the record names the version, the hash and the date, with no personal data.

## 7. Infrastructure

- [x] 7.1 Add to Bicep the SMTP host, port, user, sender and the mailbox password as a Key Vault reference, optional until the mailbox exists. Verify the template tests and `az bicep lint` pass, no secret value is in the template, and an environment without a host stays unavailable.

## 8. Walkthroughs and final check

- [x] 8.1 **Gate:** the mailbox (P-02) for the Azure test environment, and the recipient (P-01) and text (P-03) before any real send; record their status. Verify they are written down and that none is defaulted.
- [x] 8.2 Repeat UI-07 (an email ending in Error, with its reason and no retry action) and UI-08 (pausing explains that a started attempt may finish) on the real stack, recording each result in `docs/approvals/change_02_backend.md`. Verify both rows are filled in by the administrator.
- [x] 8.3 Run the final check: CI green, images build, no secret in the repository, no mechanism of retry anywhere, the interval respected in the logs of a run, and the open gates listed with their status. Verify the results are recorded.

## Workflow follow-up

- Archive the change when its tasks are done. Real sending in production stays blocked until P-01, P-02 and P-03 are resolved and the administrator approves its activation.
