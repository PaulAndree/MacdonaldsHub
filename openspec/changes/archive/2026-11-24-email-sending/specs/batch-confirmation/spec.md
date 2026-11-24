# Spec Delta

## MODIFIED Requirements

### Requirement: Batch completion
The system SHALL mark a confirmed batch Completado when all its emails are Enviado or Error, and SHALL allow a confirmed batch with no emails to be Completado at confirmation. Completado SHALL NOT mean that every send succeeded, and the totals of Enviado and Error SHALL be shown apart. (RF-11, MAIL-08)

#### Scenario: Glovo-only batch
- **WHEN** a batch whose new rows are all Glovo is confirmed
- **THEN** it can be Completado at once, with no email

#### Scenario: Every email ended, some in error
- **WHEN** the last pending email of a confirmed batch ends and some of its emails are in Error
- **THEN** the batch becomes Completado with separate totals of Enviado and Error (MAIL-08)

#### Scenario: An email is still pending
- **WHEN** a confirmed batch still has a Pendiente or Enviando email
- **THEN** it stays Confirmado
