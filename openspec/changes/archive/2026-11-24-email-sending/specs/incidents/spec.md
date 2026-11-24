# Spec Delta

## ADDED Requirements

### Requirement: The incident follows the result of its email
The system SHALL move an incident from Pendiente de envío to Reclamada, with the claim date of the day the send ended in Europe/Madrid time, when its email is Enviado, and to Error de envío, with the reason in its history, when its email is Error. The history SHALL record each change as an email result with the actor system, and an incident in Error de envío SHALL NOT return to Pendiente de envío. The incident and its email SHALL change in the same transaction. (RN-12, RF-13, MAIL-06, E-10)

#### Scenario: Email sent
- **WHEN** an email is recorded as Enviado
- **THEN** its incident is Reclamada with the claim date and an email-result entry in its history (MAIL-06)

#### Scenario: Email failed
- **WHEN** an email is recorded as Error
- **THEN** its incident is Error de envío, the reason is in the history, and it cannot return to Pendiente de envío (E-10)

#### Scenario: A claimed incident counts in the email channel
- **WHEN** an email is Enviado
- **THEN** the incident counts as a claim by email in the dashboard from then on
