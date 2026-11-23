# Spec Delta

## ADDED Requirements

### Requirement: Backend permissions by role for every operation
The API SHALL authorize each operation by the caller's role after the allowlist check: the administrator may import, confirm, record results and manual entries, and read; the global manager, if enabled, may only read incidents, history and the dashboard. A user outside the allowlist, or with a read-only role attempting a change, SHALL be refused with 403 and nothing SHALL change. (RNF-04, BE-08, UI-10)

#### Scenario: Read-only role tries to change
- **WHEN** a global manager calls an operation that confirms, discards, records a result or creates an incident
- **THEN** the API answers 403 and no data changes (BE-08)

#### Scenario: Identity outside the allowlist
- **WHEN** an authenticated Google identity that is not in the allowlist calls the API
- **THEN** the API answers 403 for every business operation (BE-08)

### Requirement: Allowlist and roles read from the database
The API SHALL read the allowlist and roles from the database, and a removed or deactivated identity SHALL lose access even if its Google session continues. The system SHALL NOT create accounts or store passwords. (RNF-04)

#### Scenario: Identity removed
- **WHEN** an identity is deactivated while its session is open
- **THEN** its next API call is refused

### Requirement: Initial administrator remains configuration-driven
The system SHALL keep the initial administrator defined outside source code, and SHALL NOT offer an operation to add or change allowlist entries. (P-07)

#### Scenario: No management operation
- **WHEN** the API operations are listed
- **THEN** none adds, edits or removes allowlist entries or roles
