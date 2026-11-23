# Proposal

## Why

Confirming a batch, or saving a manual entry, creates pending emails and sends none, so no claim by email ever leaves the system and the email channel of the dashboard stays empty. The sending task completes the claim flow: it consumes the outbox one email at a time, with a single attempt each, and records the result without ever retrying. It must be safe from the start (pausable, spaced, limited to the test recipient) because a duplicate or a misdirected email cannot be undone.

## What Changes

- **Source:** `docs/change_03_envio_correos.md`. Shared context: `docs/project_overview.md` and `docs/architecture.md`.
- **Dependencies:** `platform-base` (worker, advisory lock, mail adapter slot, secrets), `frontend` (approved queue screen) and `backend` (all archived: the outbox, the pending emails, the audit, the contract test with the queue operations deferred to this change).
- A consumer in the existing single worker takes the oldest pending email, starts **one** attempt, and records Enviado or Error with a reason. Nothing retries or resends, ever.
- The 30-second minimum between the starts of consecutive attempts is global, kept in PostgreSQL and survives restarts and overlapping revisions.
- The start of an attempt is recorded durably before the mail service is called. An attempt left unfinished by a restart ends in Error as an unverified result and is not sent again.
- Pause and resume, persistent and global, restricted to the administrator. A new environment starts **paused**: the administrator resumes it from the Correo screen, which is the explicit activation of sending.
- The three email-queue operations of the approved contract are served: the queue with its totals and entries, pause and resume.
- An incident follows its email: Enviado makes it Reclamada with the claim date, Error makes it Error de envío without return. A batch becomes Completado when all its emails have ended, with success and failure totals apart. Sending and queue control are audited.
- Safe recipients: only the configured test recipient, never a real provider; a production environment sends nothing while real recipients are undefined. Locally the mail goes to the SMTP capture service.
- Contract 0.1.2: the `batchId` of a queue entry may be null, because the emails of manual entries belong to no batch. It needs the administrator's approval, like 0.1.1.
- Verify UI-07 and UI-08 against the real stack, and repeat the full flow XLSX → confirmation → sending.
- Out of scope: retries, manual resends, cancelling after confirming, reading replies, Glovo email, real recipients (P-01), and the final template text (P-03). Sending from the Azure test environment waits for the mailbox access (P-02).

## Capabilities

### New Capabilities
<!-- None: every behavior belongs to an existing capability. -->

### Modified Capabilities
- `email-outbox`: the consumer, the global interval, the single recorded attempt, results, interruption recovery, persistent pause, the queue read operation, safe recipients and transport; the confirmation requirement no longer says sending is disabled, and the requirement that deferred the queue operations is removed.
- `batch-confirmation`: a confirmed batch completes when its emails have all ended.
- `incidents`: the incident follows the result of its email.
- `audit`: attempts, results, interruptions and queue controls are recorded.
- `platform`: no operation of the approved contract remains deferred.

## Impact

- **Code:** `src/backend` (consumer, SMTP transport, queue operations, migrations, worker wiring, tests), `src/frontend` (queue screen: a null batch), `docs/api/openapi.yaml` (0.1.2), `infra` (SMTP settings and the mailbox secret from Key Vault, optional until P-02).
- **Contract:** 0.1.2, one field becomes nullable. New approval record.
- **Dependencies:** none beyond the standard library: sending uses `smtplib`.
- **Gates:** P-02 (mailbox access) before sending from Azure; P-01 and P-03 before any real send; none is invented. The test recipient is already a variable of the test environment.
