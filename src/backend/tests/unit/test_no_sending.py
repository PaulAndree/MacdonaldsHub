"""Sending belongs to change 3: nothing in this change can reach a mail transport."""

from pathlib import Path

APP = Path(__file__).resolve().parents[2] / "app"
FORBIDDEN = ("smtplib", "aiosmtplib", "MailTransport", "send_message", "sendmail")
ALLOWED = {APP / "services" / "ports.py", APP / "composition.py", APP / "adapters" / "registry.py"}


def test_no_module_of_the_confirmation_path_can_send_email() -> None:
    offenders = []
    for path in APP.rglob("*.py"):
        if path in ALLOWED or "adapters/mail" in path.as_posix():
            continue
        source = path.read_text(encoding="utf-8")
        offenders += [f"{path.relative_to(APP)}: {word}" for word in FORBIDDEN if word in source]
    assert offenders == []
