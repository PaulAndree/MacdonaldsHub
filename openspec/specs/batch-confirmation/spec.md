# batch-confirmation Specification

## Purpose
Defines the interface for the whole lifecycle of an import batch before it becomes definitive: the review of a prepared batch, the confirmation, and the explicit ways to discard it. The classification itself is produced by the backend, never by the browser.

## Requirements

### Requirement: Preview with four classes and reasons
The interface SHALL show a summary and row detail for the four classes (new, duplicate, in conflict, with error), with the reason each excluded row is excluded. The classification SHALL come from the backend and SHALL NOT be recomputed in the browser. (RF-04, RF-05, RF-06, UI-02)

#### Scenario: Mixed batch
- **WHEN** the administrator opens an example batch with rows of all four classes
- **THEN** the interface shows the counts per class and lets them open each row with its reason
- **AND** it is clear which rows will be imported and which are excluded

#### Scenario: Classification is not recomputed
- **WHEN** the supplied data classifies a row in a way the browser could contradict
- **THEN** the interface shows the supplied classification unchanged

### Requirement: Compared versions for conflicts
The interface SHALL show, for a conflict with an existing incident, both versions side by side with the differing fields marked, and for repeated keys inside the file all occurrences of the group. (RF-04)

#### Scenario: Conflict with an existing incident
- **WHEN** the administrator opens a conflicting row
- **THEN** the file version and the existing version are shown with the differing fields highlighted

### Requirement: Excluded-rows report
The interface SHALL let the administrator download a report of the excluded rows with their reasons, so they can correct and upload again. (RF-20)

#### Scenario: Download of the report
- **WHEN** the administrator requests the report for a batch with excluded rows
- **THEN** a file with each excluded row and its reason is offered for download

### Requirement: Preparation distinguished from definitive records
Before confirmation the interface SHALL label the batch as a temporary preparation and SHALL NOT show incidents or emails as created. After confirmation it SHALL show the real result: incidents created, emails pending and rows excluded. (RF-03, UI-03)

#### Scenario: Batch under review
- **WHEN** a batch is under review
- **THEN** the interface states that no incidents or emails exist yet and counts appear as "to create"

#### Scenario: Batch confirmed
- **WHEN** a batch is confirmed
- **THEN** the interface shows incidents created and pending emails separately from the excluded rows

### Requirement: Confirmation summary and notice of no undo
The confirmation SHALL summarize the incidents to create, the emails to generate, the Glovo incidents without email, the excluded rows, the test recipient and the template reviewed, and SHALL state that there is no undo and no later cancellation of emails. The template text SHALL be marked as an example while P-03 is pending. (RF-07, UI-03)

#### Scenario: Summary before confirming
- **WHEN** the administrator reaches the confirmation step
- **THEN** the summary lists the counts, the test recipient and the template
- **AND** the no-undo notice is visible before the action

### Requirement: Single action and uncertain outcome
While the confirmation is awaiting a response the interface SHALL disable the action so a double click cannot repeat it. If the request fails, the interface SHALL NOT claim that nothing was confirmed and SHALL offer to check the batch status. A repeated confirmation SHALL show the stored result. (RF-08, RF-09)

#### Scenario: Double click
- **WHEN** the administrator clicks confirm twice quickly
- **THEN** only one confirmation is requested and the control stays disabled until the response

#### Scenario: Network failure
- **WHEN** the confirmation request fails without a response
- **THEN** the interface says the outcome is unknown and offers to check the batch status

### Requirement: Matches found at confirmation
When a row becomes a duplicate between review and confirmation, the result SHALL list it as excluded with the reason and show the real totals. (RF-10)

#### Scenario: Match found at confirmation
- **WHEN** the example result reports a row excluded at confirmation
- **THEN** the interface shows that row among the excluded and the totals actually created

### Requirement: Cancel before confirmation
The interface SHALL offer cancel only while the batch is unconfirmed. A cancelled or discarded batch SHALL NOT be confirmable. (RF-17, UI-04)

#### Scenario: Cancel
- **WHEN** the administrator cancels an unconfirmed batch
- **THEN** the batch is shown as discarded and its confirm action is no longer offered

#### Scenario: Batch already confirmed
- **WHEN** a batch is confirmed
- **THEN** the interface offers no cancel action

### Requirement: Cerrar sesión discards unconfirmed batches
The Cerrar sesión button SHALL ask for confirmation when the user has an unconfirmed batch, state that it will be discarded, and only discard batches. It SHALL NOT end the Google session. If the discard fails, it SHALL say so and leave the batch unchanged. (RF-17, UI-04)

#### Scenario: Cerrar sesión with a batch under review
- **WHEN** the administrator presses Cerrar sesión with an unconfirmed batch
- **THEN** the interface asks for confirmation and states that the batch will be discarded
- **AND** after confirming, the batch shows as discarded and the Google session remains

#### Scenario: Discard fails
- **WHEN** the discard request fails
- **THEN** the interface reports the failure and the batch stays under review

### Requirement: No expiry and pending-batch notice
The interface SHALL NOT show any expiry countdown. When the user returns and has a batch under review, it SHALL show a notice with actions to resume, confirm or cancel it. (RF-17)

#### Scenario: Return with a pending batch
- **WHEN** the administrator signs in again while a batch is under review
- **THEN** a notice offers to resume, confirm or cancel that batch

### Requirement: One unconfirmed batch per user
While the user has an unconfirmed batch the interface SHALL disable new uploads and explain why, naming the pending batch and offering to resume or cancel it. A rejected batch SHALL NOT block a new upload. (UI-12)

#### Scenario: Upload while a batch is pending
- **WHEN** the administrator tries to upload a file with a batch under review
- **THEN** the upload is blocked, the pending batch is indicated and resume or cancel is offered

#### Scenario: Previous batch rejected
- **WHEN** the previous batch was rejected for its structure
- **THEN** a new upload is allowed
