"""Only the sender may reach a mail transport: nothing on the confirmation path can send email."""

from pathlib import Path

APP = Path(__file__).resolve().parents[2] / "app"
FORBIDDEN = ("smtplib", "aiosmtplib", "MailTransport", "send_message", "sendmail", "OutgoingEmail")
# The sender and the places that build or name the transport.
ALLOWED = {
    APP / "services" / "ports.py",
    APP / "services" / "email_sending.py",
    APP / "composition.py",
    APP / "adapters" / "registry.py",
    APP / "adapters" / "mail" / "smtp.py",
    APP / "worker" / "tasks.py",
}


def test_no_other_module_can_send_email() -> None:
    offenders = []
    for path in APP.rglob("*.py"):
        if path in ALLOWED:
            continue
        source = path.read_text(encoding="utf-8")
        offenders += [f"{path.relative_to(APP)}: {word}" for word in FORBIDDEN if word in source]
    assert offenders == []


def test_the_confirmation_and_the_manual_entry_never_import_the_sender() -> None:
    for name in (
        "services/confirmation.py",
        "services/incidents.py",
        "api/batches.py",
        "api/incidents.py",
    ):
        source = (APP / name).read_text(encoding="utf-8")
        assert "email_sending" not in source and "adapters.mail" not in source, name
