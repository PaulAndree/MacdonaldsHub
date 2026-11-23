# Spec Delta

## Purpose

Defines the deployable runtime foundation of Delivery Hub: service topology, environments, persistence, storage access, worker exclusion, observability, delivery pipeline and migrations. It contains no business behavior.

## ADDED Requirements

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
The system SHALL provide a minimal screen through which an authorized user reaches the API and PostgreSQL. The screen and API SHALL verify identity and connectivity only and SHALL NOT anticipate functional design or business logic. (BASE-03)

#### Scenario: Technical round trip
- **WHEN** an authorized user opens the minimal screen
- **THEN** the screen calls the API and the API confirms a successful PostgreSQL connection

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
