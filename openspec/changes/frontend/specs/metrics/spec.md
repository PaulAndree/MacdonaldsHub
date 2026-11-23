# Spec Delta

## Purpose

Defines the dashboard interface for tracking claims: email claims and manual Glovo claims kept apart, explicit recovered amounts, pending claims and their age, and an honest treatment of incomplete data and of criteria not yet approved.

## ADDED Requirements

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
