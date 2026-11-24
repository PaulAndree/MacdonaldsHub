# Spec Delta

## ADDED Requirements

### Requirement: Sending and queue control are audited
The system SHALL record in the audit trail the start of each attempt, its result as Enviado or Error with its kind, the recovery of an interrupted attempt, and each pause and resume with the user who did it. The records SHALL hold no recipient credentials and no message content beyond the email and incident identifiers. (RNF-05, RF-19, MAIL-06)

#### Scenario: Result audited
- **WHEN** an email ends as Enviado or Error
- **THEN** an audit record names the system as actor, the email, the result and its kind, in the same transaction as the result

#### Scenario: Pause audited
- **WHEN** the administrator pauses or resumes the queue
- **THEN** an audit record names that user, the instant and the new status
