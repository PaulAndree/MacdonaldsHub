# Spec Delta

## ADDED Requirements

### Requirement: Distinct states for no session and no authorization
The interface SHALL tell apart a missing or expired session from a user who is authenticated but not on the allowlist, with a clear Spanish message for each. (RNF-04, RNF-07, BASE-01, BASE-02)

#### Scenario: Missing or expired session
- **WHEN** the API reports no valid session
- **THEN** the interface explains that the session is not valid and how to sign in again

#### Scenario: Authenticated user outside the allowlist
- **WHEN** the API denies a user whom Google authenticated
- **THEN** the interface shows an access-denied screen that explains the user is not authorized

### Requirement: Visible session, role and permissions
The interface SHALL show the signed-in identity, its role and the environment, and SHALL show only the areas and actions the role allows according to the permissions matrix: the administrator operates, the global manager, if enabled, only consults incidents, history and the dashboard. (RNF-04)

#### Scenario: Administrator
- **WHEN** an administrator signs in
- **THEN** the interface shows their identity, the role and every area and action

#### Scenario: Global manager role
- **WHEN** a user with the global manager role signs in
- **THEN** only incidents, history and the dashboard are offered

### Requirement: Hiding an action does not replace authorization
The interface SHALL NOT treat hidden actions as security. If a user without permission attempts an administrative action, the interface SHALL represent the denial returned by the API instead of failing silently. (UI-10)

#### Scenario: Global manager attempts an administrative action
- **WHEN** a global manager triggers an administrative action
- **THEN** the interface shows an access-denied result for that action and changes nothing

## MODIFIED Requirements

### Requirement: Initial administrator configured outside code
The initial administrator SHALL be defined through configuration outside source code and SHALL be authorized to use the application with the administrator role. The actual identities and allowlist contents are pending decision P-07 and SHALL NOT be assumed. (BASE-03)

#### Scenario: Initial administrator access
- **WHEN** the configured initial administrator signs in
- **THEN** they are authorized and the interface shows their administrator role
