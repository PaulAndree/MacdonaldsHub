"""Sending the pending emails: one attempt each, never repeated (RF-11, RF-13, ADR-09).

One tick of the worker first ends any attempt a dead process left unfinished (as an unverified
result, never sending it again), then starts at most one attempt. The attempt is recorded durably
before the mail service is called, and its result is recorded afterwards in one transaction. If the
result cannot be recorded, the email stays Enviando and the next recovery turns it into Error: it is
never sent a second time.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from app.services.ports import MailRefused, MailTransport, MailUnverified, OutgoingEmail

LOG = logging.getLogger("app.worker")
UNVERIFIED_REASON = "El envío se interrumpió y no se pudo verificar el resultado."


@dataclass(frozen=True)
class Attempt:
    """An email whose attempt has been recorded as started."""

    email_id: str
    order_id: str
    recipient: str
    subject: str
    body: str  # with {orderId} as the only variable


class SendingRepository(Protocol):
    def recover_interrupted(self) -> int:
        """End every email left Enviando as Error (unverified); returns how many."""
        ...

    def claim(self, authorized_recipient: str | None) -> Attempt | None:
        """Record the start of the next attempt, or None when nothing may start now."""
        ...

    def finish_sent(self, email_id: str) -> bool: ...

    def finish_error(self, email_id: str, kind: str, reason: str) -> bool: ...


@dataclass(frozen=True)
class TickResult:
    recovered: int
    attempted: str | None  # sent | send_failed | interrupted_unverified | None


class EmailConsumer:
    def __init__(
        self,
        repository: SendingRepository,
        transport: MailTransport,
        sender: str,
        authorized_recipient: str | None,
        unavailable: Callable[[], str | None],
    ) -> None:
        self._repository = repository
        self._transport = transport
        self._sender = sender
        self._authorized = authorized_recipient
        self._unavailable = unavailable

    def tick(self) -> TickResult:
        recovered = self._repository.recover_interrupted()
        if self._unavailable() is not None:
            return TickResult(recovered, None)  # nothing starts and nothing becomes an error
        attempt = self._repository.claim(self._authorized)
        if attempt is None:
            return TickResult(recovered, None)
        return TickResult(recovered, self._send(attempt))

    def _send(self, attempt: Attempt) -> str:
        message = OutgoingEmail(
            sender=self._sender,
            recipient=attempt.recipient,
            subject=attempt.subject,
            body=attempt.body.replace("{orderId}", attempt.order_id),
        )
        try:
            self._transport.send(message)
        except MailRefused as exc:
            return self._error(attempt, "send_failed", str(exc))
        except MailUnverified as exc:
            return self._error(attempt, "interrupted_unverified", str(exc))
        except Exception:  # unknown: it may have gone out, so it is never a clean refusal
            LOG.exception("unexpected failure while sending an email")
            return self._error(attempt, "interrupted_unverified", UNVERIFIED_REASON)
        self._repository.finish_sent(attempt.email_id)
        return "sent"

    def _error(self, attempt: Attempt, kind: str, reason: str) -> str:
        self._repository.finish_error(attempt.email_id, kind, reason)
        return kind
