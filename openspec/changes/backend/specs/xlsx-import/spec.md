# Spec Delta

## ADDED Requirements

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
