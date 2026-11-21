import smtplib
import uuid
from email.message import EmailMessage

import httpx
import pytest

pytestmark = pytest.mark.integration


def test_local_mail_is_captured_and_not_relayed(mailpit: tuple[str, int, str]) -> None:  # BASE-09
    host, port, api = mailpit
    marker = uuid.uuid4().hex
    msg = EmailMessage()
    msg["From"] = "institutional@example.test"
    msg["To"] = "test-recipient@example.test"  # never a real provider address
    msg["Subject"] = f"capture check {marker}"
    msg.set_content("technical check, order id 0000")

    with smtplib.SMTP(host, port, local_hostname="localhost", timeout=5) as smtp:
        smtp.send_message(msg)

    found = httpx.get(f"{api}/api/v1/search", params={"query": marker}, timeout=5).json()
    assert found["messages_count"] == 1
    captured = found["messages"][0]
    assert [t["Address"] for t in captured["To"]] == ["test-recipient@example.test"]

    # Mailpit is a sink: it only relays if explicitly configured, which Compose never does.
    info = httpx.get(f"{api}/api/v1/info", timeout=5).json()
    assert not info.get("RelayConfig", {}).get("SMTPServer")
