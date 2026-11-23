"""The SMTP transport and how it tells a refusal from an unverified outcome (RN-12, MAIL-07)."""

import smtplib
from typing import Any

import pytest

from app.adapters.mail.smtp import SmtpMailTransport
from app.services.ports import MailRefused, MailUnverified, OutgoingEmail

EMAIL = OutgoingEmail(
    sender="institutional@example.test",
    recipient="test-recipient@example.test",
    subject="Reclamación de incidente",
    body="Estimados socios Ubereats, remitimos el siguiente incidente No Incidente AB-1029x para su reclamación. Un saludo Macdonalds",
)


class FakeSmtp:
    """Records the phases; each can be told to fail."""

    instances: list["FakeSmtp"] = []
    fail: dict[str, Exception] = {}
    rcpt_reply: tuple[int, bytes] = (250, b"ok")
    data_reply: tuple[int, bytes] = (250, b"queued")

    def __init__(
        self, host: str, port: int, timeout: float, local_hostname: str | None = None
    ) -> None:
        self.calls: list[str] = []
        self.sent: bytes | None = None
        self.timeout = timeout
        self.host, self.port = host, port
        FakeSmtp.instances.append(self)
        self._maybe("connect")

    def _maybe(self, phase: str) -> None:
        self.calls.append(phase)
        if phase in FakeSmtp.fail:
            raise FakeSmtp.fail[phase]

    def ehlo(self) -> tuple[int, bytes]:
        self._maybe("ehlo")
        return 250, b"ok"

    def starttls(self) -> tuple[int, bytes]:
        self._maybe("starttls")
        return 220, b"go"

    def login(self, user: str, password: str) -> tuple[int, bytes]:
        self._maybe("login")
        self.calls.append(f"login:{user}")
        return 235, b"ok"

    def mail(self, sender: str) -> tuple[int, bytes]:
        self._maybe("mail")
        return 250, b"ok"

    def rcpt(self, recipient: str) -> tuple[int, bytes]:
        self._maybe("rcpt")
        return FakeSmtp.rcpt_reply

    def data(self, message: bytes) -> tuple[int, bytes]:
        self._maybe("data")
        self.sent = message
        if FakeSmtp.data_reply[0] != 250:
            raise smtplib.SMTPDataError(*FakeSmtp.data_reply)
        return FakeSmtp.data_reply

    def quit(self) -> tuple[int, bytes]:
        self.calls.append("quit")
        if "quit" in FakeSmtp.fail:
            raise FakeSmtp.fail["quit"]
        return 221, b"bye"

    def close(self) -> None:
        self.calls.append("close")


@pytest.fixture(autouse=True)
def reset() -> None:
    FakeSmtp.instances = []
    FakeSmtp.fail = {}
    FakeSmtp.rcpt_reply = (250, b"ok")
    FakeSmtp.data_reply = (250, b"queued")


def transport(**over: Any) -> SmtpMailTransport:
    params: dict[str, Any] = dict(
        host="smtp.example.test",
        port=587,
        user=None,
        password=None,
        starttls=False,
        timeout=20.0,
        factory=FakeSmtp,
    )
    return SmtpMailTransport(**{**params, **over})


# --- the happy path ----------------------------------------------------------------------------------------


def test_a_message_is_handed_over_once_in_the_expected_phases() -> None:
    transport().send(EMAIL)
    (smtp,) = FakeSmtp.instances
    assert smtp.calls[:5] == ["connect", "ehlo", "mail", "rcpt", "data"]
    assert smtp.calls[-2:] == ["quit", "close"]
    assert smtp.calls.count("data") == 1  # one attempt: the message goes out once


def test_the_body_decodes_to_the_stored_text_and_nothing_else() -> None:
    import email
    from email import policy

    transport().send(EMAIL)
    message = email.message_from_bytes(FakeSmtp.instances[0].sent or b"", policy=policy.default)
    assert message["Subject"] == "Reclamación de incidente"
    assert message.get_content().strip() == EMAIL.body
    assert set(message.keys()) >= {"From", "To", "Subject"}


def test_the_socket_timeout_is_shorter_than_the_interval() -> None:
    transport().send(EMAIL)
    assert FakeSmtp.instances[0].timeout < 30


def test_starttls_and_login_happen_only_when_configured() -> None:
    transport().send(EMAIL)
    assert "starttls" not in FakeSmtp.instances[0].calls
    assert not any(c.startswith("login") for c in FakeSmtp.instances[0].calls)
    transport(starttls=True, user="u@example.test", password="pw").send(EMAIL)
    calls = FakeSmtp.instances[1].calls
    assert calls.index("starttls") < calls.index("login") < calls.index("mail")


# --- refusals: nothing was handed over ------------------------------------------------------------------------


@pytest.mark.parametrize(
    "phase",
    ["connect", "ehlo", "starttls", "login", "mail"],
)
def test_a_failure_before_the_recipient_is_a_refusal(phase: str) -> None:
    FakeSmtp.fail[phase] = smtplib.SMTPException("boom")
    with pytest.raises(MailRefused):
        transport(starttls=True, user="u", password="p").send(EMAIL)


def test_a_connection_that_cannot_be_made_is_a_refusal() -> None:
    FakeSmtp.fail["connect"] = ConnectionRefusedError("refused")
    with pytest.raises(MailRefused) as caught:
        transport().send(EMAIL)
    assert "servidor de correo" in str(caught.value)


def test_a_rejected_recipient_is_a_refusal_with_the_server_answer() -> None:
    FakeSmtp.rcpt_reply = (550, b"mailbox unavailable")
    with pytest.raises(MailRefused) as caught:
        transport().send(EMAIL)
    assert "550" in str(caught.value) and "mailbox unavailable" in str(caught.value)
    assert "data" not in FakeSmtp.instances[0].calls  # nothing was sent after the refusal


def test_data_rejected_by_the_server_is_a_refusal() -> None:
    FakeSmtp.data_reply = (554, b"spam")
    with pytest.raises(MailRefused) as caught:
        transport().send(EMAIL)
    assert "554" in str(caught.value)


# --- unverified: the message may have been handed over ------------------------------------------------------------------


@pytest.mark.parametrize(
    "error",
    [
        smtplib.SMTPServerDisconnected("cut"),
        TimeoutError("slow"),
        TimeoutError("slow"),
        ConnectionResetError("reset"),
        OSError("io"),
    ],
)
def test_a_failure_while_sending_the_data_is_unverified(error: Exception) -> None:
    FakeSmtp.fail["data"] = error
    with pytest.raises(MailUnverified) as caught:
        transport().send(EMAIL)
    assert "no se pudo verificar" in str(caught.value)


def test_an_error_closing_the_session_after_acceptance_is_not_a_failure() -> None:
    FakeSmtp.fail["quit"] = smtplib.SMTPServerDisconnected("closed")
    transport().send(EMAIL)  # the service accepted the message: it is sent


def test_the_reason_never_contains_the_credentials() -> None:
    FakeSmtp.fail["login"] = smtplib.SMTPAuthenticationError(535, b"bad credentials for pw-secret")
    with pytest.raises(MailRefused) as caught:
        transport(user="sender@example.test", password="pw-secret").send(EMAIL)
    assert "pw-secret" not in str(caught.value)
