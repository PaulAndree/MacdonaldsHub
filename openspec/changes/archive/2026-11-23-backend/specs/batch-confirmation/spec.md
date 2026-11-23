# Spec Delta

## ADDED Requirements

### Requirement: Exclusive classification of rows
The system SHALL assign every row exactly one class: Con error, En conflicto, Duplicada or Nueva. Invalid rows SHALL be Con error and are identified first. The key SHALL be provider plus Order ID, and the branch SHALL NOT be part of it. (RN-01, RN-02, RF-04)

#### Scenario: Conflict prevails over duplicate
- **WHEN** valid rows share a key and any of them differs from the others or from an existing incident
- **THEN** every row of that key is En conflicto, not Duplicada

### Requirement: Conditions of each class
Among valid rows, a row SHALL be Duplicada when it has the same key and the same relevant fields as an existing incident or as an identical repetition in the file; En conflicto when a relevant field differs from an existing incident with that key or from another valid row of the file with that key; and Nueva only when it has no match and its key appears once among valid rows of the file. (RN-02, E-03, E-04)

#### Scenario: Existing key with equal fields
- **WHEN** a valid row matches an existing incident in every relevant field
- **THEN** it is Duplicada and excluded (E-03)

#### Scenario: Existing key with different fields
- **WHEN** a valid row matches an existing incident but a relevant field differs
- **THEN** it is En conflicto and both versions are available to the user (E-04)

#### Scenario: Repeated key inside the file
- **WHEN** the file repeats a key with identical data, or with differing data
- **THEN** every occurrence is Duplicada in the first case and En conflicto in the second, and none is chosen for import (BE-01)

### Requirement: Relevant fields and comparison
The system SHALL compare incident date and time, branch, claim amount, provider costs, total and description. A missing optional column and an empty optional cell SHALL be the same absent value. Amounts SHALL be compared by decimal value without rounding. Presence or absence of a time, or a different time, SHALL be a relevant difference. (RN-02, BE-13, BE-06)

#### Scenario: Same key with and without time
- **WHEN** a row repeats an existing incident's key but has no time where the incident has one
- **THEN** the row is En conflicto by the date and time difference (BE-13)

#### Scenario: Equal amounts written differently
- **WHEN** two rows with the same key differ only in how an equal decimal value was written
- **THEN** they are compared as equal in that field

### Requirement: Only new valid rows are imported
The system SHALL create incidents only from Nueva rows. Duplicates, conflicts and errors SHALL create no incident and no outbox record. No row SHALL be excluded because of the age of its incident. (RN-03, RN-13, RF-05, RF-06)

#### Scenario: Old incident date
- **WHEN** a valid new row has an incident date from long ago
- **THEN** it is still Nueva

### Requirement: Staging and preview served by the API
The system SHALL keep prepared rows in temporary staging and SHALL serve the preview from it: counts per class, a reason for each excluded row, both versions for conflicts with existing data, and the file fingerprint. Rows SHALL be pageable and filterable by class, with the total always stated. (RF-03, RF-04, RNF-01)

#### Scenario: Large preview
- **WHEN** a batch has 600 prepared rows
- **THEN** the preview reports the total and pages through all of them, with none silently omitted

### Requirement: Excluded-rows report generation
The system SHALL generate, on request, an XLSX with the excluded rows, their class and reasons, in a form the user can correct and upload again. Incidents already confirmed SHALL be classified again on re-upload and SHALL NOT generate another email. (RF-20)

#### Scenario: Corrected file uploaded again
- **WHEN** the user uploads a corrected file containing rows already confirmed
- **THEN** those rows are Duplicada and no second outbox record is created

### Requirement: Atomic confirmation in one transaction
The system SHALL, in one PostgreSQL transaction, lock the batch, recheck its state, revalidate against the incidents existing at that moment, insert the new incidents, create the outbox records, store the confirmed state with its result and write the audit record. A failure SHALL leave no incident, no outbox record and no confirmation of the batch. (RF-07, RF-08, ADR-06, E-06, E-08)

#### Scenario: Eighty new rows with twenty Glovo
- **WHEN** a batch with 80 new valid rows, 20 of them Glovo, is confirmed
- **THEN** 80 incidents and 60 pending emails exist in one transaction, and nothing has been sent (E-06)

#### Scenario: Failure midway
- **WHEN** an error occurs after some incidents were inserted but before the transaction ends
- **THEN** no incident, outbox record or confirmed state remains for the batch (E-08)

### Requirement: Confirmation limited to the reviewed batch
The system SHALL allow confirmation only to an authorized administrator, only for a batch of theirs that is En revisión and not discarded, and only for the reviewed file version identified by its SHA-256. (RF-07, ADR-14)

#### Scenario: Different file version
- **WHEN** the confirmation names a hash that differs from the reviewed file's
- **THEN** it is refused and nothing is created

#### Scenario: Batch of another user or already discarded
- **WHEN** a user confirms a batch that is not theirs or that was discarded
- **THEN** it is refused and nothing is created

### Requirement: Idempotent and concurrent confirmation
The system SHALL return the stored result for a second confirmation of the same batch without reading staging and without creating incidents, outbox records or audit effects again, including when two confirmations run at the same time. (RF-09, E-07, BE-03, BE-11)

#### Scenario: Repeated request
- **WHEN** the confirmation is sent twice
- **THEN** the second returns the same result and the record counts do not change (E-07)

#### Scenario: Simultaneous requests
- **WHEN** two confirmations of the batch run concurrently
- **THEN** exactly one creates records and the other returns its result (BE-03)

#### Scenario: Repeated after staging cleanup
- **WHEN** staging was cleaned after confirming and the confirmation is repeated
- **THEN** the stored result is returned and incidents and original are intact (BE-11)

### Requirement: Matches that appear during review
The system SHALL exclude at confirmation a row whose key was created by another batch after the preview, import the rest, and report each excluded row with its reason in the result. (RF-10, BE-02)

#### Scenario: Another batch confirms the same key
- **WHEN** another batch confirms a key while this batch is under review
- **THEN** that row is excluded at confirmation, the remaining new rows are imported, and the result lists the exclusion (BE-02)

### Requirement: Original kept separately from the transaction
The system SHALL, after the confirmation transaction, copy the original to the immutable confirmed store under a name determined by the batch, verify its SHA-256 and record the verified link. Storage SHALL NOT take part in the PostgreSQL transaction. (ADR-14, RF-19)

#### Scenario: Copy verified
- **WHEN** the copy finishes and its SHA-256 equals the reviewed one
- **THEN** the link is recorded as verified

#### Scenario: Discrepancy
- **WHEN** the stored copy differs from the reviewed hash
- **THEN** the discrepancy is recorded and alerted and the original is not replaced by another file

### Requirement: Uploads cannot overwrite
The system SHALL NOT allow an upload to overwrite an existing file, and cleanup SHALL NOT delete the file of a confirmed batch while its copy to the confirmed store is not verified. (ADR-14, BE-05)

#### Scenario: Second upload to the same blob
- **WHEN** a second upload targets a blob that already exists
- **THEN** it is refused and the first file is unchanged


#### Scenario: Copy fails after the transaction
- **WHEN** the copy to the confirmed store fails
- **THEN** the batch stays confirmed, the failure is recorded and alerted, the temporary file is kept, and the copy is retried

### Requirement: Explicit discard
The system SHALL discard an unconfirmed batch of the user when they cancel it, and SHALL discard all their unconfirmed batches when the Cerrar sesión operation is called. A batch in Subido, Procesando or En revisión SHALL be discardable. Discarding SHALL make the batch unconfirmable and remove its file and staging, without ending the Easy Auth session. If the call fails the batch SHALL keep its state and the user SHALL be informed. (RF-17, E-11, BE-15)

#### Scenario: Cancel or Cerrar sesión
- **WHEN** the user cancels, or calls Cerrar sesión, with an unconfirmed batch
- **THEN** the file and staging are removed and the batch cannot be confirmed (E-11)

#### Scenario: Discard call fails
- **WHEN** the discard fails
- **THEN** the batch stays En revisión unchanged and the failure is reported (BE-15)

#### Scenario: Stuck processing
- **WHEN** a batch is Procesando and cannot finish
- **THEN** the user can still discard it

### Requirement: No automatic expiry
The system SHALL NOT discard or expire an unconfirmed batch automatically, including after an unexpected browser closure. (RF-17, BE-04)

#### Scenario: Browser closed during review
- **WHEN** the browser closes with a batch En revisión
- **THEN** the batch is still En revisión and confirmable, and the user can resume, confirm or cancel it (BE-04)

### Requirement: One unconfirmed batch per user enforced by the database
The system SHALL allow each user at most one batch in Subido, Procesando or En revisión, guaranteed by a PostgreSQL constraint that holds under simultaneous requests. A Rechazado batch SHALL NOT count. A second request SHALL be refused naming the pending batch. (E-11, BE-16)

#### Scenario: Two simultaneous uploads
- **WHEN** the user requests two upload permissions at the same time
- **THEN** one is granted and the other is refused naming the pending batch, and two such batches never exist (BE-16)

#### Scenario: Rejected batch
- **WHEN** the user's last batch is Rechazado
- **THEN** a new upload is allowed

### Requirement: Cleanup coordinated with confirmation
The system SHALL coordinate cleanup and confirmation on the batch state in PostgreSQL so that cleanup never deletes the data or original of a confirmed batch and a discarded batch is never confirmed. A failed physical removal SHALL be recorded and completed later, and the system SHALL NOT claim it removed what is still stored. The cadence of physical cleanup is pending P-05. (BE-05, P-05)

#### Scenario: Cleanup and confirmation at the same time
- **WHEN** cleanup and confirmation of a batch run concurrently
- **THEN** a confirmed original is never deleted and a discarded batch is never confirmed (BE-05)

### Requirement: Batch completion
The system SHALL mark a confirmed batch Completado when all its emails are Enviado or Error, and SHALL allow a confirmed batch with no emails to be Completado at confirmation. Completado SHALL NOT mean that every send succeeded. Emails are sent from change 3. (RF-11)

#### Scenario: Glovo-only batch
- **WHEN** a batch whose new rows are all Glovo is confirmed
- **THEN** it can be Completado at once, with no email
