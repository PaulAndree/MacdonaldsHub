# audit Specification

## Purpose
Defines the append-only recording of operations and the verifiable link between a confirmed batch and its stored original. The application records the trail; it offers no operation to read, edit or delete it, because the technical team consults it directly in the database.

## Requirements

### Requirement: Every operation is recorded
The system SHALL record in the audit trail, at the time each happens, uploads, confirmations, discards, results, corrections, manual entries and, once change 3 adds them, send results. Each record SHALL identify the actor (the user, or the system for worker actions), the instant in UTC, the object, the operation and its outcome. (RNF-05, RF-19)

#### Scenario: Confirmation is audited
- **WHEN** a batch is confirmed
- **THEN** an audit record names the user, the instant, the batch and the outcome, and it is written in the same transaction as the confirmation (BE-10)

#### Scenario: Refused operation
- **WHEN** an operation is refused for lack of permission
- **THEN** it creates no business change, and the refusal is observable in the request telemetry (BE-08)

### Requirement: Audit records cannot be edited or deleted
The audit trail SHALL be append-only. The database SHALL refuse updates and deletes of audit records for the application's role, and the application SHALL expose no operation to modify or remove them. (RF-19)

#### Scenario: Attempt to change an audit record
- **WHEN** the application role tries to update or delete an audit record
- **THEN** the database refuses it and the record is unchanged

### Requirement: No consultation or administration operation
The system SHALL NOT expose an API operation to consult the audit trail, nor to administer authorizations, roles, branches or providers. The technical team SHALL maintain those through migrations and configuration. (RF-18 retired, RF-19)

#### Scenario: Operations offered by the API
- **WHEN** the generated OpenAPI is listed
- **THEN** it contains no audit or administration operation

### Requirement: Confirmed batch linked to its original
The audit trail SHALL link a confirmed batch to its stored original file, the user who confirmed it, the confirmation instant and the SHA-256 of the reviewed file. The link SHALL record whether the stored copy was verified. (RF-19, ADR-14, BE-10)

#### Scenario: Original verified
- **WHEN** the original has been copied to the confirmed store and its hash matches the reviewed one
- **THEN** the record states that the copy was verified and names the stored object

#### Scenario: Original not verified
- **WHEN** the stored copy is missing or its hash differs
- **THEN** the discrepancy is recorded and alerted, the batch stays confirmed, and no other file replaces the original

### Requirement: Minimal audit of a discard
The audit record of a discarded batch SHALL NOT contain any row or file content. It SHALL contain only the actor, the instant, the batch identifier and the outcome, including whether the physical removal is complete. (RF-17, RF-19)

#### Scenario: Discard audited without content
- **WHEN** a batch is discarded
- **THEN** its audit record holds no rows, no file and no file name beyond the batch identifier

### Requirement: Sending and queue control are audited
The system SHALL record in the audit trail the start of each attempt, its result as Enviado or Error with its kind, the recovery of an interrupted attempt, and each pause and resume with the user who did it. The records SHALL hold no recipient credentials and no message content beyond the email and incident identifiers. (RNF-05, RF-19, MAIL-06)

#### Scenario: Result audited
- **WHEN** an email ends as Enviado or Error
- **THEN** an audit record names the system as actor, the email, the result and its kind, in the same transaction as the result

#### Scenario: Pause audited
- **WHEN** the administrator pauses or resumes the queue
- **THEN** an audit record names that user, the instant and the new status
