# metrics Specification

## Purpose
Defines the dashboard interface for tracking claims: email claims and manual Glovo claims kept apart, explicit recovered amounts, pending claims and their age, and an honest treatment of incomplete data and of criteria not yet approved.

## Requirements

### Requirement: Email and Glovo shown separately
The dashboard SHALL present email claims and manual Glovo claims as separate figures, by channel, provider and branch, and SHALL identify the environment whose data it shows. (RF-15, UI-06)

#### Scenario: Dashboard in the test environment
- **WHEN** the user opens the dashboard in the test environment with example data
- **THEN** it shows the environment as test, email and Glovo apart, and does not present the figures as production activity

### Requirement: Distinct dates with a stated criterion
The dashboard SHALL distinguish incident, claim and recovery dates and SHALL state which date each figure and filter uses. Default filters and temporal formulas SHALL be shown as design examples, not approved criteria, while P-04 is pending. (RF-15, UI-06)

#### Scenario: Filter by claim date
- **WHEN** the user filters the dashboard by claim date
- **THEN** the interface states that the filter uses the claim date and marks any default as an example

### Requirement: Explicit recovered amount and incomplete data
The dashboard SHALL show only recovered amounts recorded explicitly and SHALL NOT treat an absent amount as zero. When a figure aggregates incomplete data it SHALL warn that it is incomplete instead of presenting a clean total. (RF-15, UI-06)

#### Scenario: Aggregate with absent amounts
- **WHEN** some incidents in a total have no claim amount
- **THEN** the figure carries an incompleteness warning and states how many incidents lack the amount

### Requirement: Pending claims and their age
The dashboard SHALL list claims still without a result and their age. The age criterion SHALL be marked as a design example while P-04 is pending. (RF-15)

#### Scenario: Claims without result
- **WHEN** the user views pending claims
- **THEN** each shows how long it has been waiting, with the criterion marked as an example

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

### Requirement: Claims, recoveries and the date used
The system SHALL count as a claim every incident that has a claim date (claimed, resolved or rejected) and as a recovery every incident marked Resuelta, whether or not it has a recorded amount. The default date SHALL be the claim date, any filter SHALL be able to use the incident, claim or recovery date instead, and the date used SHALL always be stated in the response. (RF-15, P-04)

#### Scenario: Default date
- **WHEN** the dashboard is read without choosing a date
- **THEN** the figures use the claim date and the response says so

#### Scenario: A rejected incident
- **WHEN** an incident is Rechazada
- **THEN** it counts as a claim and not as a recovery

### Requirement: Recovery rate by number of claims
The system SHALL compute the recovery rate as recoveries divided by claims, by number and not by amount, with every claim of the period in the denominator, pending and rejected ones included, and SHALL give it with four decimals. It SHALL be absent ("No calculable") when there are no claims in the period or when the recovery date is the one used, and SHALL never be shown as zero in those cases. (RF-15, P-04)

#### Scenario: Rate with pending claims
- **WHEN** a period has 5 claims, 1 of them resolved and 2 still without result
- **THEN** the rate is 0.2000

#### Scenario: No claims
- **WHEN** the period has no claims
- **THEN** the rate is absent, not 0

#### Scenario: Recovery date chosen
- **WHEN** the recovery date is the one used
- **THEN** the rate is absent because the claims of that period are not defined

### Requirement: Amounts are added up from what is known
The system SHALL add the known amounts only, SHALL report how many incidents have no claim amount and flag the figure as incomplete, and SHALL leave a figure with no known amount absent, never zero. A Resuelta incident without a recorded recovered amount SHALL count as a recovery and make the recovered figure incomplete. (RF-15, RNF-13, P-04)

#### Scenario: Some amounts missing
- **WHEN** 3 claimed incidents have amounts 10.00 and 5.50 and one has none
- **THEN** the claimed amount is 15.50, the incomplete count is 1 and a warning says the total is incomplete

#### Scenario: No amount known
- **WHEN** no claimed incident of the period has an amount
- **THEN** the claimed amount is absent, not zero

### Requirement: Age of claims without a result
The system SHALL list the claims that have no result with their age in calendar days from the claim date to today in Europe/Madrid time, from the oldest to the newest, with no threshold and no alert. (RF-15, P-04)

#### Scenario: Pending claims
- **WHEN** two claims have no result, one claimed 10 days ago and one 2 days ago
- **THEN** both are listed oldest first with ages 10 and 2

### Requirement: Channels and breakdown
The system SHALL report the email channel (Uber Eats and Just Eat) and the Glovo channel apart, each with its counts and amounts, and a breakdown by provider and branch where an absent branch is its own row. When nothing matches, the response SHALL have no channels and a no-data warning. (RF-15)

#### Scenario: Nothing in the period
- **WHEN** no incident matches the filters
- **THEN** the channels, the breakdown and the pending list are empty and a no-data warning is given
