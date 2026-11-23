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
