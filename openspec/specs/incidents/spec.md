# incidents Specification

## Purpose
Defines the interface for incidents after confirmation: listing, detail and export, the manual recording of claim results and recovered amounts with audited corrections, and manual entry of an incident with a human confirmation before it is saved.

## Requirements

### Requirement: Incident list, filters and detail
The interface SHALL list incidents with filters by provider, branch, status and date, and a detail view with the status history. The detail SHALL show the incident, claim and recovery dates as distinct values. (RF-16, RF-21)

#### Scenario: Filtering
- **WHEN** the user filters by provider and status
- **THEN** only matching incidents are listed and the active filters are visible

#### Scenario: Detail with history
- **WHEN** the user opens an incident
- **THEN** the detail shows its status history with actor, date, previous and new value, and the three dates separately

### Requirement: Export keeps filters and optional values
The interface SHALL export the incidents that match the active filters, keeping absent optional values explicit (Sin sucursal, unknown amount) instead of replacing them with zero. (RF-16)

#### Scenario: Export of a filtered list
- **WHEN** the user exports a filtered list that includes an incident without branch and without amount
- **THEN** the exported content respects the filters and shows those values as absent, not zero

### Requirement: Incident states and no email retry
The interface SHALL present the incident states Importada (sin correo), Pendiente de envío, Reclamada, Error de envío, Resuelta and Rechazada. It SHALL NOT offer any action that returns an incident from Error de envío to Pendiente de envío. (RF-21, RF-13)

#### Scenario: Incident in Error de envío
- **WHEN** the user opens an incident in Error de envío
- **THEN** the detail shows the reason and offers no retry or resend action

### Requirement: Manual Glovo claim
The interface SHALL let an administrator mark a Glovo incident as Reclamada with a claim date. The external channel used to claim SHALL NOT be assumed while P-11 is pending. (RF-21)

#### Scenario: Marking a Glovo claim
- **WHEN** the administrator marks a Glovo incident as claimed and enters the date
- **THEN** the incident shows Reclamada with that claim date, separate from email claims

### Requirement: Resolution with an explicit recovered amount
The interface SHALL let an administrator record Resuelta or Rechazada with an explicit recovered amount, including a partial one. Resuelta SHALL NOT imply that the whole claimed amount was recovered. (UI-05, RF-21)

#### Scenario: Partial recovery
- **WHEN** the administrator records a resolved incident with a recovered amount lower than the claimed one
- **THEN** the detail shows the explicit recovered amount and the recovery date, and does not show the claim as fully recovered

### Requirement: Audited correction of a result
The interface SHALL let an administrator correct a recorded result and SHALL show the correction in the history with actor, date, previous value, new value and reason. A correction SHALL NOT be presented as undoing the import or any email. (UI-05, RF-21)

#### Scenario: Correcting a marking
- **WHEN** the administrator corrects a result already recorded as final
- **THEN** the history shows the correction and the detail states that the batch and emails are unchanged

### Requirement: Manual entry with human confirmation
The interface SHALL provide a form with the same business fields and basic obligations as the XLSX, warn about a duplicate or conflict by provider and order ID without creating another incident, and require a review and confirmation before an accepted entry appears as saved. Email generation for Uber Eats and Just Eat SHALL NOT be offered while P-12 is pending. (RF-22, UI-09)

#### Scenario: Duplicate entry
- **WHEN** the administrator enters a provider and order ID that already exist
- **THEN** the form warns about the duplicate or conflict and the entry is rejected

#### Scenario: New entry
- **WHEN** the administrator enters a new incident
- **THEN** the interface shows a review step and the incident figures as saved only after the administrator confirms

#### Scenario: Email option pending
- **WHEN** the administrator enters a new Uber Eats incident
- **THEN** the form does not offer to generate an email and indicates the decision is pending

### Requirement: Incident uniqueness guaranteed by PostgreSQL
The system SHALL guarantee with a PostgreSQL constraint that only one incident exists per provider and Order ID, whatever the batch or the concurrency. The branch SHALL NOT be part of the key. (RN-01, BE-03)

#### Scenario: Two batches insert the same key
- **WHEN** two confirmations try to create the same provider and Order ID
- **THEN** exactly one incident exists and the other row is reported as excluded

### Requirement: Initial state and state history
A new incident SHALL start as Pendiente de envío when it has an outbox record, and as Importada (sin correo) when it has none. The system SHALL record every state change with actor, instant, previous value, new value and reason when one applies. A state in Error de envío SHALL NOT return to Pendiente de envío. (RN-15, RF-21)

#### Scenario: Glovo incident created
- **WHEN** a Glovo incident is created by a confirmation
- **THEN** its state is Importada (sin correo) and its history starts with that state

### Requirement: Query and export with filters
The system SHALL list incidents with filters by provider, branch, state and date (incident, claim or recovery), and SHALL export to XLSX the incidents matching the same filters. Absent values and "Sin sucursal" SHALL be explicit, and amounts SHALL keep their source precision in the list, the detail and the export. A user with the consultation role SHALL be able to read. (RF-16, RNF-13)

#### Scenario: Export with a filter
- **WHEN** the user exports with provider and date filters applied
- **THEN** the file holds exactly the matching incidents, with optional values kept

#### Scenario: Amount with many decimals
- **WHEN** an incident has the amount `12.345`
- **THEN** the detail, the list and the export show `12.345` and not a rounded value

### Requirement: Manual Glovo claim recorded
The system SHALL let the administrator mark a Glovo incident as Reclamada with a claim date, recording the actor. The external claim channel is pending P-11. Importing or creating an outbox record SHALL NOT count as claiming. (RF-21, P-11)

#### Scenario: Marking a claim
- **WHEN** the administrator marks a Glovo incident as claimed on a date
- **THEN** it becomes Reclamada with that claim date and a history entry

### Requirement: Resolution stored with an explicit recovered amount
The system SHALL let the administrator record Resuelta or Rechazada on a claimed incident, with a recovery date and an explicit recovered amount that may be partial. Resuelta SHALL NOT imply the whole claimed amount was recovered. Restrictions on the recovered amount are pending P-04 and SHALL NOT be invented. (RF-21, E-12)

#### Scenario: Partial recovery
- **WHEN** the administrator records Resuelta with a recovered amount lower than the claimed one
- **THEN** the recovered amount is stored as entered and the claimed amount is unchanged

### Requirement: Correction stored with its history
The system SHALL allow correcting a recorded result, even one considered final, keeping the previous value in the history, the actor and the instant. A correction SHALL NOT revert the import or any email. (RF-21, E-12)

#### Scenario: Correct a partial recovery
- **WHEN** a result is corrected
- **THEN** the history shows the previous and the new value, and the batch and email states do not change

### Requirement: Distinct dates
The system SHALL store the incident date, the claim date and the recovery date separately, and SHALL store the incident time only when the source had one. System timestamps SHALL be stored in UTC. (RNF-13, BE-12)

#### Scenario: Incident without time
- **WHEN** an incident was imported from a date without time
- **THEN** its time is absent and no time is invented anywhere

### Requirement: Manual entry checked against the key
The system SHALL accept a manual incident with the same business fields and the same mandatory fields as the file. It SHALL check provider plus Order ID before saving: an existing key SHALL give a warning and create nothing, and a new key SHALL be saved only after the user reviews and confirms it. (RF-22, E-13)

#### Scenario: Existing key
- **WHEN** the manual entry's provider and Order ID already exist
- **THEN** a warning is returned and no incident is created (E-13)

#### Scenario: New key reviewed and confirmed
- **WHEN** the user confirms a reviewed manual entry with a new key
- **THEN** the incident is created once, with audit
