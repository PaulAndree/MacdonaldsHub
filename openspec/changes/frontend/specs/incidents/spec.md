# Spec Delta

## Purpose

Defines the interface for incidents after confirmation: listing, detail and export, the manual recording of claim results and recovered amounts with audited corrections, and manual entry of an incident with a human confirmation before it is saved.

## ADDED Requirements

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
