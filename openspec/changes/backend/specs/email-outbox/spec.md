# Spec Delta

## ADDED Requirements

### Requirement: Outbox records created at confirmation, never sent
The system SHALL create exactly one outbox record, in state Pendiente, for each new Uber Eats or Just Eat incident created by a confirmation, and none for Glovo. No email SHALL be sent from a request, a trigger or a callback of the confirmation, and sending SHALL stay disabled in this change. (RN-04, RF-08, E-06)

#### Scenario: Confirmation with Glovo incidents
- **WHEN** a batch with Uber Eats, Just Eat and Glovo rows is confirmed
- **THEN** each Uber Eats and Just Eat incident has one Pendiente record, Glovo has none, and nothing is sent

### Requirement: Manual entries of email providers create their email
The system SHALL create, in the same transaction that saves a reviewed manual entry of Uber Eats or Just Eat, one outbox record in state Pendiente with the authorized recipient and template, and SHALL create none for a Glovo entry, which is claimed by hand. It SHALL refuse the entry when an email is needed and no recipient is configured, and SHALL send nothing from the request. (RF-22, RN-04, P-12)

#### Scenario: Manual Uber Eats entry
- **WHEN** a reviewed manual entry of Uber Eats or Just Eat is saved
- **THEN** the incident is Pendiente de envío and has one Pendiente outbox record, created in the same transaction

#### Scenario: Manual Glovo entry
- **WHEN** a reviewed manual entry of Glovo is saved
- **THEN** it has no outbox record and can be claimed by hand

#### Scenario: No recipient configured
- **WHEN** an Uber Eats or Just Eat entry is saved and no recipient is configured
- **THEN** nothing is created and the user is told why

### Requirement: Authorized recipient and template kept in the outbox
Each outbox record SHALL keep the recipient and the template version authorized at confirmation, without secrets. A later edit of the configured recipient or template SHALL NOT change records already created. Until real recipients are defined (P-01), only the configured test recipient SHALL be allowed. The template text is pending P-03; the only variable is the incident number (Order ID), and amounts and free description SHALL NOT be included. (RN-07, RN-14, BE-07, P-01, P-03)

#### Scenario: Configuration edited after confirming
- **WHEN** the recipient or template is edited after a batch was confirmed
- **THEN** the batch's outbox records keep the authorized version (BE-07)

### Requirement: Test data isolation
The system SHALL keep test batches, outbox records, storage and metrics in the test environment's own database and storage, and SHALL NOT promote them to production. (RN-08)

#### Scenario: Test environment recipients
- **WHEN** the test environment creates outbox records
- **THEN** their recipient is the configured test recipient and no production store holds them

### Requirement: Email queue operations left to change 3
The operations of the approved contract that read the email queue and pause or resume it SHALL NOT be implemented in this change; they belong to change 3. Until then the generated API SHALL NOT claim to serve them. (BE-18)

#### Scenario: Contract test and the queue operations
- **WHEN** the contract test runs in this change
- **THEN** the three queue operations are listed as deferred to change 3 and every other approved operation is compared
