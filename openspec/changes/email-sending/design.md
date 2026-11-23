# Design

## Context

The outbox, the pending emails, the audit, the permissions (`queue_control`), the worker with its PostgreSQL ownership lock, the `setting` table and the mail adapter slot exist already; the queue screen of the approved frontend is built. What is missing is the consumer, the transport, the pause state, the three queue operations (deferred in the contract test) and the incident, batch and audit effects of a send. See `proposal.md` for the motivation.

Constraints: exactly one attempt per email; at least 30 s between starts, global and persistent; the start is recorded before the call; pause survives restarts; nothing is sent to a real provider; the queue starts paused; the worker already ticks every 5 s and owns the work under `pg_advisory_lock`.

## Goals / Non-Goals

**Goals:** a consumer that cannot send twice, cannot shorten the interval and recovers conservatively; results that move the incident, the batch, the history and the audit in one transaction; the queue operations of the contract; a locally verifiable flow with the capture service.

**Non-Goals:** retries, resends, cancel, replies, Glovo email, real recipients, the final text, a configurable interval, and a new service or broker.

## Decisions

### D1. The consumer is one more step of the worker tick
Each tick, as owner, the worker first recovers interrupted attempts (D5), then lets the consumer start at most one attempt. The 5 s tick is fine granularity for a 30 s interval. The call to the mail service happens outside any database transaction, so a slow transport cannot hold locks.
*Alternative:* a separate sender process. Rejected: ADR-08 keeps one worker.

### D2. Pause and interval live in one row, `mail_control`
Columns: `paused` (default true, so a new environment starts paused), `paused_at`, `last_started_at`, `updated_at`. The migration inserts the single row. Locking that row with `FOR UPDATE` serializes every start across overlapping revisions even if the advisory lock were lost, and the eligibility test runs in SQL with `now()`, so host clocks do not matter: `paused = false AND (last_started_at IS NULL OR last_started_at + interval '30 seconds' <= now())`. The 30 is a constant, not a setting.

### D3. Claiming an attempt is one short transaction
Lock `mail_control`; check eligibility; select the oldest pending email of an email provider with `FOR UPDATE SKIP LOCKED`; check its stored recipient is authorized (D6); set it Enviando with `started_at = now()`; set `last_started_at = now()`; audit the start; commit. Only then the message is built and sent. If the process dies after the commit, the row stays Enviando and recovery ends it in Error: the start was recorded before the call, as required.

### D4. Recording the result is one transaction, guarded by the state
`UPDATE outbox … WHERE id = :id AND state = 'sending'` records Enviado or Error with the end time and the reason; in the same transaction the incident moves (Reclamada with the Madrid claim date, or Error de envío), its history gets an email-result entry, the batch becomes Completado if no email of it is left Pendiente or Enviando, and the audit records the result. If recovery already ended that email, the guarded update touches nothing and the result is dropped, so a worker that lost ownership cannot overwrite the conservative outcome.

### D5. Recovery is "any Enviando at the start of a tick is orphaned"
Attempts are synchronous inside a tick, so an Enviando row found at the start of a tick can only belong to a process that stopped. It ends in Error of kind unverified, with the same effects as D4, and is never sent again. This covers a restart, a lost lock and an overlapping revision (MAIL-03, MAIL-04, MAIL-07).

### D6. Authorization of the recipient and availability are separate
An email may be sent only if its stored recipient equals the configured test recipient (case-insensitive). If it does not, the email ends in Error without a transport call (MAIL-10). Whether sending is available at all is a different check done before claiming: a transport is configured, a test recipient is set, and the environment is not production. When it is not available, nothing is claimed and nothing becomes an error, so a missing variable cannot burn the queue. The queue reports the reason.

### D7. The transport separates "refused" from "unverified"
One SMTP adapter over `smtplib` (no new dependency), with STARTTLS and login only when configured; locally it talks to the capture service with neither. It uses the phases `connect/ehlo/starttls/login`, `mail`, `rcpt` and `data`: a failure up to and including `rcpt` means the message was not handed over, so it is an Error of kind send failed; a failure while sending the data, or a timeout afterwards, leaves the outcome unknown, so it is Error of kind unverified. The socket timeout is 20 s, under the 30 s interval.

### D8. Settings and secrets
New settings: `SMTP_USER`, `SMTP_PASSWORD` (secret), `SMTP_FROM` (institutional sender) and `SMTP_STARTTLS`. Bicep passes host, port, user and sender, and the password only as a Key Vault reference; with no host set, the environment stays unavailable. Until P-02 provides the mailbox, the Azure test environment sends nothing, which is the safe default.

### D9. Contract 0.1.2
Two additive changes to the approved contract: a queue entry's `batchId` becomes nullable (manual entries have no batch), and `QueueStatus` gains `sendingAvailable` and `unavailableReason` so the interface can say why nothing is sent (D6). The frontend shows "Alta manual" for a null batch and a notice for unavailability; the example data follows. The administrator approves the version before integration, as with 0.1.1.

### D10. The queue read is SQL
Totals by state, per-batch totals with `completed` when nothing is pending or sending, and the entries filtered and paged, all from the outbox. The emails of manual entries appear in the totals and the entries, not in the batch list. `nextEligibleAt` is `last_started_at + 30 s` when the queue runs and has pending emails, otherwise null.

### D11. Verification without a real mailbox
Unit tests drive the consumer with a fake transport and a controllable clock (state in the database, time set by writing `last_started_at`); integration tests use real PostgreSQL and the Mailpit capture service for the happy path and stop it for the failure path. UI-07 is reproduced by stopping the capture service; UI-08 (pause with a send in progress) is covered by the automated test, since a capture service answers too fast to catch an attempt by hand.

## Risks / Trade-offs

- [A message accepted by the service whose success was not recorded shows as Error] → by design and shown as "unverified result", never as "not received"; it is never resent.
- [A stuck transport call delays the tick] → a 20 s socket timeout, shorter than the interval.
- [A missing variable could stall the queue silently] → the queue reports `sendingAvailable: false` with the reason, and nothing is turned into an error.
- [Overlapping worker revisions] → ownership lock plus the `mail_control` row lock plus the guarded result update.
- [The contract changes after approval] → the 0.1.2 approval is a task before integration.

## Migration Plan

1. Migration for `mail_control` (paused) and the supporting index on the outbox.
2. Domain rules and the consumer under test, then the transport, then the queue operations, then the worker wiring.
3. Contract 0.1.2, frontend and approval, then the walkthroughs UI-07 and UI-08.
4. Deployment: the migration runs before the applications; the queue arrives paused and the Azure test environment stays unavailable until P-02 supplies the mailbox. Rollback: redeploy the previous image; the migration only adds a table and an index.

## Open Questions

- Real recipients (P-01), the mailbox (P-02) and the final text (P-03) stay open and gate real sending only; the test recipient and the example text are enough to build and verify everything here.
