# Spec Delta

## ADDED Requirements

### Requirement: One consumer in the single worker
The system SHALL send the pending emails from the single worker that holds the PostgreSQL ownership of the work, one at a time, and never from an API request, a trigger or a callback. It SHALL take only emails of Uber Eats and Just Eat, in the order they were created, and Glovo SHALL have no email and no attempt. When two revisions of the worker overlap, only the one that holds the ownership SHALL send. (RF-11, RN-04, MAIL-04, MAIL-11)

#### Scenario: Two worker revisions overlap
- **WHEN** two worker processes run at the same time
- **THEN** only the owner of the work starts attempts and no email is attempted twice

#### Scenario: Glovo-only batch
- **WHEN** a batch contains only Glovo incidents
- **THEN** there is no email record and no attempt for it (MAIL-11)

### Requirement: Global minimum interval between starts
The system SHALL start the attempt of an email at least 30 seconds after the start of the previous attempt, whatever its result, and the interval SHALL be global to the sender, kept in PostgreSQL so that restarts and overlapping revisions do not shorten it. The interval SHALL NOT be configurable. (RN-05, ADR-09, MAIL-01)

#### Scenario: Two or more pending emails
- **WHEN** several emails are pending and sending is active
- **THEN** their attempts start at least 30 seconds apart

#### Scenario: The previous attempt failed
- **WHEN** the previous attempt ended in Error
- **THEN** the next one still waits for 30 seconds from the start of that attempt

#### Scenario: Restart between attempts
- **WHEN** the worker restarts 10 seconds after an attempt started
- **THEN** the next attempt does not start before 30 seconds have passed since that start

### Requirement: A single attempt, recorded before it starts
The system SHALL record durably, before it calls the mail service, that the attempt of an email has started, moving it from Pendiente to Enviando with its start time, and SHALL make at most one attempt per email. No automatic retry, no manual resend and no cancellation of an email SHALL exist. (RN-12, ADR-09, E-10)

#### Scenario: The start is recorded first
- **WHEN** an attempt is about to call the mail service
- **THEN** the email is already Enviando with its start time in the database

#### Scenario: No second attempt
- **WHEN** an email is Enviado or Error
- **THEN** nothing sends it again, whatever the cause or the configuration afterwards

### Requirement: The result is recorded as sent or error
The system SHALL record Enviado, with its end time, when the send operation finishes without error, and Error, with its end time and a reason, otherwise. A refusal by the mail service SHALL be an Error of kind send failed, and a lost connection or a timeout after the message was handed over SHALL be an Error of kind unverified result. Enviado SHALL NOT claim that the email was delivered. (RN-12, RF-13, E-10, MAIL-06)

#### Scenario: The send operation finishes without error
- **WHEN** the mail service accepts the message
- **THEN** the email is Enviado with its end time

#### Scenario: The mail service refuses
- **WHEN** the mail service refuses the message
- **THEN** the email is Error with the reason and the kind send failed, and no new attempt is made (E-10)

#### Scenario: The connection is lost after the message was handed over
- **WHEN** the connection is lost or times out without a verifiable answer
- **THEN** the email is Error with the kind unverified result and is not sent again

### Requirement: An interrupted attempt ends in error without sending again
The system SHALL turn an email left Enviando by an interrupted process into Error of kind unverified result, with a reason that says the outcome could not be verified, as soon as a worker takes over, and SHALL NOT send it again. Pending emails SHALL continue respecting pause and interval. (RNF-03, MAIL-03, MAIL-07)

#### Scenario: Restart with a pending and an unverifiable email
- **WHEN** the worker restarts with pending emails and one Enviando
- **THEN** the Enviando one becomes Error without another send and the pending ones continue after the interval

#### Scenario: Accepted but not recorded
- **WHEN** the mail service accepted the message and the process stopped before recording the success
- **THEN** the recovery records Error as unverified and the email is not sent again

### Requirement: Persistent pause controlled by the administrator
The system SHALL keep a global pause, persisted in PostgreSQL, that stops new attempts without cancelling the one in progress and without changing any finished email. A new environment SHALL start paused, so that no email leaves until the administrator resumes it. Only a user with the queue permission SHALL pause or resume, and a refusal SHALL change nothing. (RF-14, MAIL-02, MAIL-09)

#### Scenario: Pausing with an attempt in progress
- **WHEN** the queue is paused while one email is Enviando
- **THEN** that attempt can finish and no other starts until it is resumed (MAIL-02)

#### Scenario: A new environment
- **WHEN** an environment is created
- **THEN** its queue is paused and nothing is sent until the administrator resumes it

#### Scenario: Pause survives a restart
- **WHEN** the worker restarts while the queue is paused
- **THEN** it remains paused and sends nothing

#### Scenario: A user without permission
- **WHEN** a user without the queue permission pauses or resumes
- **THEN** the API denies it and nothing changes (MAIL-09)

### Requirement: The queue is consultable
The system SHALL serve the queue with its pause status and the attempts in progress, the totals per state, the progress of each batch with its own totals, and the emails, filterable by state and batch and paged with the total always stated. The response SHALL state the 30-second minimum and the single attempt per email, and the time before which the next attempt cannot start. (RF-14, RNF-02)

#### Scenario: Completed batch with failures
- **WHEN** all the emails of a batch have ended and some are in Error
- **THEN** the batch is shown as completed with separate totals of Enviado and Error

#### Scenario: Filter by state
- **WHEN** the queue is read with a state filter
- **THEN** only emails in that state are listed while the totals still describe the whole queue

### Requirement: Queue entries show their outcome and recipient
Each email in the queue SHALL show its state, the reason and kind of its error, its start and end times, its incident and its recipient as the test recipient. An email of a manual entry, which belongs to no batch, SHALL show no batch and SHALL count in the totals. (RF-14, RF-13)

#### Scenario: Email of a manual entry
- **WHEN** the queue includes the email of a manual entry
- **THEN** it is listed with no batch and counts in the totals

#### Scenario: Email in error
- **WHEN** an email ended in Error
- **THEN** its reason and its kind, failed or unverified, are shown and no action to retry it exists

### Requirement: Only the authorized test recipient is used
The system SHALL send only to the recipient stored with the email when it is authorized, which until real recipients are defined means the configured test recipient, and SHALL NOT send to a real provider. An email whose stored recipient is not an authorized one SHALL end in Error without any call to the mail service, and a change of the configured recipient or template SHALL NOT alter emails already authorized. (RN-08, RF-12, E-09, MAIL-05, MAIL-10)

#### Scenario: Test environment
- **WHEN** the test environment sends
- **THEN** every email reaches only the test recipient and none counts in production figures (E-09)

#### Scenario: Recipient not authorized
- **WHEN** an email stores a recipient that is not the authorized test recipient
- **THEN** it ends in Error without calling the mail service (MAIL-10)

#### Scenario: Configuration edited after confirming
- **WHEN** the recipient or the template is edited after emails were authorized
- **THEN** they are sent with the content and destination they stored (MAIL-05)

### Requirement: Sending is unavailable until it is configured and safe
The system SHALL NOT start attempts, and SHALL leave the emails pending and say why in the queue, when no test recipient or no mail transport is configured. A production environment SHALL NOT send while no real recipient is defined. Unavailability SHALL NOT turn any email into an error. (RN-08, MAIL-10)

#### Scenario: Nothing configured
- **WHEN** no test recipient or no mail transport is configured
- **THEN** no attempt starts, the emails stay pending and the queue says that sending is unavailable

#### Scenario: Production without real recipients
- **WHEN** the production environment has pending emails and no real recipient is defined
- **THEN** it sends nothing

### Requirement: Mail transport by configuration
The system SHALL send through the transport selected by configuration: locally an SMTP capture service that relays nothing, and in Azure the institutional mailbox with credentials taken from the secret store. Credentials SHALL NOT appear in code, the outbox, logs or the audit, and a transport call SHALL have a time limit shorter than the interval. (RNF-04, P-02)

#### Scenario: Local environment
- **WHEN** sending is active locally
- **THEN** the message appears in the capture service and reaches no provider

### Requirement: Content of the message
The system SHALL build each message from the subject and body stored with the email, with the incident number (Order ID) as the only variable, and SHALL NOT include any amount or free description. (RN-14, P-03)

#### Scenario: Content of the message
- **WHEN** a message is built
- **THEN** it contains the stored subject and body with the Order ID in place of the variable, and nothing else of the incident

## MODIFIED Requirements

### Requirement: Outbox records created at confirmation, never sent
The system SHALL create exactly one outbox record, in state Pendiente, for each new Uber Eats or Just Eat incident created by a confirmation, and none for Glovo. No email SHALL be sent from a request, a trigger or a callback of the confirmation: the records wait for the consumer of the worker. (RN-04, RF-08, E-06)

#### Scenario: Confirmation with Glovo incidents
- **WHEN** a batch with Uber Eats, Just Eat and Glovo rows is confirmed
- **THEN** each Uber Eats and Just Eat incident has one Pendiente record, Glovo has none, and nothing is sent by the confirmation

## REMOVED Requirements

### Requirement: Email queue operations left to change 3
**Reason**: Change 3 serves the three operations that read the queue and pause or resume it, so nothing remains deferred.
**Migration**: The contract test no longer lists deferred operations; see the platform requirement that no approved operation remains deferred.
