# Spec Delta

## ADDED Requirements

### Requirement: No approved operation remains deferred
The system SHALL serve every operation of the approved contract, and the contract test SHALL fail if any operation is neither served and identical nor changed with a new approval. The contract version of this change SHALL make the batch of a queue entry optional and SHALL be approved by the administrator before it is integrated. (ADR-16, BE-18)

#### Scenario: Contract test after this change
- **WHEN** the contract test runs
- **THEN** it has no deferred operation and every approved operation is compared

#### Scenario: Contract changed
- **WHEN** the contract is modified
- **THEN** the change is flagged as needing a new administrator approval
