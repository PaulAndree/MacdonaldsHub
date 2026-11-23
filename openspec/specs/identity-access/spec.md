# identity-access Specification

## Purpose

Defines how users are authenticated and authorized: Google login through the platform's authentication layer, trusted identity forwarding, allowlist and role checks, the initial administrator and the restricted local development identity.

## Requirements

### Requirement: Google authentication on the frontend only
Users SHALL authenticate with Google through the platform authentication layer (Easy Auth), enabled only on the frontend. Application user login SHALL NOT use Microsoft Entra ID. (RNF-04, BASE-01)

#### Scenario: Unauthenticated access
- **WHEN** a user without a session accesses the application
- **THEN** Google authentication is started through Easy Auth

### Requirement: Trusted identity only from the authentication layer
The API SHALL accept a user identity only from the identity forwarded by Easy Auth through the frontend proxy. A request without that identity SHALL receive 401 before any allowlist lookup. Identity headers supplied by a caller SHALL NOT grant access outside that mechanism. (BASE-04, BASE-12)

#### Scenario: Missing identity header
- **WHEN** the API receives a request without the Easy Auth identity in Azure
- **THEN** it responds 401 without querying the allowlist

#### Scenario: Forged identity header
- **WHEN** a request attempts to impersonate a user by supplying identity headers outside the trusted Easy Auth path
- **THEN** access is denied

### Requirement: Allowlist authorization
The API SHALL authorize each request by checking the authenticated identity against an allowlist and the permissions of the user's role. A user authenticated by Google but absent from the allowlist SHALL be denied. (RNF-04, BASE-02)

#### Scenario: User not in allowlist
- **WHEN** an authenticated user who is not in the allowlist calls the API
- **THEN** access is denied although Google authenticated the user

#### Scenario: Role permission check
- **WHEN** an allowlisted user calls an operation not permitted to their role
- **THEN** the API denies the operation

### Requirement: Initial administrator configured outside code
The initial administrator SHALL be defined through configuration outside source code and SHALL be able to use the minimal technical flow. The actual identities and allowlist contents are pending decision P-07 and SHALL NOT be assumed. (BASE-03)

#### Scenario: Initial administrator access
- **WHEN** the configured initial administrator signs in
- **THEN** they are authorized and complete the screen → API → PostgreSQL flow

### Requirement: Restricted local development identity
A local development identity adapter with a configurable role SHALL be available for local use only. The process SHALL refuse to start with a clear error when it is enabled outside the local environment. (RNF-16, BASE-08)

#### Scenario: Development identity in Azure
- **WHEN** the application starts in Azure with the development identity enabled
- **THEN** startup is rejected with a clear error message

#### Scenario: Development identity locally
- **WHEN** the application starts locally with the development identity and a configured role
- **THEN** requests act as a user with that role
