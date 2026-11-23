# Spec Delta

## Purpose

Defines the interface for the email queue: the states of each email, their reasons and totals, the global pause and resume, and the guarantee shown to the user that each email has a single attempt with no retry, resend or later cancellation.

## ADDED Requirements

### Requirement: Queue states and totals
The interface SHALL show each email as Pendiente, Enviando, Enviado or Error, with totals per state. A completed batch SHALL be able to show both Enviado and Error totals, and a completed batch SHALL NOT be presented as a total success. (RF-11, RF-13)

#### Scenario: Completed batch with failures
- **WHEN** all emails of a batch have ended and some are in Error
- **THEN** the batch shows as completed with separate totals of Enviado and Error

### Requirement: Error reason and no retry actions
The interface SHALL show the reason for each Error and SHALL NOT offer retry, resend or cancel actions. An Error caused by an interruption SHALL be described as an unverifiable result that does not prove the email was not received. (UI-07, RF-13)

#### Scenario: Send ends in Error
- **WHEN** an example send ends in Error
- **THEN** the reason is shown and no retry, resend or cancel action exists

#### Scenario: Interrupted attempt
- **WHEN** an email is in Error because its result could not be verified
- **THEN** the message says the result is unverified and the email may have been delivered

### Requirement: Pause and resume
An administrator SHALL be able to pause and resume the queue, and the interface SHALL show that the queue is paused. On pausing it SHALL explain that an attempt already started may finish and no other starts. (UI-08, RF-14)

#### Scenario: Pausing with an attempt in progress
- **WHEN** the administrator pauses the queue while one email is Enviando
- **THEN** the interface states that this attempt may finish and no new attempt starts until resumed

#### Scenario: User without permission
- **WHEN** a user who is not an administrator opens the queue
- **THEN** the pause and resume controls are absent

### Requirement: One attempt and minimum spacing shown
The interface SHALL state that each email has a single attempt and that at least 30 seconds separate the start of consecutive attempts. (RF-11)

#### Scenario: Queue with several pending emails
- **WHEN** the queue has several pending emails
- **THEN** the interface shows the single-attempt rule and the 30-second minimum between starts

### Requirement: Only email providers and the test recipient
The queue SHALL include only Uber Eats and Just Eat incidents, and a batch containing only Glovo incidents SHALL show no emails. In the test environment the only recipient shown SHALL be the test recipient, marked as such. (RF-12)

#### Scenario: Glovo-only batch
- **WHEN** the user opens the queue of a batch that has only Glovo incidents
- **THEN** it shows no email entries

#### Scenario: Recipient in the test environment
- **WHEN** the test environment shows an email recipient
- **THEN** it is the configured test recipient, labelled as a test recipient
