# Spec Delta

## ADDED Requirements

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
The system SHALL accept a manual incident with the same business fields and the same mandatory fields as the file. It SHALL check provider plus Order ID before saving: an existing key SHALL give a warning and create nothing, and a new key SHALL be saved only after the user reviews and confirms it. Whether a manual Uber Eats or Just Eat entry creates an email is pending P-12: until it is decided, no manual entry SHALL create an outbox record. (RF-22, E-13, P-12)

#### Scenario: Existing key
- **WHEN** the manual entry's provider and Order ID already exist
- **THEN** a warning is returned and no incident is created (E-13)

#### Scenario: New key reviewed and confirmed
- **WHEN** the user confirms a reviewed manual entry with a new key
- **THEN** the incident is created once, with audit, and no outbox record exists while P-12 is open
