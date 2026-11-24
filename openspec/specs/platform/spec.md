# platform Specification

## Purpose

Defines the deployable runtime foundation of Delivery Hub: service topology, environments, persistence, storage access, worker exclusion, observability, delivery pipeline and migrations. It contains no business behavior.

## Requirements

### Requirement: Three application services
The system SHALL run as three application services: a frontend, an API and one worker. The API and the worker SHALL share the same backend code and image. No separate services SHALL exist for import and for email sending. Each service SHALL expose a health check.

#### Scenario: Services start and report health
- **WHEN** the platform is started in any environment
- **THEN** the frontend, API and worker are running and the frontend and API report healthy through their health checks
- **AND** the worker reports its lifecycle state without any public ingress

### Requirement: Internal-only API ingress
In Azure, the API SHALL be reachable only through the frontend's `/api` proxy and SHALL have internal ingress. The worker SHALL have no ingress. (BASE-11)

#### Scenario: Direct external call to the API
- **WHEN** a client outside the Container Apps environment calls the API address directly, with or without an identity header
- **THEN** the API is not reachable

### Requirement: Configuration selects adapters, not rules
The system SHALL select adapters (identity, storage, mail transport, telemetry output) through environment variables only. Business rules and code SHALL be identical across local, test and production. (RNF-15)

#### Scenario: Same code in different environments
- **WHEN** the same backend image is started with local and Azure configuration
- **THEN** only the selected adapters differ and no business rule changes

### Requirement: Secrets kept out of code and logs
Secrets SHALL NOT appear in source code, documentation, logs, database plaintext or version control. `.env` SHALL be excluded from version control and `.env.example` SHALL list variable names without secret values. In Azure, secrets SHALL be held in Key Vault and services SHALL reach storage and secrets through managed identities. (RNF-04)

#### Scenario: Repository contains no secrets
- **WHEN** the repository and the startup logs are inspected
- **THEN** no secret value is present and `.env` is ignored by version control

### Requirement: Reproducible local environment
The system SHALL provide a Compose environment with frontend, API, one worker, PostgreSQL with persistent storage, Azurite with persistent storage and SMTP capture. A single command SHALL start it and it SHALL NOT require Azure access. Local email SHALL stay in SMTP capture and SHALL NOT reach real providers. (RNF-14, BASE-09)

#### Scenario: Local email is captured
- **WHEN** the local environment is running and a mail is submitted to the local SMTP transport
- **THEN** it appears only in the SMTP capture and no message is addressed to a real provider
- **AND** no outbox consumer is required for this check

### Requirement: Persistence across restarts
Restarting containers SHALL NOT delete PostgreSQL data or stored files. Services SHALL recover automatically after restart. (RNF-03, BASE-06)

#### Scenario: Restart of data stores and applications
- **WHEN** PostgreSQL, Azurite and the application processes are restarted
- **THEN** previously stored database records and files are still present
- **AND** the services return to a healthy state

### Requirement: Storage service with temporary direct upload
The system SHALL access file storage through a storage abstraction backed by Azurite locally and Blob Storage with managed identity in Azure. The API SHALL grant a temporary, create-only upload permission limited to the authorized file in the `uploads` container, usable directly from the browser. CORS SHALL be configured in both environments. The system SHALL provide a `confirmed` container for later use.

#### Scenario: Upload of a technical file
- **WHEN** an authorized user requests an upload permission and uploads a technical file from the browser
- **THEN** the file is stored in Azurite (or Blob in Azure) and the API identifies it
- **AND** no incident is created (BASE-05)

#### Scenario: Permission limited to the authorized file
- **WHEN** the temporary permission is used for a different file name or to overwrite or read an existing file
- **THEN** the storage service rejects the operation

### Requirement: Minimal technical flow
The system SHALL provide technical operations in the API, with no user-facing screen, through which the technical team verifies identity, the PostgreSQL connection and a direct upload to storage. They SHALL verify connectivity only and SHALL NOT anticipate business logic. (BASE-03)

#### Scenario: Technical round trip
- **WHEN** an authorized user calls the technical operations
- **THEN** the API confirms the identity and a successful PostgreSQL connection

### Requirement: Single active worker with PostgreSQL exclusion
The system SHALL run one permanent worker replica. PostgreSQL mutual exclusion SHALL ensure that only one worker owns the processing loop even when two deployment revisions overlap. The worker in this change SHALL only demonstrate its lifecycle and exclusion and SHALL NOT import or send. (RNF-09, BASE-07)

#### Scenario: Overlapping worker revisions
- **WHEN** two worker instances run at the same time
- **THEN** only one acquires ownership of the processing loop and the other does not process work

#### Scenario: Ownership after owner stops
- **WHEN** the owning worker stops
- **THEN** the remaining instance can acquire ownership

### Requirement: Traceable requests and processes
API requests and worker processes SHALL emit telemetry that identifies actor, correlation and result without secret data. Telemetry SHALL be exported to Azure Monitor and Application Insights in Azure, with a configurable local output. (RNF-05)

#### Scenario: Request correlation
- **WHEN** an authenticated API request is processed
- **THEN** the telemetry records the actor, a correlation identifier and the outcome, and contains no secrets

### Requirement: Operability and documented restore
The system SHALL provide logs and technical alerts, and SHALL document one tested database restoration procedure. Concrete operating objectives are pending decision P-05 and SHALL NOT be assumed. (RNF-10)

#### Scenario: Restore rehearsal
- **WHEN** the documented restoration procedure is followed in a non-production environment
- **THEN** the database is restored and the result is recorded

### Requirement: UTC storage and Europe/Madrid presentation
Event timestamps SHALL use UTC criteria and be presented in Europe/Madrid time. An incident time of day is optional and SHALL NOT be invented. (RNF-13)

#### Scenario: Presentation timezone
- **WHEN** a UTC event timestamp is presented to a user
- **THEN** it is shown in Europe/Madrid local time

### Requirement: Isolated test environment
A test environment SHALL exist separately from production with its own database, storage and mail configuration. Test batches and outbox entries SHALL NOT be copied or promoted to production. (BASE-10)

#### Scenario: Resource isolation
- **WHEN** the resources of the test and production environments are compared
- **THEN** their database, storage and mail configuration are distinct and no test data is shared

### Requirement: Azure infrastructure as code
Azure resources SHALL be provisioned from versioned infrastructure code per environment: Container Apps services, image registry, one PostgreSQL Flexible Server per environment, Blob storage, Key Vault, managed identities and observability. (RNF-11)

#### Scenario: Provisioning an environment
- **WHEN** the infrastructure code is applied to an environment
- **THEN** the services run in Container Apps against that environment's own external PostgreSQL server

### Requirement: Delivery pipeline and reversible migrations
The pipeline SHALL run lint, tests, image builds and deployment, and SHALL run integration tests against real PostgreSQL and Azurite. Database migrations SHALL be versioned and reversible.

#### Scenario: Pipeline on a change
- **WHEN** a change is pushed
- **THEN** lint, tests and image builds run and a failure blocks deployment

#### Scenario: Migration rollback
- **WHEN** a migration is applied and then reverted
- **THEN** the schema returns to its previous version

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

### Requirement: Business schema with reversible migrations
The business schema SHALL be created by versioned migrations that can be applied and reverted, each tested up and down, with the uniqueness of provider plus Order ID and the one-unconfirmed-batch rule enforced by PostgreSQL constraints. (RNF-03, RNF-09)

#### Scenario: Migrate up and down
- **WHEN** the migrations are applied and then reverted on a real PostgreSQL
- **THEN** both directions succeed and the schema returns to its previous state

### Requirement: Initial catalog from configuration
The branch catalog and the providers with their configured recipients SHALL be loaded from configuration or migration by the technical team, SHALL exist before import tests, and SHALL NOT be invented: their real values are supplied by the administrator, and examples are only test fixtures. (RF-06, P-01)

#### Scenario: Import with an empty catalog
- **WHEN** the catalog has not been loaded
- **THEN** imports are not enabled and the missing configuration is reported at startup

### Requirement: Backend matches the approved contract
The system SHALL fail a contract test when the OpenAPI generated by the API differs from the approved `docs/api/openapi.yaml` in any operation it implements, and SHALL list explicitly the operations deferred to a later change. A different contract SHALL require a new approval. (ADR-16, BE-18)

#### Scenario: Divergent response schema
- **WHEN** an implemented operation returns a field the approved contract does not define
- **THEN** the contract test fails and integration is blocked (BE-18)

### Requirement: Integration tested with real services
Rules about uniqueness, transactions and concurrency SHALL be tested against a real PostgreSQL, and file handling against a real Azurite. Example data of the frontend SHALL NOT count as integration evidence. (BE-03, BE-05)

#### Scenario: Concurrent confirmation test
- **WHEN** the concurrency tests run
- **THEN** they run against a real PostgreSQL and not against a mock

### Requirement: Approved frontend integrated with the real API
The standard frontend build SHALL talk to the real API with no example data, and the walkthroughs UI-01 to UI-06 and UI-09 to UI-12 SHALL be repeated against it. UI-07 and UI-08 SHALL be repeated after change 3 provides sending. (UI-11)

#### Scenario: Walkthrough against the real API
- **WHEN** the administrator repeats a walkthrough with the real backend
- **THEN** the behavior matches the approved example

### Requirement: No approved operation remains deferred
The system SHALL serve every operation of the approved contract, and the contract test SHALL fail if any operation is neither served and identical nor changed with a new approval. The contract version of this change SHALL make the batch of a queue entry optional and SHALL be approved by the administrator before it is integrated. (ADR-16, BE-18)

#### Scenario: Contract test after this change
- **WHEN** the contract test runs
- **THEN** it has no deferred operation and every approved operation is compared

#### Scenario: Contract changed
- **WHEN** the contract is modified
- **THEN** the change is flagged as needing a new administrator approval
