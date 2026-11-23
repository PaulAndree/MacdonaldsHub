# xlsx-import Specification

## Purpose
Defines the import interface: how an administrator selects an XLSX file, follows its upload and processing, and how the input contract and absent optional values are displayed faithfully. The real parsing and validation belong to the backend.

## Requirements

### Requirement: File selection, upload and processing progress
The interface SHALL let an administrator select one XLSX file, show the upload progress and the processing state, and keep them informed until the batch reaches review or is rejected. (RF-01, RF-03)

#### Scenario: Upload followed by processing
- **WHEN** the administrator selects an XLSX file and starts the import
- **THEN** the interface shows the upload progress and then a processing state
- **AND** when processing ends the batch opens in review

#### Scenario: Upload interrupted
- **WHEN** the upload fails before the file reaches storage
- **THEN** the interface explains that the file was not stored and offers to select a file again
- **AND** no batch is shown as under review

### Requirement: Structure rejection with a reason
The interface SHALL show the reason when a file is rejected for its structure: a missing required header, more than one worksheet, or a corrupt or protected file. A rejected file SHALL NOT open a preview. File size and row limits SHALL NOT be shown as approved while P-06 is pending. (RF-02)

#### Scenario: Missing required header
- **WHEN** the example file lacks one of the headers Proveedor, Order ID or Fecha y hora
- **THEN** the interface shows that the file was rejected and names the missing header
- **AND** no preview is offered

#### Scenario: More than one worksheet
- **WHEN** the example file contains several worksheets
- **THEN** the interface shows the rejection and its reason

### Requirement: Notice for an identical file
The interface SHALL warn, before continuing the preparation, when the selected file matches a previously confirmed file. The notice SHALL NOT replace the row-level duplicate classification. (RF-03)

#### Scenario: File already confirmed
- **WHEN** the selected file is identical to a confirmed one
- **THEN** the interface shows the warning and lets the administrator continue or cancel
- **AND** the preview still classifies each row by its own key

### Requirement: Faithful display of the input contract
The interface SHALL present three required headers (Proveedor, Order ID, Fecha y hora) and five optional columns, and SHALL display absent optional values as unknown, never as zero or a made-up value. A missing branch SHALL read "Sin sucursal". Amounts SHALL keep their source decimals, and an incident time SHALL appear only when it exists, never as 00:00. (UI-01, RNF-13)

#### Scenario: File with only the three required headers
- **WHEN** the administrator reviews an example file that has only the three required headers
- **THEN** the preview is valid, optional values appear as unknown and the branch reads "Sin sucursal"

#### Scenario: Amount precision and absence
- **WHEN** an example amount has more than two decimals and another amount is absent
- **THEN** the first is shown with all its decimals and the second as unknown, not zero

#### Scenario: Incident date with and without time
- **WHEN** one incident has a date and a time and another has only a date
- **THEN** the first shows `YYYY-MM-DD` and `HH:MM` in Europe/Madrid time and the second shows only the date

### Requirement: Direct upload and worker processing
The API SHALL grant a temporary, create-only permission to upload one file for a batch of the requesting user, and SHALL register the batch. After the browser reports the upload, the single worker SHALL discover the batch from its persisted state, verify the stored file, and process it into staging. No separate import worker SHALL exist. (RF-01, RF-03, E-01)

#### Scenario: Preparation without definitive records
- **WHEN** a valid file has been processed
- **THEN** its rows exist only in staging and no incident or outbox record exists for the batch (E-01)

#### Scenario: Worker restarted during preparation
- **WHEN** the worker stops while a batch is Procesando
- **THEN** a worker that takes over continues the batch from its persisted state and creates no definitive incident (BE-09)

#### Scenario: Blob reference not from the batch
- **WHEN** the browser reports an upload for a batch that is not the user's, or for a file that does not exist
- **THEN** the API refuses the request and processes nothing

### Requirement: File structure validation
The system SHALL reject the whole file when it is corrupt, protected, has more than one worksheet, or lacks any of the three mandatory headers (Proveedor, Order ID, Fecha y hora). The five optional headers (Sucursal, Importe a reclamar, Costos de proveedor, Total, Descripción) SHALL be allowed to be missing. A rejection SHALL state its reason, and the batch SHALL become Rechazado. (RF-02, E-02)

#### Scenario: Missing mandatory header
- **WHEN** a file lacks the Order ID header
- **THEN** the file is rejected with that reason and no row is prepared

#### Scenario: Several worksheets
- **WHEN** a file has two worksheets
- **THEN** the file is rejected with the reason "several worksheets"

#### Scenario: Only the three mandatory headers
- **WHEN** a file has only the three mandatory headers
- **THEN** it is accepted and its optional values are absent (E-01)

### Requirement: File size limit
The system SHALL reject a file larger than 10 MB entirely, with that reason, and SHALL NOT truncate any file silently. There SHALL be no row limit other than the size limit. (P-06)

#### Scenario: File over the size limit
- **WHEN** a file larger than 10 MB is uploaded
- **THEN** the whole file is rejected with the reason that it exceeds the size limit

### Requirement: A curated file is assumed
The system SHALL ignore unrecognized extra headers and SHALL skip rows that are completely empty, without an error and without counting them as rows. It SHALL check the mandatory columns in every row, and SHALL accept optional columns as they come under the reading rules of this capability, with no further checks. (P-09)

#### Scenario: Extra column and blank rows
- **WHEN** a file has an unrecognized extra column and completely empty rows between data rows
- **THEN** the extra column is ignored and the empty rows are skipped without an error or a count

### Requirement: Formula cells are never evaluated
The system SHALL NOT evaluate formulas, SHALL NOT use a calculated value as validated data, and SHALL make a row an error, with the reason "celda con fórmula", when any of its cells holds a formula. (P-09)

#### Scenario: Cell holding a formula
- **WHEN** a row has a formula in a mandatory or an optional cell
- **THEN** the row is an error and no formula is evaluated

### Requirement: Row-level validation
The system SHALL invalidate a row, without stopping the others, when a mandatory value is absent, the provider is not `uber eats`, `just eat` or `glovo` after lowercasing, a supplied branch is not in the catalog, the Order ID is not text, the date or time does not follow the accepted formats, or a supplied amount is not numeric. Each invalid row SHALL carry a reason. An absent branch SHALL be valid and mean "Sin sucursal". (RF-06, E-05, BE-14)

#### Scenario: Branch absent and branch unknown
- **WHEN** one row has no branch and another has a branch that is not in the catalog
- **THEN** the first is valid without branch and the second is an error (E-05)

#### Scenario: Order ID as text and as a number
- **WHEN** one row has the Order ID `AB-1029x` as text and another has a numeric cell
- **THEN** the first is kept exactly as received and the second is an error ("Order ID debe ser texto") (BE-14)

### Requirement: Only provider and branch are normalized
The system SHALL convert only the provider and the branch to lowercase. It SHALL NOT trim spaces, resolve aliases, change the Order ID or normalize any other field. (RN-09)

#### Scenario: Provider with capitals
- **WHEN** a row has the provider `Uber Eats`
- **THEN** it is read as `uber eats`, and the Order ID is stored without any change

### Requirement: Amounts keep their source value
The system SHALL read an amount, when present, from a numeric cell, and keep its sign and exact decimal digits as in the file, including zero and negative values, with no sign validation and no rounding. An amount written as text, even if it looks like a number, SHALL make the row an error ("el importe debe ser numérico"). An empty amount SHALL be absent, never zero. Amounts SHALL never be handled as binary floating point. (RN-06, RNF-13, BE-06, BE-17)

#### Scenario: Numeric amounts with sign and precision
- **WHEN** a file has the numeric cells `-12.5`, `0` and `12.345`
- **THEN** the three are accepted with exactly those values (BE-17)

#### Scenario: Text amount
- **WHEN** an amount cell contains the text `12,50 €`
- **THEN** the row is an error with the reason that the amount must be numeric (BE-17)

#### Scenario: Absent amount
- **WHEN** an optional amount is empty and the column is present, or the column is missing
- **THEN** the amount is absent, not zero (BE-06)

### Requirement: Incident date and optional time
The system SHALL accept a native date or date-time cell, or a text exactly `YYYY-MM-DD` or `YYYY-MM-DD HH:MM`; any other text SHALL be a row error. A time SHALL be read as Europe/Madrid local time, with minute precision, and SHALL exist only when the source has it. A native cell whose time is exactly 00:00 SHALL be treated as a date without time, and a text with an explicit `00:00` SHALL keep that time. (RN-10, BE-12)

#### Scenario: Three date cells
- **WHEN** a file has a native `2026-10-12 20:22`, a native date only, and the text `12/10/2026`
- **THEN** the first keeps date and time, the second keeps only the date with no time invented, and the third is a row error (BE-12)

### Requirement: Descriptions preserved
The system SHALL keep line breaks and special characters of a description as received. They SHALL NOT be errors. (RN-09)

#### Scenario: Multi-line description
- **WHEN** a description contains line breaks and quotation marks
- **THEN** it is stored unchanged and treated safely when shown or exported

### Requirement: File fingerprint and identical-file notice
The system SHALL compute and store the SHA-256 of each uploaded file, and SHALL tell the user, before the review continues, that the file is identical to one already confirmed. The notice SHALL NOT replace deduplication. (RN-11, ADR-14)

#### Scenario: Same file uploaded again
- **WHEN** a file whose SHA-256 equals that of a confirmed file is uploaded
- **THEN** the notice is shown and every row is still classified against existing incidents
