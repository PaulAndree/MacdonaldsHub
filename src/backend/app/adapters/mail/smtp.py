"""SMTP transport over the standard library: the capture service locally, the institutional
mailbox in Azure (RNF-04).

The phases are kept apart on purpose. Up to the recipient, a failure means nothing was handed over
(a refusal). Once the data is being sent, a cut connection or a timeout leaves the outcome unknown
(unverified). A message the server rejected after the data is a refusal. Credentials never appear in
a reason.
"""

import contextlib
import smtplib
from collections.abc import Callable
from email.message import EmailMessage
from typing import Any

from app.services.ports import MailRefused, MailUnverified, OutgoingEmail

REASON_LIMIT = 200


class SmtpMailTransport:
    def __init__(
        self,
        host: str,
        port: int,
        user: str | None,
        password: str | None,
        starttls: bool,
        timeout: float = 20.0,  # shorter than the 30-second interval
        factory: Callable[..., Any] = smtplib.SMTP,
    ) -> None:
        self._host, self._port = host, port
        self._user, self._password = user, password
        self._starttls = starttls
        self._timeout = timeout
        self._factory = factory

    def send(self, email: OutgoingEmail) -> None:
        message = EmailMessage()
        message["From"] = email.sender
        message["To"] = email.recipient
        message["Subject"] = email.subject
        message.set_content(email.body)

        smtp = self._open(email)
        try:
            self._envelope(smtp, email)
            self._data(smtp, message.as_bytes())
        finally:
            with contextlib.suppress(Exception):  # the message is decided; closing may not matter
                smtp.quit()
            with contextlib.suppress(Exception):
                smtp.close()

    def _open(self, email: OutgoingEmail) -> Any:
        try:
            return self._factory(
                self._host, self._port, timeout=self._timeout, local_hostname="localhost"
            )
        except (smtplib.SMTPException, OSError) as exc:
            raise MailRefused(
                f"No se pudo conectar con el servidor de correo: {self._safe(exc)}"
            ) from None

    def _envelope(self, smtp: Any, email: OutgoingEmail) -> None:
        """Everything before the data: a failure here means nothing was handed over."""
        try:
            smtp.ehlo()
            if self._starttls:
                smtp.starttls()
                smtp.ehlo()
            if self._user:
                smtp.login(self._user, self._password or "")
            code, answer = smtp.mail(email.sender)
            if code != 250:
                raise MailRefused(self._answer("El servidor rechazó el remitente", code, answer))
            code, answer = smtp.rcpt(email.recipient)
            if code not in (250, 251):
                raise MailRefused(self._answer("El servidor rechazó el destinatario", code, answer))
        except MailRefused:
            raise
        except (smtplib.SMTPException, OSError) as exc:
            raise MailRefused(
                f"El servidor de correo rechazó el envío: {self._safe(exc)}"
            ) from None

    def _data(self, smtp: Any, content: bytes) -> None:
        try:
            smtp.data(content)
        except smtplib.SMTPDataError as exc:  # the server answered: it did not accept the message
            reason = self._answer("El servidor rechazó el mensaje", exc.smtp_code, exc.smtp_error)
            raise MailRefused(reason) from None
        except (smtplib.SMTPException, OSError):
            # Cut or timed out while the data was going out: it may or may not have arrived.
            raise MailUnverified(
                "El envío se interrumpió y no se pudo verificar el resultado."
            ) from None

    def _answer(self, what: str, code: int, answer: bytes | str) -> str:
        text = answer.decode("utf-8", "replace") if isinstance(answer, bytes) else str(answer)
        return f"{what}: {code} {self._clip(text)}"

    def _safe(self, exc: BaseException) -> str:
        return self._clip(str(exc))

    def _clip(self, text: str) -> str:
        if self._password:
            text = text.replace(self._password, "[oculto]")
        if self._user:
            text = text.replace(self._user, "[oculto]")
        return text[:REASON_LIMIT]
