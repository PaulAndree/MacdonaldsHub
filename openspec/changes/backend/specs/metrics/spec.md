# Spec Delta

## ADDED Requirements

### Requirement: Aggregation from recorded data in PostgreSQL
The system SHALL compute the dashboard figures in PostgreSQL from recorded incidents, claims and recoveries, without a separate analytical store. Recovered amounts and rates SHALL rely only on recorded amounts, an absent amount SHALL NOT be treated as zero, and incomplete data SHALL be flagged with its count. (RF-15, RNF-13)

#### Scenario: Incident without claim amount
- **WHEN** an incident has no claim amount
- **THEN** it is counted as incomplete data and no zero is added

### Requirement: Email and Glovo separated
The system SHALL report email claims and manual Glovo claims separately, each with its own counts and amounts. An email claim SHALL count only after change 3 records a send without error; importing a row or creating an outbox record SHALL NOT count as claiming. (RF-15)

#### Scenario: Pending emails are not claims
- **WHEN** an Uber Eats incident has a Pendiente outbox record
- **THEN** it does not count as claimed in the email channel

### Requirement: Test and production isolated
The system SHALL NOT mix test and production figures, and SHALL identify the environment on the figures. (RF-12)

#### Scenario: Test environment figures
- **WHEN** the dashboard is read in the test environment
- **THEN** the figures come only from that environment's data and are identified as test

### Requirement: Calculation criteria pending P-04
The system SHALL NOT implement the default date of each filter, the rate formula and denominator, division by zero, the age criterion, the restrictions on the recovered amount, or the sum rules with absent amounts until P-04 is resolved by the administrator. Examples shown in the approved design SHALL NOT become approved formulas. (P-04)

#### Scenario: Phase blocked
- **WHEN** P-04 is not yet resolved
- **THEN** the metrics phase does not start and no calculation of those criteria is shipped
