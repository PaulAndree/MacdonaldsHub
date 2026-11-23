# Spec Delta

## ADDED Requirements

### Requirement: Versioned API contract
The operations the interface needs from the backend SHALL be defined in a versioned OpenAPI file at `docs/api/openapi.yaml`, with inputs, outputs, states and errors, and the example responses SHALL be valid against its schemas. A change to the approved contract SHALL require a new approval. (ADR-16)

#### Scenario: Examples validate against the contract
- **WHEN** the contract and its example responses are checked
- **THEN** every example response is valid against its schema

#### Scenario: Contract changed after approval
- **WHEN** the approved contract is modified
- **THEN** the change is flagged as needing a new administrator approval

### Requirement: Contract distinctions
The contract SHALL distinguish the incident date (with an optional time) from system timestamps, and an absent value from zero, for every optional date and amount. (RNF-13)

#### Scenario: Optional amount absent
- **WHEN** an incident has no claim amount
- **THEN** the contract represents it as absent, not as zero

### Requirement: Example data mode
The interface SHALL support an example mode, selected at build time, that serves example data without any business server. The mode SHALL display a permanent notice that the data is example data. The production image SHALL be built without example mode. (UI-11)

#### Scenario: Example build in the test environment
- **WHEN** the test environment runs the example build
- **THEN** every screen shows the example-data notice and Google sign-in still protects access

#### Scenario: Production build
- **WHEN** the production image is built
- **THEN** it contains no example data and no example-mode notice

### Requirement: Spanish, desktop and accessible interface
The interface SHALL be in Spanish for desktop browsers, usable by keyboard, with sufficient contrast, and SHALL present understandable error messages. (RNF-07, RNF-08)

#### Scenario: Keyboard-only walkthrough
- **WHEN** a user completes the import review flow using only the keyboard
- **THEN** every action is reachable and the focus is always visible

### Requirement: Non-happy states in every area
Each area SHALL show distinct states for no data, loading, error, incomplete data, permission denied, discarded batch and paused queue, where they apply, besides the success path. (RNF-07)

#### Scenario: Area without data
- **WHEN** an area has no data
- **THEN** it shows an explicit empty state, not a blank screen

#### Scenario: Request error
- **WHEN** a request fails
- **THEN** the area shows an error state that does not claim an outcome it cannot know

### Requirement: Visible test environment
The interface SHALL identify the test environment visibly, and its recipients and metrics SHALL NOT be presented as production activity. (RF-12)

#### Scenario: Test environment banner
- **WHEN** a user opens the application in the test environment
- **THEN** the test environment is identified on every screen

### Requirement: Explicit administrator approval
The change SHALL NOT be considered closed until the administrator explicitly approves layout, navigation, flows, messages and actions, and the approval SHALL record the design version and the contract version approved. Requested adjustments SHALL be made before closure. (UI-11)

#### Scenario: Approval recorded
- **WHEN** the administrator approves after reviewing every walkthrough
- **THEN** the approval is recorded with the design version and the contract version

#### Scenario: Adjustments requested
- **WHEN** the administrator asks for adjustments
- **THEN** the change stays open and the approval is not recorded until they are made

## MODIFIED Requirements

### Requirement: Minimal technical flow
The system SHALL provide technical operations in the API, with no user-facing screen, through which the technical team verifies identity, the PostgreSQL connection and a direct upload to storage. They SHALL verify connectivity only and SHALL NOT anticipate business logic. (BASE-03)

#### Scenario: Technical round trip
- **WHEN** an authorized user calls the technical operations
- **THEN** the API confirms the identity and a successful PostgreSQL connection
