"""The SMTP transport against the real capture service (RN-14, MAIL-06): nothing leaves the machine."""

import uuid

import httpx
import pytest

from app.adapters.mail.smtp import SmtpMailTransport
from app.services.ports import MailRefused, OutgoingEmail

pytestmark = pytest.mark.integration


def email(order_id: str) -> OutgoingEmail:
    return OutgoingEmail(
        sender="institutional@example.test",
        recipient="test-recipient@example.test",
        subject=f"Reclamación {order_id}",
        body=f"Estimados socios, remitimos el incidente {order_id}. Un saludo",
    )


def test_a_message_reaches_the_capture_service_and_only_it(mailpit: tuple[str, int, str]) -> None:
    host, port, api = mailpit
    order_id = uuid.uuid4().hex
    SmtpMailTransport(host, port, None, None, False).send(email(order_id))
    found = httpx.get(f"{api}/api/v1/search", params={"query": order_id}, timeout=5).json()
    assert found["messages_count"] == 1
    message = found["messages"][0]
    assert [t["Address"] for t in message["To"]] == ["test-recipient@example.test"]
    assert message["From"]["Address"] == "institutional@example.test"
    assert message["Subject"] == f"Reclamación {order_id}"


def test_the_body_holds_the_incident_number_and_nothing_else(mailpit: tuple[str, int, str]) -> None:
    host, port, api = mailpit
    order_id = uuid.uuid4().hex
    SmtpMailTransport(host, port, None, None, False).send(email(order_id))
    found = httpx.get(f"{api}/api/v1/search", params={"query": order_id}, timeout=5).json()
    detail = httpx.get(f"{api}/api/v1/message/{found['messages'][0]['ID']}", timeout=5).json()
    assert order_id in detail["Text"]
    assert "€" not in detail["Text"]


def test_a_service_that_is_not_there_is_a_refusal_not_a_hang() -> None:
    with pytest.raises(MailRefused):
        SmtpMailTransport("127.0.0.1", 1, None, None, False, timeout=2).send(email("x"))
